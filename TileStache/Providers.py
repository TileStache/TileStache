""" The provider bits of TileStache.

A Provider is the part of TileStache that actually renders imagery. A few default
providers are found here, but it's possible to define your own and pull them into
TileStache dynamically by class name.

Built-in providers:
- mapnik
- proxy

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

A provider must offer one of two methods for rendering map areas.

The renderTile() method draws a single tile at a time, and has these arguments:

- width, height: in pixels
- srs: projection as Proj4 string.
  "+proj=longlat +ellps=WGS84 +datum=WGS84" is an example, 
  see http://spatialreference.org for more.
- coord: Coordinate object representing a single tile.

The renderArea() method draws a variably-sized area, and is used when drawing
metatiles. It has these arguments:

- width, height: in pixels
- srs: projection as Proj4 string.
  "+proj=longlat +ellps=WGS84 +datum=WGS84" is an example, 
  see http://spatialreference.org for more.
- xmin, ymin, xmax, ymax: coordinates of bounding box in projected coordinates.
- zoom: zoom level of final map. Technically this can be derived from the other
  arguments, but that's a hassle so we'll pass it in explicitly.
  
A provider may offer a method for custom response type, getTypeByExtension().
This method accepts a single argument, a filename extension string (e.g. "png",
"json", etc.) and returns a tuple with twon strings: a mime-type and a format.
Note that for image and non-image tiles alike, renderArea() and renderTile()
methods on a provider class must return a object with a save() method that
can accept a file-like object and a format name, e.g. this should word:
    
    provder.renderArea(...).save(fp, "TEXT")

... if "TEXT" is a valid response format according to getTypeByExtension().

Non-image providers and metatiles do not mix.

For an example of a non-image provider, see TileStache.Goodies.Provider.PostGeoJSON.
"""

import os

from StringIO import StringIO
from urlparse import urlparse
from httplib import HTTPConnection
from tempfile import mkstemp
from urllib import urlopen

try:
    import mapnik
except ImportError:
    # It's possible to get by without mapnik,
    # if you don't plan to use the mapnik provider.
    pass

import PIL.Image
import ModestMaps
from ModestMaps.Core import Point, Coordinate

import Geography

def getProviderByName(name):
    """ Retrieve a provider object by name.
    
        Raise an exception if the name doesn't work out.
    """
    if name.lower() == 'mapnik':
        return Mapnik

    elif name.lower() == 'proxy':
        return Proxy

    raise Exception('Unknown provider name: "%s"' % name)

class Proxy:
    """ Proxy provider, to pass through and cache tiles from other places.
    
        This provider is identified by the name "proxy" in the TileStache config.
        
        Additional arguments:
        
        - url (optional)
            URL template for remote tiles, for example:
            "http://tile.openstreetmap.org/{Z}/{X}/{Y}.png"
        - provider (optional)
            Provider name string from Modest Maps built-ins.
            See ModestMaps.builtinProviders.keys() for a list.
            Example: "OPENSTREETMAP".

        One of the above is required. When both are present, url wins.
        
        Example configuration:
        
        {
            "name": "proxy",
            "url": "http://tile.openstreetmap.org/{Z}/{X}/{Y}.png"
        }
    """
    def __init__(self, layer, url=None, provider_name=None):
        """ Initialize Proxy provider with layer and url.
        """
        if url:
            self.provider = ModestMaps.Providers.TemplatedMercatorProvider(url)

        elif provider_name:
            if provider_name in ModestMaps.builtinProviders:
                self.provider = ModestMaps.builtinProviders[provider_name]()
            else:
                raise Exception('Unkown Modest Maps provider: "%s"' % provider_name)

        else:
            raise Exception('Missing required url or provider parameter to Proxy provider')

    def renderTile(self, width, height, srs, coord):
        """
        """
        if srs != Geography.SphericalMercator.srs:
            raise Exception('Projection doesn\'t match EPSG:900913: "%(srs)s"' % locals())
    
        if (width, height) != (256, 256):
            raise Exception("Image dimensions don't match expected tile size: %(width)dx%(height)d" % locals())

        img = PIL.Image.new('RGB', (width, height))
        
        for url in self.provider.getTileUrls(coord):
            s, host, path, p, query, f = urlparse(url)
            conn = HTTPConnection(host, 80)
            conn.request('GET', path+'?'+query)

            body = conn.getresponse().read()
            tile = PIL.Image.open(StringIO(body)).convert('RGBA')
            img.paste(tile, (0, 0), tile)
        
        return img
            
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

    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom):
        """
        """
        if self.mapnik is None:
            self.mapnik = mapnik.Map(0, 0)
            
            handle, filename = mkstemp()
            os.write(handle, urlopen(self.mapfile).read())
            os.close(handle)

            mapnik.load_map(self.mapnik, filename)
            os.unlink(filename)
        
        self.mapnik.width = width
        self.mapnik.height = height
        self.mapnik.zoom_to_box(mapnik.Envelope(xmin, ymin, xmax, ymax))
        
        img = mapnik.Image(width, height)
        mapnik.render(self.mapnik, img)
        
        img = PIL.Image.fromstring('RGBA', (width, height), img.tostring())
        
        return img
