''' Datasource for Mapnik that consumes vector tiles in GeoJSON or MVT format.

VecTiles provides Mapnik with a Datasource that can read remote tiles of vector
data in spherical mercator projection, providing for rendering of data without
the use of a local PostGIS database.

Sample usage in Mapnik configuration XML:
    
 <Layer name="test" srs="+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +no_defs">
     <StyleName>...</StyleName>
     <Datasource>
         <Parameter name="type">python</Parameter>
         <Parameter name="factory">TileStache.Goodies.VecTiles:Datasource</Parameter>
         <Parameter name="template">http://example.com/{z}/{x}/{y}.mvt</Parameter>
         <Parameter name="sort_key">sort_key ascending</Parameter>
     </Datasource>
 </Layer>

From http://github.com/mapnik/mapnik/wiki/Python-Plugin:

  The Mapnik Python plugin allows you to write data sources in the Python
  programming language. This is useful if you want to rapidly prototype a
  plugin, perform some custom manipulation on data or if you want to bind
  mapnik to a datasource which is most conveniently accessed through Python.

  The plugin may be used from the existing mapnik Python bindings or it can
  embed the Python interpreter directly allowing it to be used from C++, XML
  or even JavaScript.

See also:
    http://mapnik.org/docs/v2.1.0/api/python/mapnik.PythonDatasource-class.html
'''
from math import pi, log as _log
from threading import Thread, Lock as _Lock
try:
    from http.client import HTTPConnection
except ImportError:
    # Python 2
    from httplib import HTTPConnection
from itertools import product
try:
    from io import StringIO
except ImportError:
    # Python 2
    from StringIO import StringIO
try:
    from urllib.parse import urlparse
except ImportError:
    # Python 2
    from urlparse import urlparse
from gzip import GzipFile

import logging

from . import mvt, geojson

try:
    from mapnik import PythonDatasource, Box2d
except ImportError:
    # can still build documentation
    PythonDatasource = object

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

def list_tiles(query, zoom_adjust):
    ''' Return a list of tiles (z, x, y) dicts for a mapnik Query object.
    
        Query is assumed to be in spherical mercator projection.
        Zoom_adjust is an integer delta to subtract from the calculated zoom.
    '''
    # relative zoom from one-meter pixels to query pixels
    resolution = sum(query.resolution) / 2
    diff = _log(resolution) / _log(2) - zoom_adjust
    
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
                logging.error('Unknown MIME-Type "%s" from %s:%d%s' % (mime_type, host, port, path))
                return
                
            logging.debug('%d features in %s:%d%s' % (len(file_features), host, port, path))
            features.extend(file_features)

class Datasource (PythonDatasource):
    ''' Mapnik datasource to read tiled vector data in GeoJSON or MVT formats.

        Sample usage in Mapnik configuration XML:
        
        <Layer name="test" srs="+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +no_defs">
            <StyleName>...</StyleName>
            <Datasource>
                <Parameter name="type">python</Parameter>
                <Parameter name="factory">TileStache.Goodies.VecTiles:Datasource</Parameter>
                <Parameter name="template">http://example.com/{z}/{x}/{y}.mvt</Parameter>
                <Parameter name="sort_key">sort_key ascending</Parameter>
            </Datasource>
        </Layer>
    '''
    def __init__(self, template, sort_key=None, clipped='true', zoom_data='single'):
        ''' Make a new Datasource.
        
            Parameters:
        
              template:
                Required URL template with placeholders for tile zoom, x and y,
                e.g. "http://example.com/layer/{z}/{x}/{y}.json".
        
              sort_key:
                Optional field name to use when sorting features for rendering.
                E.g. "name" or "name ascending" to sort ascending by name,
                "name descending" to sort descending by name.
              
              clipped:
                Optional boolean flag to determine correct behavior for
                duplicate geometries. When tile data is not clipped, features()
                will check geometry uniqueness and throw out duplicates.

                Setting clipped to false for actually-clipped geometries has no
                effect but wastes time. Setting clipped to false for unclipped
                geometries will result in possibly wrong-looking output.

                Default is "true".
              
              zoom_data:
                Optional keyword specifying single or double zoom data tiles.
                Works especially well with relatively sparse label layers.
                
                When set to "double", tiles will be requested at one zoom level
                out from the map view, e.g. double-sized z13 tiles will be used
                to render a normal z14 map.

                Default is "single".
        '''
        scheme, host, path, p, query, f = urlparse(template)
        
        self.host = host
        self.port = 443 if scheme == 'https' else 80
        
        if ':' in host:
            self.host = host.split(':', 1)[0]
            self.port = int(host.split(':', 1)[1])
        
        self.path = path + ('?' if query else '') + query
        self.path = self.path.replace('%', '%%')
        self.path = self.path.replace('{Z}', '{z}').replace('{z}', '%(z)d')
        self.path = self.path.replace('{X}', '{x}').replace('{x}', '%(x)d')
        self.path = self.path.replace('{Y}', '{y}').replace('{y}', '%(y)d')
        
        if sort_key is None:
            self.sort, self.reverse = None, None
        
        elif sort_key.lower().endswith(' descending'):
            logging.debug('Will sort by %s descending' % sort_key)
            self.sort, self.reverse = sort_key.split()[0], True
        
        else:
            logging.debug('Will sort by %s ascending' % sort_key)
            self.sort, self.reverse = sort_key.split()[0], False
        
        self.clipped = clipped.lower() not in ('false', 'no', '0')
        self.zoom_adjust = {'double': 1}.get(zoom_data.lower(), 0)
        
        bbox = Box2d(-diameter/2, -diameter/2, diameter/2, diameter/2)
        PythonDatasource.__init__(self, envelope=bbox)

    def features(self, query):
        '''
        '''
        logging.debug('Rendering %s' % str(query.bbox))
        
        tiles = list_tiles(query, self.zoom_adjust)
        features = []
        seen = set()
        
        for (wkb, props) in load_features(8, self.host, self.port, self.path, tiles):
            if not self.clipped:
                # not clipped means get rid of inevitable dupes
                key = (wkb, tuple(sorted(props.items())))
                
                if key in seen:
                    continue

                seen.add(key)
            
            features.append((wkb, utf8_keys(props)))
            
        if self.sort:
            logging.debug('Sorting by %s %s' % (self.sort, 'descending' if self.reverse else 'ascending'))
            key_func = lambda wkb_props: wkb_props[1].get(self.sort, None)
            features.sort(reverse=self.reverse, key=key_func)
        
        if len(features) == 0:
            return PythonDatasource.wkb_features(keys=[], features=[])
        
        # build a set of shared keys
        props = zip(*features)[1]
        keys = [set(prop.keys()) for prop in props]
        keys = reduce(lambda a, b: a & b, keys)

        return PythonDatasource.wkb_features(keys=keys, features=features)
