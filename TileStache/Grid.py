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

import logging
import json

from TileStache.Core import KnownUnknown
from TileStache.Geography import getProjectionByName

try:
    import mapnik2 as mapnik
except ImportError:
    try:
        import mapnik
    except ImportError:
        pass

global_mapnik_lock = allocate_lock()

class Provider:

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
            self.mapnik = mapnik.Map(0, 0)
            
            if exists(self.mapfile):
                mapnik.load_map(self.mapnik, str(self.mapfile))
            
            else:
                handle, filename = mkstemp()
                os.write(handle, urlopen(self.mapfile).read())
                os.close(handle)
    
                mapnik.load_map(self.mapnik, filename)
                os.unlink(filename)

            logging.debug('TileStache.Grid.renderArea() %.3f to load %s', time() - start_time, self.mapfile)
        
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
        
        return SaveableResponse(json.dumps(data))
    
        logging.debug('TileStache.Grid.renderArea() %dx%d at %d in %.3f from %s', width, height, self.scale, time() - start_time, self.mapfile)
    
        return img

    def renderTile(self, width, height, srs, coord):
        """
        """
        if self.mapnik is None:
            self.mapnik = mapnik.Map(0, 0)
            mapnik.load_map(self.mapnik, str(self.mapfile))

        # buffer as fraction of tile size
        buffer = 0.0

        nw = self.layer.projection.coordinateLocation(coord.left(buffer).up(buffer))
        se = self.layer.projection.coordinateLocation(coord.right(1 + buffer).down(1 + buffer))
        ul = self.mercator.locationProj(nw)
        lr = self.mercator.locationProj(se)

        self.mapnik.width = width + 2 * self.buffer
        self.mapnik.height = height + 2 * self.buffer
        self.mapnik.zoom_to_box(mapnik.Box2d(ul.x, ul.y, lr.x, lr.y))

        # create grid as same size as map/image
        grid = mapnik.Grid(width + 2 * self.buffer, height + 2 * self.buffer)
        # render a layer to that grid array
        mapnik.render_layer(self.mapnik, grid, layer=self.layer_index, fields=self.fields)
        # extract a gridview excluding the buffer
        grid_view = grid.view(self.buffer, self.buffer, width, height)
        # then encode the grid array as utf, resample to 1/scale the size, and dump features
        grid_utf = grid_view.encode('utf', resolution=self.scale, add_features=True)

        return SaveableResponse(json.dumps(grid_utf))

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
    def __init__(self, content):
        self.content = content

    def save(self, out, format):
        if format != 'JSON':
            raise KnownUnknown('MapnikGrid only saves .json tiles, not "%s"' % format)

        out.write(self.content)
    
    def crop(self, bbox):
        """ Fake-crop that doesn't actually crop.
        
            TODO: crop.
        """
        return self
