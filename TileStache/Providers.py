""" The provider bits of TileStache.

A Provider is the part of TileStache that actually renders imagery. A few default
providers are found here, but it's possible to define your own and pull them into
TileStache dynamically by class name.

Built-in providers:
- mapnik (Mapnik)
- proxy (Proxy)
- vector (TileStache.Vector.Provider)
- url template (UrlTemplate)
- mbtiles (TileStache.MBTiles.Provider)

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
from posixpath import exists
from thread import allocate_lock
from urlparse import urlparse, urljoin
import urllib
from tempfile import mkstemp
from string import Template
from urllib import urlopen
import urllib2
from glob import glob
from time import time

try:
    import mapnik2 as mapnik
except ImportError:
    try:
        import mapnik
    except ImportError:
        # It's possible to get by without mapnik,
        # if you don't plan to use the mapnik provider.
        pass

try:
    from PIL import Image
except ImportError:
    # On some systems, PIL.Image is known as Image.
    import Image

import ModestMaps
from ModestMaps.Core import Point, Coordinate

import Vector
import MBTiles
import Geography

def getProviderByName(name):
    """ Retrieve a provider object by name.
    
        Raise an exception if the name doesn't work out.
    """
    if name.lower() == 'mapnik':
        return Mapnik

    elif name.lower() == 'proxy':
        return Proxy

    elif name.lower() == 'url template':
        return UrlTemplate

    elif name.lower() == 'vector':
        return Vector.Provider

    elif name.lower() == 'mbtiles':
        return MBTiles.Provider

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

global_mapnik_lock = allocate_lock()

class Mapnik:
    """ Built-in Mapnik provider. Renders map images from Mapnik XML files.
    
        This provider is identified by the name "mapnik" in the TileStache config.
        
        Additional arguments:
        
        - mapfile (required)
            Local file path to Mapnik XML file.
    
        - fonts (optional)
            Local directory path to *.ttf font files.
    
        More information on Mapnik and Mapnik XML:
        - http://mapnik.org
        - http://trac.mapnik.org/wiki/XMLGettingStarted
        - http://trac.mapnik.org/wiki/XMLConfigReference
    """
    
    def __init__(self, layer, mapfile, fonts=None):
        """ Initialize Mapnik provider with layer and mapfile.
            
            XML mapfile keyword arg comes from TileStache config,
            and is an absolute path by the time it gets here.
        """
        maphref = urljoin(layer.config.dirpath, mapfile)
        scheme, h, path, q, p, f = urlparse(maphref)
        
        if scheme in ('file', ''):
            self.mapfile = path
        else:
            self.mapfile = maphref
        
        self.layer = layer
        self.mapnik = None
        
        engine = mapnik.FontEngine.instance()
        
        if fonts:
            fontshref = urljoin(layer.config.dirpath, fonts)
            scheme, h, path, q, p, f = urlparse(fontshref)
            
            if scheme not in ('file', ''):
                raise Exception('Fonts from "%s" can\'t be used by Mapnik' % fontshref)
        
            for font in glob(path.rstrip('/') + '/*.ttf'):
                engine.register_font(str(font))

    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom):
        """
        """
        start_time = time()
        
        if self.mapnik is None:
            self.mapnik = mapnik.Map(0, 0)
            
            if exists(self.mapfile):
                mapnik.load_map(self.mapnik, str(self.mapfile))
            
            else:
                handle, filename = mkstemp()
                os.write(handle, urlopen(self.mapfile).read())
                os.close(handle)
    
                mapnik.load_map(self.mapnik, filename)
                os.unlink(filename)

            logging.debug('TileStache.Providers.Mapnik.renderArea() %.3f to load %s', time() - start_time, self.mapfile)
        
        #
        # Mapnik can behave strangely when run in threads, so place a lock on the instance.
        #
        if global_mapnik_lock.acquire():
            self.mapnik.width = width
            self.mapnik.height = height
            self.mapnik.zoom_to_box(mapnik.Envelope(xmin, ymin, xmax, ymax))
            
            img = mapnik.Image(width, height)
            mapnik.render(self.mapnik, img)
            global_mapnik_lock.release()
        
        img = Image.fromstring('RGBA', (width, height), img.tostring())
    
        logging.debug('TileStache.Providers.Mapnik.renderArea() %dx%d in %.3f from %s', width, height, time() - start_time, self.mapfile)
    
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
