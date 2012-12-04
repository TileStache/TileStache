""" The provider bits of TileStache.

A Provider is the part of TileStache that actually renders imagery. A few default
providers are found here, but it's possible to define your own and pull them into
TileStache dynamically by class name.

Built-in providers:
- mapnik (Mapnik.ImageProvider)
- proxy (Proxy)
- vector (TileStache.Vector.Provider)
- url template (UrlTemplate)
- mbtiles (TileStache.MBTiles.Provider)
- mapnik grid (Mapnik.GridProvider)

Example built-in provider, for JSON configuration file:

    "layer-name": {
        "provider": {"name": "mapnik", "mapfile": "style.xml"},
        ...
    }

Example external provider, for JSON configuration file:

    "layer-name": {
        "provider": {"class": "Module:Classname", "kwargs": {"frob": "yes"}},
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

For an example of a non-image provider, see TileStache.Vector.Provider.
"""

import os
import logging

from StringIO import StringIO
from string import Template
import urllib2
import urllib

try:
    from PIL import Image
except ImportError:
    # On some systems, PIL.Image is known as Image.
    import Image

import ModestMaps
from ModestMaps.Core import Point, Coordinate

import Geography

# This import should happen inside getProviderByName(), but when testing
# on Mac OS X features are missing from output. Wierd-ass C libraries...
try:
    from . import Vector
except ImportError:
    pass

# Already deprecated; provided for temporary backward-compatibility with
# old location of Mapnik provider. TODO: remove in next major version.
try:
    from .Mapnik import ImageProvider as Mapnik
except ImportError:
    pass

def getProviderByName(name):
    """ Retrieve a provider object by name.
    
        Raise an exception if the name doesn't work out.
    """
    if name.lower() == 'mapnik':
        from . import Mapnik
        return Mapnik.ImageProvider

    elif name.lower() == 'proxy':
        return Proxy

    elif name.lower() == 'url template':
        return UrlTemplate

    elif name.lower() == 'vector':
        from . import Vector
        return Vector.Provider

    elif name.lower() == 'mbtiles':
        from . import MBTiles
        return MBTiles.Provider

    elif name.lower() == 'mapnik grid':
        from . import Mapnik
        return Mapnik.GridProvider

    elif name.lower() == 'sandwich':
        from . import Sandwich
        return Sandwich.Provider

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

    @staticmethod
    def prepareKeywordArgs(config_dict):
        """ Convert configured parameters to keyword args for __init__().
        """
        kwargs = dict()

        if 'url' in config_dict:
            kwargs['url'] = config_dict['url']

        if 'provider' in config_dict:
            kwargs['provider_name'] = config_dict['provider']
        
        return kwargs
    
    def renderTile(self, width, height, srs, coord):
        """
        """
        if srs != Geography.SphericalMercator.srs:
            raise Exception('Projection doesn\'t match EPSG:900913: "%(srs)s"' % locals())
    
        if (width, height) != (256, 256):
            raise Exception("Image dimensions don't match expected tile size: %(width)dx%(height)d" % locals())

        img = None
        urls = self.provider.getTileUrls(coord)
        
        for url in urls:
            body = urllib.urlopen(url).read()
            tile = Image.open(StringIO(body)).convert('RGBA')

            if len(urls) == 1:
                #
                # if there is only one URL, don't bother
                # with PIL's non-Porter-Duff alpha channeling.
                #
                return tile
            elif img is None:
                #
                # for many URLs, paste them to a new image.
                #
                img = Image.new('RGBA', (width, height))
            
            img.paste(tile, (0, 0), tile)
        
        return img

class UrlTemplate:
    """ Built-in URL Template provider. Proxies map images from WMS servers.
        
        This provider is identified by the name "url template" in the TileStache config.
        
        Additional arguments:
        
        - template (required)
            String with substitutions suitable for use in string.Template.

        - referer (optional)
            String to use in the "Referer" header when making HTTP requests.

        More on string substitutions:
        - http://docs.python.org/library/string.html#template-strings
    """

    def __init__(self, layer, template, referer=None):
        """ Initialize a UrlTemplate provider with layer and template string.
        
            http://docs.python.org/library/string.html#template-strings
        """
        self.layer = layer
        self.template = Template(template)
        self.referer = referer

    @staticmethod
    def prepareKeywordArgs(config_dict):
        """ Convert configured parameters to keyword args for __init__().
        """
        kwargs = {'template': config_dict['template']}

        if 'referer' in config_dict:
            kwargs['referer'] = config_dict['referer']
        
        return kwargs
    
    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom):
        """ Return an image for an area.
        
            Each argument (width, height, etc.) is substituted into the template.
        """
        mapping = {'width': width, 'height': height, 'srs': srs, 'zoom': zoom}
        mapping.update({'xmin': xmin, 'ymin': ymin, 'xmax': xmax, 'ymax': ymax})
        
        href = self.template.safe_substitute(mapping)
        req = urllib2.Request(href)
        
        if self.referer:
            req.add_header('Referer', self.referer)
        
        body = urllib2.urlopen(req).read()
        tile = Image.open(StringIO(body)).convert('RGBA')

        return tile
