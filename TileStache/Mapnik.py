""" Mapnik UTFGrid Provider.

Takes the first layer from the given mapnik xml file and renders it as UTFGrid
https://github.com/mapbox/utfgrid-spec/blob/master/1.2/utfgrid.md
It can then be used for this:
http://mapbox.github.com/wax/interaction-leaf.html
Only works with mapnik2 (Where the Grid functionality was introduced)

Use Sperical Mercator projection and the extension "json"

Sample configuration:

    "provider":
    {
      "class": "TileStache.Goodies.Providers.MapnikGrid:Provider",
      "kwargs":
      {
        "mapfile": "mymap.xml", 
        "fields":["name", "address"],
        "layer_index": 0,
        "scale": 4
      }
    }

mapfile: the mapnik xml file to load the map from
fields: The fields that should be added to the resulting grid json.
layer_index: The index of the layer you want from your map xml to be rendered
scale: What to divide the tile pixel size by to get the resulting grid size. Usually this is 4.
buffer: buffer around the queried features, in px, default 0. Use this to prevent problems on tile boundaries.
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

    def __init__(self, layer, mapfile, fields=None, layer_index=0, scale=4):
        """
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
