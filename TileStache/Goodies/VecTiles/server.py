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

from . import mvt, geojson, topojson
from ...Geography import SphericalMercator
from ModestMaps.Core import Point

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

        The queries field has an alternate dictionary-like syntax which maps
        zoom levels to their associated query.  Zoom levels for which there is
        no query may be omitted and are assumed null.  This is equivalent to
        the queries defined above:

              "queries": {
                "10": "SELECT way AS __geometry__, highway, name FROM planet_osm_line -- zoom 10+ ",
                "11": "http://example.com/query-z11.pgsql",
                "12": "query-z12-plus.pgsql"
              }

        Note that JSON requires keys to be strings, therefore the zoom levels
        must be enclosed in quotes.
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
        
        self.columns = {}

        # Each type creates an iterator yielding tuples of:
        # (zoom level (int), query (string))
        if isinstance(queries, dict):
            # Add 1 to include space for zoom level 0
            n_zooms = max(int(z) for z in queries) + 1
            queryiter = ((int(z), q) for z, q in queries.iteritems())
        else:  # specified as array
            n_zooms = len(queries)
            queryiter = enumerate(queries)

        # For the dict case, unspecified zoom levels are assumed to be null.
        self.queries = [None] * n_zooms
        for z, query in queryiter:
            if query is None:
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
        
            self.queries[z] = query
        
    def renderTile(self, width, height, srs, coord):
        ''' Render a single tile, return a Response instance.
        '''
        try:
            query = self.queries[coord.zoom]
        except IndexError:
            query = self.queries[-1]

        ll = self.layer.projection.coordinateProj(coord.down())
        ur = self.layer.projection.coordinateProj(coord.right())
        bounds = ll.x, ll.y, ur.x, ur.y
        
        if not query:
            return EmptyResponse(bounds)
        
        if query not in self.columns:
            self.columns[query] = query_columns(self.dbinfo, self.srid, query, bounds)
        
        tolerance = self.simplify * tolerances[coord.zoom] if coord.zoom < self.simplify_until else None
        
        return Response(self.dbinfo, self.srid, query, self.columns[query], bounds, tolerance, coord.zoom, self.clip)

    def getTypeByExtension(self, extension):
        ''' Get mime-type and format by file extension, one of "mvt", "json" or "topojson".
        '''
        if extension.lower() == 'mvt':
            return 'application/octet-stream+mvt', 'MVT'
        
        elif extension.lower() == 'json':
            return 'application/json', 'JSON'
        
        elif extension.lower() == 'topojson':
            return 'application/json', 'TopoJSON'
        
        else:
            raise ValueError(extension)

class MultiProvider:
    ''' VecTiles provider to gather PostGIS tiles into a single multi-response.
        
        Returns a MultiResponse object for GeoJSON or TopoJSON requests.
    
        names:
          List of names of vector-generating layers from elsewhere in config.
        
        Sample configuration, for a layer with combined data from water
        and land areas, both assumed to be vector-returning layers:
        
          "provider":
          {
            "class": "TileStache.Goodies.VecTiles:MultiProvider",
            "kwargs":
            {
              "names": ["water-areas", "land-areas"]
            }
          }
    '''
    def __init__(self, layer, names):
        self.layer = layer
        self.names = names
        
    def renderTile(self, width, height, srs, coord):
        ''' Render a single tile, return a Response instance.
        '''
        return MultiResponse(self.layer.config, self.names, coord)

    def getTypeByExtension(self, extension):
        ''' Get mime-type and format by file extension, "json" or "topojson" only.
        '''
        if extension.lower() == 'json':
            return 'application/json', 'JSON'
        
        elif extension.lower() == 'topojson':
            return 'application/json', 'TopoJSON'
        
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
    def __init__(self, dbinfo, srid, subquery, columns, bounds, tolerance, zoom, clip):
        ''' Create a new response object with Postgres connection info and a query.
        
            bounds argument is a 4-tuple with (xmin, ymin, xmax, ymax).
        '''
        self.dbinfo = dbinfo
        self.bounds = bounds
        self.zoom = zoom
        self.clip = clip
        
        bbox = 'ST_MakeBox2D(ST_MakePoint(%.2f, %.2f), ST_MakePoint(%.2f, %.2f))' % bounds
        geo_query = build_query(srid, subquery, columns, bbox, tolerance, True, clip)
        merc_query = build_query(srid, subquery, columns, bbox, tolerance, False, clip)
        self.query = dict(TopoJSON=geo_query, JSON=geo_query, MVT=merc_query)
    
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
            geojson.encode(out, features, self.zoom, self.clip)
        
        elif format == 'TopoJSON':
            ll = SphericalMercator().projLocation(Point(*self.bounds[0:2]))
            ur = SphericalMercator().projLocation(Point(*self.bounds[2:4]))
            topojson.encode(out, features, (ll.lon, ll.lat, ur.lon, ur.lat), self.clip)
        
        else:
            raise ValueError(format)

class EmptyResponse:
    ''' Simple empty response renders valid MVT or GeoJSON with no features.
    '''
    def __init__(self, bounds):
        self.bounds = bounds
    
    def save(self, out, format):
        '''
        '''
        if format == 'MVT':
            mvt.encode(out, [])
        
        elif format == 'JSON':
            geojson.encode(out, [], 0, False)
        
        elif format == 'TopoJSON':
            ll = SphericalMercator().projLocation(Point(*self.bounds[0:2]))
            ur = SphericalMercator().projLocation(Point(*self.bounds[2:4]))
            topojson.encode(out, [], (ll.lon, ll.lat, ur.lon, ur.lat), False)
        
        else:
            raise ValueError(format)

class MultiResponse:
    '''
    '''
    def __init__(self, config, names, coord):
        ''' Create a new response object with TileStache config and layer names.
        '''
        self.config = config
        self.names = names
        self.coord = coord
    
    def save(self, out, format):
        '''
        '''
        if format == 'TopoJSON':
            topojson.merge(out, self.names, self.config, self.coord)
        
        elif format == 'JSON':
            geojson.merge(out, self.names, self.config, self.coord)
        
        else:
            raise ValueError(format)

def query_columns(dbinfo, srid, subquery, bounds):
    ''' Get information about the columns returned for a subquery.
    '''
    with Connection(dbinfo) as db:
        #
        # While bounds covers less than the full planet, look for just one feature.
        #
        while (abs(bounds[2] - bounds[0]) * abs(bounds[2] - bounds[0])) < 1.61e15:
            bbox = 'ST_MakeBox2D(ST_MakePoint(%f, %f), ST_MakePoint(%f, %f))' % bounds
            bbox = 'ST_SetSRID(%s, %d)' % (bbox, srid)
        
            query = subquery.replace('!bbox!', bbox)
        
            db.execute(query + '\n LIMIT 1') # newline is important here, to break out of comments.
            row = db.fetchone()
            
            if row is None:
                #
                # Try zooming out three levels (8x) to look for features.
                #
                bounds = (bounds[0] - (bounds[2] - bounds[0]) * 3.5,
                          bounds[1] - (bounds[3] - bounds[1]) * 3.5,
                          bounds[2] + (bounds[2] - bounds[0]) * 3.5,
                          bounds[3] + (bounds[3] - bounds[1]) * 3.5)
                
                continue
            
            column_names = set(row.keys())
            return column_names
        
def build_query(srid, subquery, subcolumns, bbox, tolerance, is_geo, is_clipped):
    ''' Build and return an PostGIS query.
    '''
    bbox = 'ST_SetSRID(%s, %d)' % (bbox, srid)
    geom = 'q.__geometry__'
    
    if is_clipped:
        geom = 'ST_Intersection(%s, %s)' % (geom, bbox)
    
    if tolerance is not None:
        geom = 'ST_SimplifyPreserveTopology(%s, %.2f)' % (geom, tolerance)
    
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
