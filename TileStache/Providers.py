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

from io import BytesIO
from string import Template

from .py3_compat import urllib2

try:
    from PIL import Image
except ImportError:
    # On some systems, PIL.Image is known as Image.
    import Image

import ModestMaps
from ModestMaps.Core import Point, Coordinate

from . import Geography

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

class Verbatim:
    ''' Wrapper for PIL.Image that saves raw input bytes if modes and formats match.
    '''
    def __init__(self, bytes_):
        self.buffer = BytesIO(bytes_)
        self.format = None
        self._image = None

        #
        # Guess image format based on magic number, if possible.
        # http://www.astro.keele.ac.uk/oldusers/rno/Computing/File_magic.html
        #
        magic = {
            '\x89\x50\x4e\x47': 'PNG',
            '\xff\xd8\xff\xe0': 'JPEG',
            '\x47\x49\x46\x38': 'GIF',
            '\x47\x49\x46\x38': 'GIF',
            '\x4d\x4d\x00\x2a': 'TIFF',
            '\x49\x49\x2a\x00': 'TIFF'
            }

        if bytes_[:4] in magic:
            self.format = magic[bytes_[:4]]

        else:
            self.format = self.image().format

    def image(self):
        ''' Return a guaranteed instance of PIL.Image.
        '''
        if self._image is None:
            self._image = Image.open(self.buffer)

        return self._image

    def convert(self, mode):
        if mode == self.image().mode:
            return self
        else:
            return self.image().convert(mode)

    def crop(self, bbox):
        return self.image().crop(bbox)

    def save(self, output, format):
        if format == self.format:
            output.write(self.buffer.getvalue())
        else:
            self.image().save(output, format)

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
        - timeout (optional)
            Defines a timeout in seconds for the request.
            If not defined, the global default timeout setting will be used.


        Either url or provider is required. When both are present, url wins.

        Example configuration:

        {
            "name": "proxy",
            "url": "http://tile.openstreetmap.org/{Z}/{X}/{Y}.png"
        }
    """
    def __init__(self, layer, url=None, provider_name=None, timeout=None):
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

        self.timeout = timeout

    @staticmethod
    def prepareKeywordArgs(config_dict):
        """ Convert configured parameters to keyword args for __init__().
        """
        kwargs = dict()

        if 'url' in config_dict:
            kwargs['url'] = config_dict['url']

        if 'provider' in config_dict:
            kwargs['provider_name'] = config_dict['provider']

        if 'timeout' in config_dict:
            kwargs['timeout'] = config_dict['timeout']

        return kwargs

    def renderTile(self, width, height, srs, coord):
        """
        """
        img = None
        urls = self.provider.getTileUrls(coord)

        # Tell urllib2 get proxies if set in the environment variables <protocol>_proxy
        # see: https://docs.python.org/2/library/urllib2.html#urllib2.ProxyHandler
        proxy_support = urllib2.ProxyHandler()
        url_opener = urllib2.build_opener(proxy_support)

        for url in urls:
            body = url_opener.open(url, timeout=self.timeout).read()
            tile = Verbatim(body)

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

        - source projection (optional)
            Projection to transform coordinates into before making request
        - timeout (optional)
            Defines a timeout in seconds for the request.
            If not defined, the global default timeout setting will be used.

        More on string substitutions:
        - http://docs.python.org/library/string.html#template-strings
    """

    def __init__(self, layer, template, referer=None, source_projection=None,
                 timeout=None):
        """ Initialize a UrlTemplate provider with layer and template string.

            http://docs.python.org/library/string.html#template-strings
        """
        self.layer = layer
        self.template = Template(template)
        self.referer = referer
        self.source_projection = source_projection
        self.timeout = timeout

    @staticmethod
    def prepareKeywordArgs(config_dict):
        """ Convert configured parameters to keyword args for __init__().
        """
        kwargs = {'template': config_dict['template']}

        if 'referer' in config_dict:
            kwargs['referer'] = config_dict['referer']

        if 'source projection' in config_dict:
            kwargs['source_projection'] = Geography.getProjectionByName(config_dict['source projection'])

        if 'timeout' in config_dict:
            kwargs['timeout'] = config_dict['timeout']

        return kwargs

    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom):
        """ Return an image for an area.

            Each argument (width, height, etc.) is substituted into the template.
        """
        if self.source_projection is not None:
            ne_location = self.layer.projection.projLocation(Point(xmax, ymax))
            ne_point = self.source_projection.locationProj(ne_location)
            ymax = ne_point.y
            xmax = ne_point.x
            sw_location = self.layer.projection.projLocation(Point(xmin, ymin))
            sw_point = self.source_projection.locationProj(sw_location)
            ymin = sw_point.y
            xmin = sw_point.x
            srs = self.source_projection.srs

        mapping = {'width': width, 'height': height, 'srs': srs, 'zoom': zoom,
                   'xmin': xmin, 'ymin': ymin, 'xmax': xmax, 'ymax': ymax}

        href = self.template.safe_substitute(mapping)
        req = urllib2.Request(href)

        if self.referer:
            req.add_header('Referer', self.referer)

        body = urllib2.urlopen(req, timeout=self.timeout).read()
        tile = Verbatim(body)

        return tile
