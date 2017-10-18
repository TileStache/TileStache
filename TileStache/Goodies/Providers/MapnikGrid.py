""" Mapnik UTFGrid Provider.

Takes the first layer from the given mapnik xml file and renders it as UTFGrid
https://github.com/mapbox/utfgrid-spec/blob/master/1.2/utfgrid.md
It can then be used for this:
http://mapbox.github.com/wax/interaction-leaf.html
Only works with mapnik>=2.0 (Where the Grid functionality was introduced)

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
        "wrapper": "grid",
        "scale": 4
      }
    }

mapfile: the mapnik xml file to load the map from
fields: The fields that should be added to the resulting grid json.
layer_index: The index of the layer you want from your map xml to be rendered
wrapper: If not included the json will be output raw, if included the json will be wrapped in "wrapper(JSON)" (for use with wax)
scale: What to divide the tile pixel size by to get the resulting grid size. Usually this is 4.
buffer: buffer around the queried features, in px, default 0. Use this to prevent problems on tile boundaries.
"""
import json
from os.path import exists
from TileStache.Core import KnownUnknown
from TileStache.Geography import getProjectionByName
try:
    from urllib.parse import urljoin, urlparse
except ImportError:
    # Python 2
    from urlparse import urljoin, urlparse
from tempfile import mkstemp
from urllib import urlopen
import os

try:
    import mapnik
except ImportError:
    pass

class Provider:

    def __init__(self, layer, mapfile, fields, layer_index=0, wrapper=None, scale=4, buffer=0):
        """
        """
        self.mapnik = None
        self.layer = layer

        maphref = urljoin(layer.config.dirpath, mapfile)
        scheme, h, path, q, p, f = urlparse(maphref)
        
        if scheme in ('file', ''):
            self.mapfile = path
        else:
            self.mapfile = maphref
        
        self.layer_index = layer_index
        self.wrapper = wrapper
        self.scale = scale
        self.buffer = buffer
        #De-Unicode the strings or mapnik gets upset
        self.fields = list(str(x) for x in fields)

        self.mercator = getProjectionByName('spherical mercator')

    def renderTile(self, width, height, srs, coord):
        """
        """
        if self.mapnik is None:
            self.mapnik = get_mapnikMap(self.mapfile)

        # buffer as fraction of tile size
        buffer = float(self.buffer) / 256

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

        if self.wrapper is None:
            return SaveableResponse(json.dumps(grid_utf))
        else:
            return SaveableResponse(self.wrapper + '(' + json.dumps(grid_utf) + ')')

    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.

            This only accepts "json".
        """
        if extension.lower() != 'json':
            raise KnownUnknown('MapnikGrid only makes .json tiles, not "%s"' % extension)

        return 'application/json; charset=utf-8', 'JSON'

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
