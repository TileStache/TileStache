""" Mapnik Providers.

ImageProvider is known as "mapnik" in TileStache config, GridProvider is
known as "mapnik grid". Both require Mapnik to be installed; Grid requires
Mapnik 2.0.0 and above.
"""
from time import time
from os.path import exists
from thread import allocate_lock
from urlparse import urlparse, urljoin

import logging
import json

from TileStache.Core import KnownUnknown
from TileStache.Geography import getProjectionByName

try:
    from PIL import Image
except ImportError:
    # On some systems, PIL.Image is known as Image.
    import Image

try:
    import mapnik
except ImportError:
    try:
        # mapnik 2.0.0 is known as mapnik2
        import mapnik2 as mapnik
    except ImportError:
        # It's possible to get by without mapnik,
        # if you don't plan to use the mapnik provider.
        pass

global_mapnik_lock = allocate_lock()

class ImageProvider:
    """ Built-in Mapnik provider. Renders map images from Mapnik XML files.
    
        This provider is identified by the name "mapnik" in the TileStache config.
        
        Arguments:
        
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
            self.mapnik = get_mapnikMap(self.mapfile)
            logging.debug('TileStache.Mapnik.ImageProvider.renderArea() %.3f to load %s', time() - start_time, self.mapfile)
        
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
    
        logging.debug('TileStache.Mapnik.ImageProvider.renderArea() %dx%d in %.3f from %s', width, height, time() - start_time, self.mapfile)
    
        return img

class GridProvider:
    """ Built-in UTF Grid provider. Renders JSON raster objects from Mapnik.
    
        This provider is identified by the name "mapnik grid" in the
        Tilestache config, and uses Mapnik 2.0 (and above) to generate
        JSON UTF grid responses.
        
        Sample configuration:

          "provider":
          {
            "name": "mapnik grid",
            "mapfile": "world_merc.xml", 
            "fields": ["NAME", "POP2005"]
          }
    
        Arguments:
        
        - mapfile (required)
          Local file path to Mapnik XML file.
        
        - fields (optional)
          Array of field names to return in the response, defaults to all.
        
        - layer index (optional)
          Which layer from the mapfile to render, defaults to 0 (first layer).
        
        - scale (optional)
          Scale factor of output raster, defaults to 4 (64x64).
        
        Information and examples for UTF Grid:
        - https://github.com/mapbox/utfgrid-spec/blob/master/1.2/utfgrid.md
        - http://mapbox.github.com/wax/interaction-leaf.html
    """
    def __init__(self, layer, mapfile, fields=None, layer_index=0, scale=4):
        """ Initialize Mapnik grid provider with layer and mapfile.
            
            XML mapfile keyword arg comes from TileStache config,
            and is an absolute path by the time it gets here.
        """
        self.mapnik = None
        self.layer = layer
        self.mapfile = mapfile
        self.layer_index = layer_index
        self.scale = scale
        self.fields = fields

        self.mercator = getProjectionByName('spherical mercator')

    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom):
        """
        """
        start_time = time()
        
        if self.mapnik is None:
            self.mapnik = get_mapnikMap(self.mapfile)
            logging.debug('TileStache.Mapnik.GridProvider.renderArea() %.3f to load %s', time() - start_time, self.mapfile)
        
        datasource = self.mapnik.layers[self.layer_index].datasource
        fields = self.fields and map(str, self.fields) or datasource.fields()
        
        #
        # Mapnik can behave strangely when run in threads, so place a lock on the instance.
        #
        if global_mapnik_lock.acquire():
            self.mapnik.width = width
            self.mapnik.height = height
            self.mapnik.zoom_to_box(mapnik.Envelope(xmin, ymin, xmax, ymax))
            
            data = mapnik.render_grid(self.mapnik, 0, resolution=self.scale, fields=fields)
            global_mapnik_lock.release()
    
        logging.debug('TileStache.Mapnik.GridProvider.renderArea() %dx%d at %d in %.3f from %s', width, height, self.scale, time() - start_time, self.mapfile)
        
        return SaveableResponse(data, self.scale)

    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.

            This only accepts "json".
        """
        if extension.lower() != 'json':
            raise KnownUnknown('MapnikGrid only makes .json tiles, not "%s"' % extension)

        return 'application/json', 'JSON'

class SaveableResponse:
    """ Wrapper class for JSON response that makes it behave like a PIL.Image object.

        TileStache.getTile() expects to be able to save one of these to a buffer.
    """
    def __init__(self, content, scale):
        self.content = content
        self.scale = scale

    def save(self, out, format):
        if format != 'JSON':
            raise KnownUnknown('MapnikGrid only saves .json tiles, not "%s"' % format)

        json.dump(self.content, out)
    
    def crop(self, bbox):
        """ Return a cropped grid response.
        """
        minchar, minrow, maxchar, maxrow = [v/self.scale for v in bbox]

        keys, data = self.content['keys'], self.content.get('data', None)
        grid = [row[minchar:maxchar] for row in self.content['grid'][minrow:maxrow]]
        
        cropped = dict(keys=keys, data=data, grid=grid)
        return SaveableResponse(cropped, self.scale)

def get_mapnikMap(mapfile):
    """ Get a new mapnik.Map instance for a mapfile
    """
    mmap = mapnik.Map(0, 0)
    
    if exists(mapfile):
        mapnik.load_map(mmap, str(mapfile))
    
    else:
        handle, filename = mkstemp()
        os.write(handle, urlopen(mapfile).read())
        os.close(handle)

        mapnik.load_map(mmap, filename)
        os.unlink(filename)
    
    return mmap
