from math import pi

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
    '''
    '''
    def __init__(self, layer):
        '''
        '''
        self.layer = layer
        self.db = connect(host='localhost', user='gis', password='gis', database='gis').cursor(cursor_factory=RealDictCursor)
        
    def renderTile(self, width, height, srs, coord):
        '''
        '''
        ll = self.layer.projection.coordinateProj(coord.down())
        ur = self.layer.projection.coordinateProj(coord.right())

        bbox = 'MakeBox2D(MakePoint(%.2f, %.2f), MakePoint(%.2f, %.2f))' % (ll.x, ll.y, ur.x, ur.y)
        query = 'SELECT way AS geometry, highway, name FROM planet_osm_line'
        tolerance = tolerances[coord.zoom]
        
        return Response(self.db, query, bbox, tolerance)

    def getTypeByExtension(self, extension):
        '''
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
    def __init__(self, db, query, bbox, tolerance):
        '''
        '''
        self.db = db
        
        self.query = {
            'JSON': build_query(query, bbox, tolerance, True),
            'MVT': build_query(query, bbox, tolerance, False)
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

def build_query(query, bbox, tolerance, geo):
    '''
    '''
    bbox = 'SetSRID(%s, 900913)' % bbox

    geom = 'Intersection(Simplify(q.geometry, %(tolerance).2f), %(bbox)s)' % locals()
    
    if geo:
        geom = 'Transform(%s, 4326)' % geom
    
    return '''SELECT q.*,
                     AsBinary(%(geom)s) AS geometry
              FROM (%(query)s) AS q
              WHERE q.geometry && %(bbox)s
                AND Intersects(q.geometry, %(bbox)s)''' \
            % locals()
