""" Provider that returns GeoJSON data responses from PostGIS queries.
"""

from json import dump
from psycopg2 import connect
from TileStache.Core import KnownUnknown

class SaveableResponse:
    """ Wrapper class for JSON response that makes it behave like a PIL.Image object.
    
        TileStache.handleRequest() expects to be able to save one of these to a buffer.
    """
    def __init__(self, content):
        self.content = content

    def save(self, fp, format):
        if format != 'JSON':
            raise KnownUnknown('PostGeoJSON only makes .json tiles, not "%s"' % extension)

        dump(self.content, fp)

class Provider:
    """
    """
    def __init__(self, layer, dsn):
        self.layer = layer
        conn = connect('dbname=geodata user=postgres')

    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.
        """
        if extension.lower() != 'json':
            raise KnownUnknown('PostGeoJSON only makes .json tiles, not "%s"' % extension)
    
        return 'text/json', 'JSON'

    def renderTile(self, width, height, srs, coord):
        return SaveableResponse({'hello': 'world'})
