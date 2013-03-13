''' Provider that returns PostGIS vector tiles in GeoJSON or MVT format.

VecTiles is intended for rendering, and returns tiles with contents simplified,
precision reduced and often clipped. The MVT format in particular is designed
for use in Mapnik with the VecTiles Datasource, which can read binary MVT tiles.

For a more general implementation, try the Vector provider:
    http://tilestache.org/doc/#vector-provider
'''
from math import pi
from urlparse import urljoin, urlparse
from urllib import urlopen
from os.path import exists

try:
    from psycopg2.extras import RealDictCursor
    from psycopg2 import connect

except ImportError, err:
    # Still possible to build the documentation without psycopg2

    def connect(*args, **kwargs):
        raise err

from . import mvt, geojson

tolerances = [6378137 * 2 * pi / (2 ** (zoom + 8)) for zoom in range(20)]
    
class Provider:
    ''' VecTiles provider for PostGIS data sources.
    
        Parameters:
        
          queries:
            List of Postgres queries, one for each zoom level. The last query
            in the list is repeated for higher zoom levels, and null queries
            indicate an empty response. Query must use "geometry" for a column
            name, and must be in spherical mercator (900913) projection.
            A query can additionally be a file name or URL, interpreted
            relative to the location of the TileStache config file.
        
        Sample configuration, for a layer with no results at zooms 0-9, basic
        selection of lines with names and highway tags for zoom 10, a remote
        URL containing a query for zoom 11, and a local file for zooms 12+:
        
          "provider":
          {
            "class": "TileStache.Goodies.VecTiles:Provider",
            "kwargs":
            {
              "queries":
              [
                null, null, null, null, null,
                null, null, null, null, null,
                "SELECT way AS geometry, highway, name FROM planet_osm_line -- zoom 10+ ",
                "http://example.com/query-z11.pgsql",
                "query-z12-plus.pgsql"
              ]
            }
          }
    '''
    def __init__(self, layer, queries):
        '''
        '''
        self.layer = layer
        self.db = connect(host='localhost', user='gis', password='gis', database='gis').cursor(cursor_factory=RealDictCursor)
        
        self.queries = []
        
        for query in queries:
            if query is None:
                self.queries.append(None)
                continue
        
            #
            # might be a file or URL?
            #
            url = urljoin(layer.config.dirpath, query)
            scheme, h, path, p, q, f = urlparse(url)
            
            if scheme in ('file', '') and exists(path):
                query = open(path).read()
            
            elif scheme == 'http' and ' ' not in url:
                query = urlopen(url).read()
        
            self.queries.append(query)
        
    def renderTile(self, width, height, srs, coord):
        ''' Render a single tile, return a Response instance.
        '''
        try:
            query = self.queries[coord.zoom]
        except IndexError:
            query = self.queries[-1]

        if not query:
            return EmptyResponse()
        
        ll = self.layer.projection.coordinateProj(coord.down())
        ur = self.layer.projection.coordinateProj(coord.right())
        bbox = 'MakeBox2D(MakePoint(%.2f, %.2f), MakePoint(%.2f, %.2f))' % (ll.x, ll.y, ur.x, ur.y)
        
        return Response(self.db, query, bbox, tolerances[coord.zoom])

    def getTypeByExtension(self, extension):
        ''' Get mime-type and format by file extension, one of "mvt" or "json".
        '''
        if extension.lower() == 'mvt':
            return 'application/octet-stream+mvt', 'MVT'
        
        elif extension.lower() == 'json':
            return 'text/json', 'JSON'
        
        else:
            raise ValueError(extension)

class Response:
    '''
    '''
    def __init__(self, db, subquery, bbox, tolerance):
        '''
        '''
        self.db = db
        
        self.query = {
            'JSON': build_query(subquery, bbox, tolerance, is_geo=True),
            'MVT': build_query(subquery, bbox, tolerance)
            }
    
    def save(self, out, format):
        '''
        '''
        self.db.execute(self.query[format])
        
        features = []
        
        for row in self.db.fetchall():
            wkb = bytes(row['geometry'])
            prop = dict([(k, v) for (k, v) in row.items() if k != 'geometry'])
            
            features.append((wkb, prop))

        if format == 'MVT':
            mvt.encode(out, features)
        
        elif format == 'JSON':
            geojson.encode(out, features)
        
        else:
            raise ValueError(format)

class EmptyResponse:
    ''' Simple empty response renders valid MVT or GeoJSON with no features.
    '''
    def save(self, out, format):
        '''
        '''
        if format == 'MVT':
            mvt.encode(out, [])
        
        elif format == 'JSON':
            geojson.encode(out, [])
        
        else:
            raise ValueError(format)

def build_query(subquery, bbox, tolerance, is_geo=False, is_clipped=True):
    ''' Build and return an PostGIS query.
    '''
    bbox = 'SetSRID(%s, 900913)' % bbox
    geom = 'Simplify(q.geometry, %.2f)' % tolerance
    
    if is_clipped:
        geom = 'Intersection(%s, %s)' % (geom, bbox)
    
    if is_geo:
        geom = 'Transform(%s, 4326)' % geom
    
    return '''SELECT q.*,
                     AsBinary(%(geom)s) AS geometry
              FROM (
                %(subquery)s
                ) AS q
              WHERE q.geometry && %(bbox)s
                AND Intersects(q.geometry, %(bbox)s)''' \
            % locals()
