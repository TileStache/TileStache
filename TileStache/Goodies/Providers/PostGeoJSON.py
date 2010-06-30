""" Provider that returns GeoJSON data responses from PostGIS queries.
"""

from re import compile
from json import JSONEncoder
from copy import copy as _copy
from binascii import unhexlify as _unhexlify

from shapely.wkb import loads as _loadshape
from psycopg2 import connect as _connect
from psycopg2.extras import RealDictCursor
from TileStache.Core import KnownUnknown
from TileStache.Geography import getProjectionByName

def row2feature(row, id_field, geometry_field):
    """ Convert a database row dict to a feature dict.
    """
    feature = {'type': 'Feature', 'properties': _copy(row)}

    geometry = feature['properties'].pop(geometry_field)
    feature['geometry'] = _loadshape(_unhexlify(geometry))
    feature['id'] = feature['properties'].pop(id_field)
    
    return feature

def _p2p(xy, projection):
    """ Convert a simple (x, y) coordinate to a (lon, lat) position.
    """
    loc = projection.projLocation(_Point(*xy))
    return loc.lon, loc.lat

def shape2geometry(shape, projection):
    """ Convert a Shapely geometry object to a GeoJSON-suitable geometry dict.
    """
    if str(shape).startswith('POINT '):
        type = 'Point'
        coords = _p2p(shape.coords[0], projection)

    elif str(shape).startswith('LINESTRING '):
        type = 'LineString'
        coords = [_p2p(xy, projection) for xy in shape.coords]

    elif str(shape).startswith('POLYGON '):
        type = 'Polygon'
        rings = [shape.exterior] + list(shape.interiors)
        coords = [[_p2p(xy, projection) for xy in ring.coords] for ring in rings]

    else:
        return None

    return {'type': type, 'coordinates': coords}

class _Point:
    """ Local duck for (x, y) points.
    """
    def __init__(self, x, y):
        self.x = x
        self.y = y

class SaveableResponse:
    """ Wrapper class for JSON response that makes it behave like a PIL.Image object.
    
        TileStache.handleRequest() expects to be able to save one of these to a buffer.
    """
    def __init__(self, content):
        self.content = content

    def save(self, out, format):
        if format != 'JSON':
            raise KnownUnknown('PostGeoJSON only saves .json tiles, not "%s"' % format)
        
        encoded = JSONEncoder(indent=2).iterencode(self.content)
        float_pat = compile(r'^-?\d+\.\d+$')
        
        for atom in encoded:
            if float_pat.match(atom):
                out.write('%.6f' % float(atom))
            else:
                out.write(atom)

class Provider:
    """
    """
    def __init__(self, layer, dsn, query, id_column='id', geometry_column='geometry'):
        self.layer = layer
        self.dbdsn = dsn
        self.query = query
        self.projection = getProjectionByName('spherical mercator')
        self.geometry_field = geometry_column
        self.id_field = id_column

    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.
        """
        if extension.lower() != 'json':
            raise KnownUnknown('PostGeoJSON only makes .json tiles, not "%s"' % extension)
    
        return 'text/json', 'JSON'

    def renderTile(self, width, height, srs, coord):
        ul = self.projection.coordinateProj(coord)
        lr = self.projection.coordinateProj(coord.right().down())
        
        bbox = 'ST_SetSRID(ST_MakeBox2D(ST_MakePoint(%.6f, %.6f), ST_MakePoint(%.6f, %.6f)), 900913)' % (ul.x, ul.y, lr.x, lr.y)

        db = _connect(self.dbdsn).cursor(cursor_factory=RealDictCursor)

        db.execute(self.query.replace('!bbox!', bbox))
        rows = db.fetchall()
        
        db.close()
        
        response = {'type': 'FeatureCollection', 'features': []}
        
        for row in rows:
            feature = row2feature(row, self.id_field, self.geometry_field)
            feature['geometry'] = shape2geometry(feature['geometry'], self.projection)
            response['features'].append(feature)
    
        return SaveableResponse(response)
