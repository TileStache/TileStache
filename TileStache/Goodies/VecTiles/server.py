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
        
          dbinfo:
            Required dictionary of Postgres connection parameters. Should
            include some combination of 'host', 'user', 'password', and 'database'.
        
          queries:
            Required list of Postgres queries, one for each zoom level. The
            last query in the list is repeated for higher zoom levels, and null
            queries indicate an empty response.
            
            Query must use "__geometry__" for a column name, and must be in
            spherical mercator (900913) projection. A query may include an
            "__id__" column, which will be used as a feature ID in GeoJSON
            instead of a dynamically-generated hash of the geometry. A query
            can additionally be a file name or URL, interpreted relative to
            the location of the TileStache config file.
            
            If the query contains the token "!bbox!", it will be replaced with
            a constant bounding box geomtry like this:
            "ST_SetSRID(ST_MakeBox2D(ST_MakePoint(x, y), ST_MakePoint(x, y)), <srid>)"
            
            This behavior is modeled on Mapnik's similar bbox token feature:
            https://github.com/mapnik/mapnik/wiki/PostGIS#bbox-token
          
          clip:
            Optional boolean flag determines whether geometries are clipped to
            tile boundaries or returned in full. Default true: clip geometries.
        
          srid:
            Optional numeric SRID used by PostGIS for spherical mercator.
            Default 900913.
        
          simplify:
            Optional floating point number of pixels to simplify all geometries.
            Useful for creating double resolution (retina) tiles set to 0.5, or
            set to 0.0 to prevent any simplification. Default 1.0.
        
          simplify_until:
            Optional integer specifying a zoom level where no more geometry
            simplification should occur. Default 16.
        
        Sample configuration, for a layer with no results at zooms 0-9, basic
        selection of lines with names and highway tags for zoom 10, a remote
        URL containing a query for zoom 11, and a local file for zooms 12+:
        
          "provider":
          {
            "class": "TileStache.Goodies.VecTiles:Provider",
            "kwargs":
            {
              "dbinfo":
              {
                "host": "localhost",
                "user": "gis",
                "password": "gis",
                "database": "gis"
              },
              "queries":
              [
                null, null, null, null, null,
                null, null, null, null, null,
                "SELECT way AS __geometry__, highway, name FROM planet_osm_line -- zoom 10+ ",
                "http://example.com/query-z11.pgsql",
                "query-z12-plus.pgsql"
              ]
            }
          }
    '''
    def __init__(self, layer, dbinfo, queries, clip=True, srid=900913, simplify=1.0, simplify_until=16):
        '''
        '''
        self.layer = layer
        
        keys = 'host', 'user', 'password', 'database', 'port', 'dbname'
        self.dbinfo = dict([(k, v) for (k, v) in dbinfo.items() if k in keys])

        self.clip = bool(clip)
        self.srid = int(srid)
        self.simplify = float(simplify)
        self.simplify_until = int(simplify_until)
        
        self.queries = []
        self.columns = {}
        
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
        
        if query not in self.columns:
            self.columns[query] = query_columns(self.dbinfo, self.srid, query)
        
        ll = self.layer.projection.coordinateProj(coord.down())
        ur = self.layer.projection.coordinateProj(coord.right())
        bbox = 'ST_MakeBox2D(ST_MakePoint(%.2f, %.2f), ST_MakePoint(%.2f, %.2f))' % (ll.x, ll.y, ur.x, ur.y)
        
        tolerance = self.simplify * tolerances[coord.zoom] if coord.zoom < self.simplify_until else None
        
        return Response(self.dbinfo, self.srid, query, self.columns[query], bbox, tolerance, self.clip)

    def getTypeByExtension(self, extension):
        ''' Get mime-type and format by file extension, one of "mvt" or "json".
        '''
        if extension.lower() == 'mvt':
            return 'application/octet-stream+mvt', 'MVT'
        
        elif extension.lower() == 'json':
            return 'text/json', 'JSON'
        
        else:
            raise ValueError(extension)

class Connection:
    ''' Context manager for Postgres connections.
    
        See http://www.python.org/dev/peps/pep-0343/
        and http://effbot.org/zone/python-with-statement.htm
    '''
    def __init__(self, dbinfo):
        self.dbinfo = dbinfo
    
    def __enter__(self):
        self.db = connect(**self.dbinfo).cursor(cursor_factory=RealDictCursor)
        return self.db
    
    def __exit__(self, type, value, traceback):
        self.db.connection.close()

class Response:
    '''
    '''
    def __init__(self, dbinfo, srid, subquery, columns, bbox, tolerance, clip):
        '''
        '''
        self.dbinfo = dbinfo
        
        self.query = {
            'JSON': build_query(srid, subquery, columns, bbox, tolerance, True, clip),
            'MVT': build_query(srid, subquery, columns, bbox, tolerance, False, clip)
            }
    
    def save(self, out, format):
        '''
        '''
        with Connection(self.dbinfo) as db:
            db.execute(self.query[format])
            
            features = []
            
            for row in db.fetchall():
                if row['__geometry__'] is None:
                    continue
            
                wkb = bytes(row['__geometry__'])
                prop = dict([(k, v) for (k, v) in row.items()
                             if k not in ('__geometry__', '__id__')])
                
                if '__id__' in row:
                    features.append((wkb, prop, row['__id__']))
                
                else:
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

def query_columns(dbinfo, srid, subquery):
    ''' Get information about the columns returned for a subquery.
    '''
    #
    # Bounding box for columns is the whole world.
    #
    bbox = -20037507.58, -20037506.44, 20037507.76, 20037504.73
    bbox = 'ST_MakeBox2D(ST_MakePoint(%f, %f), ST_MakePoint(%f, %f))' % bbox
    bbox = 'ST_SetSRID(%s, %d)' % (bbox, srid)

    subquery = subquery.replace('!bbox!', bbox)
    
    with Connection(dbinfo) as db:
        db.execute(subquery + ' LIMIT 1')
        columns = set(db.fetchone().keys())
    
    return columns

def build_query(srid, subquery, subcolumns, bbox, tolerance, is_geo, is_clipped):
    ''' Build and return an PostGIS query.
    '''
    bbox = 'ST_SetSRID(%s, %d)' % (bbox, srid)
    geom = 'q.__geometry__'
    
    if tolerance is not None:
        geom = 'ST_Simplify(%s, %.2f)' % (geom, tolerance)
    
    if is_clipped:
        geom = 'ST_Intersection(%s, %s)' % (geom, bbox)
    
    if is_geo:
        geom = 'ST_Transform(%s, 4326)' % geom
    
    subquery = subquery.replace('!bbox!', bbox)
    columns = ['q."%s"' % c for c in subcolumns if c not in ('__geometry__', )]
    
    if '__geometry__' not in subcolumns:
        raise Exception("There's supposed to be a __geometry__ column.")
    
    if '__id__' not in subcolumns:
        columns.append('Substr(MD5(ST_AsBinary(q.__geometry__)), 1, 10) AS __id__')
    
    columns = ', '.join(columns)
    
    return '''SELECT %(columns)s,
                     ST_AsBinary(%(geom)s) AS __geometry__
              FROM (
                %(subquery)s
                ) AS q
              WHERE ST_IsValid(q.__geometry__)
                AND q.__geometry__ && %(bbox)s
                AND ST_Intersects(q.__geometry__, %(bbox)s)''' \
            % locals()
