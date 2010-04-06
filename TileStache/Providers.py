import mapnik
import PIL.Image

class Mapnik:

    def __init__(self, layer, mapfile):
        self.layer = layer
        self.mapfile = str(mapfile)
        self.mapnik = None

    def renderEnvelope(self, width, height, srs, xmin, ymin, xmax, ymax):
        """
        """
        if self.mapnik is None:
            self.mapnik = mapnik.Map(0, 0)
            mapnik.load_map(self.mapnik, self.mapfile)
        
        self.mapnik.width = width
        self.mapnik.height = height
        self.mapnik.zoom_to_box(mapnik.Envelope(xmin, ymin, xmax, ymax))
        
        img = mapnik.Image(width, height)
        mapnik.render(self.mapnik, img)
        
        img = PIL.Image.fromstring('RGBA', (width, height), img.tostring())
        
        return img

def getProviderByName(name):
    """ Retrieve a provider object by name.
    
        Raise an exception if the name doesn't work out.
    """
    if name == 'mapnik':
        return Mapnik

    raise Exception('Unknown provider name: "%s"' % name)

def loadProviderByClass(classpath):
    """
    """
    classpath = classpath.split('.')
    module = __import__( '.'.join(classpath[:-1]) )
    _class = getattr(module, classpath[-1])
    
    return _class
