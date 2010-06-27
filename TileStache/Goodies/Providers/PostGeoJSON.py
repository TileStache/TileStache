""" Provider that returns GeoJSON data responses from PostGIS queries.
"""

from re import compile
from json import JSONEncoder

from psycopg2 import connect as _connect
from psycopg2.extras import RealDictCursor
from TileStache.Core import KnownUnknown
from TileStache.Geography import getProjectionByName

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
    def __init__(self, layer, dsn, query):
        self.layer = layer
        self.dbdsn = dsn
        self.query = query
        self.projection = getProjectionByName('spherical mercator')

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
        
        query = self.query.replace('!bbox!', bbox)
        
        db.execute(query)
        
        res = db.fetchone()
        
        db.close()
    
        return SaveableResponse({'w': width, 'h': height, 's': srs,
                                 'ul': str(coord), 'lr': str(coord.down().right()),
                                 'bbox': bbox,
                                 'query': query,
                                 'res': res})
