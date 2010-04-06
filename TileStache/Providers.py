""" The provider bits of TileStache.

A Provider is the part of TileStache that actually renders imagery. A few default
providers are found here, but it's possible to define your own and pull them into
TileStache dynamically by class name.

Built-in providers:
- mapnik

Example built-in provider, for JSON configuration file:

    "layer-name": {
        "provider": {"name": "mapnik", "mapfile": "style.xml"},
        ...
    }

Example external provider, for JSON configuration file:

    "layer-name": {
        "provider": {"class": "Module.Classname", "kwargs": {"frob": "yes"}},
        ...
    }

- The "class" value is split up into module and classname, and dynamically
  included. If this doesn't work for some reason, TileStache will fail loudly
  to let you know.
- The "kwargs" value is fed to the class constructor as a dictionary of keyword
  args. If your defined class doesn't accept any of these keyword arguments,
  TileStache will throw an exception.

The only method that a provider currently needs to implement is renderEnvelope(),
with the following seven arguments:

- width, height: in pixels
- srs: projection as Proj4 string.
  "+proj=longlat +ellps=WGS84 +datum=WGS84" is an example, 
  see http://spatialreference.org for more.
- xmin, ymin, xmax, ymax: coordinates of bounding box in projected coordinates.
"""

import PIL.Image

try:
    import mapnik
except ImportError:
    # It's possible to get by without mapnik,
    # if you don't plan to use the mapnik provider.
    pass

class Mapnik:
    """ Built-in Mapnik provider. Renders map images from Mapnik XML files.
    
        This provider is identified by the name "mapnik" in the TileStache config.
        
        Additional arguments:
        
        - mapfile (required)
            Local file path to Mapnik XML file.
    
        More information on Mapnik and Mapnik XML:
        - http://mapnik.org
        - http://trac.mapnik.org/wiki/XMLGettingStarted
        - http://trac.mapnik.org/wiki/XMLConfigReference
    """
    def __init__(self, layer, mapfile):
        """ Initialize Mapnik provider with layer and mapfile.
            
            XML mapfile keyword arg comes from TileStache config,
            and is an absolute path by the time it gets here.
        """
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
    """ Load external provider based on a class path.
    
        Example classpath: "Module.Submodule.Classname",
    """
    classpath = classpath.split('.')
    module = __import__( '.'.join(classpath[:-1]) )
    _class = getattr(module, classpath[-1])
    
    return _class
