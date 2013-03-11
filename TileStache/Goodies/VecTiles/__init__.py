from math import pi, log as _log
from StringIO import StringIO
from httplib import HTTPConnection
from threading import Thread, Lock as _Lock
from itertools import product
from urlparse import urlparse
from gzip import GzipFile

import json
import logging
import mapnik

from . import mvt, geojson

# earth's diameter in meters
diameter = 2 * pi * 6378137

# zoom of one-meter pixels
meter_zoom = _log(diameter) / _log(2) - 8

def utf8_keys(dictionary):
    ''' Convert dictionary keys to utf8-encoded strings for Mapnik.
    
        By default, json.load() returns dictionaries with unicode keys
        but Mapnik is ultra-whiny about these and rejects them.
    '''
    return dict([(key.encode('utf8'), val) for (key, val) in dictionary.items()])

def list_tiles(query):
    ''' Return a list of tiles (z, x, y) dicts for a mapnik Query object.
    
        Query is assumed to be in spherical mercator projection.
    '''
    # relative zoom from one-meter pixels to query pixels
    resolution = sum(query.resolution) / 2
    diff = _log(resolution) / _log(2)
    
    # calculated zoom level for this query
    zoom = round(meter_zoom + diff)
    
    scale = 2**zoom
    
    mincol = int(scale * (query.bbox.minx/diameter + .5))
    maxcol = int(scale * (query.bbox.maxx/diameter + .5))
    minrow = int(scale * (.5 - query.bbox.maxy/diameter))
    maxrow = int(scale * (.5 - query.bbox.miny/diameter))
    
    cols, rows = range(mincol, maxcol+1), range(minrow, maxrow+1)
    return [dict(z=zoom, x=col, y=row) for (col, row) in product(cols, rows)]

def load_features(jobs, host, port, path, tiles):
    ''' Load data from tiles to features.
    
        Calls load_tile_features() in a thread pool to speak HTTP.
    '''
    features = []
    lock = _Lock()
    
    args = (lock, host, port, path, tiles, features)
    threads = [Thread(target=load_tile_features, args=args) for i in range(jobs)]
    
    for thread in threads:
        thread.start()
    
    for thread in threads:
        thread.join()
    
    logging.debug('Loaded %d features' % len(features))
    return features

def load_tile_features(lock, host, port, path_fmt, tiles, features):
    ''' Load data from tiles to features.
    
        Called from load_features(), in a thread.
        
        Returns a list of (WKB, property dict) pairs.
    '''
    while True:
        try:
            tile = tiles.pop()
            
        except IndexError:
            # All done.
            break
        
        #
        # Request tile data from remote server.
        #
        conn = HTTPConnection(host, port)
        head = {'Accept-Encoding': 'gzip'}
        path = path_fmt % tile

        conn.request('GET', path, headers=head)
        resp = conn.getresponse()
        file = StringIO(resp.read())
        
        if resp.getheader('Content-Encoding') == 'gzip':
            file = GzipFile(fileobj=file, mode='r')

        #
        # Convert data to feature list, which
        # benchmarked slightly faster in a lock.
        #
        with lock:
            mime_type = resp.getheader('Content-Type')
            
            if mime_type in ('text/json', 'application/json'):
                file_features = geojson.decode(file)
            
            elif mime_type == 'application/octet-stream+mvt':
                file_features = mvt.decode(file)
            
            else:
                raise ValueError('Unknown MIME-Type "%s"' % mime_type)
                
            logging.debug('%d features in %s:%d%s' % (len(file_features), host, port, path))
            features.extend(file_features)

#
# Smaller numbers prioritize roads in front of other roads.
#
highway_priorities = {
    'motorway': 0, 'trunk': 1, 'primary': 2, 'secondary': 3, 'tertiary': 4,
    'motorway_link': 5, 'trunk_link': 5, 'primary_link': 5, 'secondary_link': 5, 'tertiary_link': 5,
    'residential': 6, 'unclassified': 6, 'road': 6,
    'unclassified': 7, 'service': 7, 'minor': 7
    }

def feature_sortkey((geom, props)):
    ''' Get highway layer (z-index) as an integer.
    '''
    # explicit layering mostly wins
    layer = props.get('explicit_layer', 0) * 1000
    
    # implicit layering less important.
    if props['is_bridge'] == 'yes':
        layer += 100
    
    if props['is_tunnel'] == 'yes':
        layer -= 100
    
    # leave the +/-10 order of magnitude open for bridge casings.
    
    # adjust slightly based on priority derived from highway type
    highway = props.get('highway', None)
    layer -= highway_priorities.get(highway, 9)
    
    return layer

class Datasource (mapnik.PythonDatasource):
    ''' Mapnik datasource to read tiled vector data in GeoJSON or MVT formats.

        Sample usage in Mapnik configuration XML:
        
        <Layer name="test" srs="+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +no_defs">
            <StyleName>...</StyleName>
            <Datasource>
                <Parameter name="type">python</Parameter>
                <Parameter name="factory">TileStache.Goodies.VecTiles:Datasource</Parameter>
                <Parameter name="template">http://example.com/{z}/{x}/{y}.mvt</Parameter>
            </Datasource>
        </Layer>
    '''
    def __init__(self, template):
        ''' Make a new Datasource.
        
            Parameters:
        
            template
                Required URL template with placeholders for tile zoom, x and y,
                e.g. "http://example.com/layer/{z}/{x}/{y}.json".
        '''
        scheme, host, path, p, query, f = urlparse(template)
        
        self.host = host
        self.port = 443 if scheme == 'https' else 80
        
        self.path = path + ('?' if query else '') + query
        self.path = self.path.replace('%', '%%')
        self.path = self.path.replace('{Z}', '{z}').replace('{z}', '%(z)d')
        self.path = self.path.replace('{X}', '{x}').replace('{x}', '%(x)d')
        self.path = self.path.replace('{Y}', '{y}').replace('{y}', '%(y)d')
        
        bbox = mapnik.Box2d(-diameter/2, -diameter/2, diameter/2, diameter/2)
        mapnik.PythonDatasource.__init__(self, envelope=bbox)

    def features(self, query):
        '''
        '''
        logging.debug('Rendering %s' % str(query.bbox))
        
        tiles = list_tiles(query)
        
        features = load_features(8, self.host, self.port, self.path, tiles)
        features = [(wkb, utf8_keys(props)) for (wkb, props) in features]
        features.sort(key=feature_sortkey)
        
        # build a set of shared keys
        props = zip(*features)[1]
        keys = [set(prop.keys()) for prop in props]
        keys = reduce(lambda a, b: a & b, keys)

        return mapnik.PythonDatasource.wkb_features(keys=keys, features=features)
