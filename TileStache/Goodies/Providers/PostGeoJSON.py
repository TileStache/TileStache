""" Provider that returns GeoJSON data responses from PostGIS queries.
"""

from psycopg2 import connect

from TileStache.Core import KnownUnknown

class Provider:

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
        pass
