from TileStache.Core import KnownUnknown

def coordinate_api_url(coord, projection):
    """
    """
    ul = projection.coordinateLocation(coord)
    ur = projection.coordinateLocation(coord.right())
    ll = projection.coordinateLocation(coord.down())
    lr = projection.coordinateLocation(coord.down().right())
    
    n = max(ul.lat, ur.lat, ll.lat, lr.lat)
    s = min(ul.lat, ur.lat, ll.lat, lr.lat)
    e = max(ul.lon, ur.lon, ll.lon, lr.lon)
    w = min(ul.lon, ur.lon, ll.lon, lr.lon)
    
    url = 'http://api.openstreetmap.org/api/0.6/map?bbox=%(w).6f,%(s).6f,%(e).6f,%(n).6f' % locals()
    
    return url

class SaveableResponse:
    """ Wrapper class for JSON response that makes it behave like a PIL.Image object.
    
        TileStache.getTile() expects to be able to save one of these to a buffer.
    """
    def __init__(self, content):
        self.content = content
        
    def save(self, out, format):
        if format != 'XML':
            raise KnownUnknown('MirrorOSM only saves .xml tiles, not "%s"' % format)

        out.write(self.content)

class Provider:
    """
    """
    
    def __init__(self, layer):
        """
        """
        self.layer = layer

    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.
        
            This only accepts "xml".
        """
        if extension.lower() != 'xml':
            raise KnownUnknown('MirrorOSM only makes .xml tiles, not "%s"' % extension)
    
        return 'text/xml', 'XML'

    def renderTile(self, width, height, srs, coord):
        """ Render a single tile, return a SaveableResponse instance.
        """
        url = coordinate_api_url(coord, self.layer.projection)
        
        return SaveableResponse(url + "\n")
