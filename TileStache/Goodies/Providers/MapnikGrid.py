""" Mapnik UTFGrid Provider.
Only works with mapnik2 (Where the Grid functionality was introduced)

Sample configuration:

    "provider":
    {
      "class": "TileStache.Goodies.Providers.MapnikGrid:Provider",
      "kwargs": { "mapfile": "mymap.xml", "fields":["name","address"] }
    }

mapfile: the mapnik xml file to load the map from
fields: The fields that should be added to the resulting grid json.

"""
import json
import mapnik2 as mapnik
from TileStache.Geography import getProjectionByName

class Provider:

    def __init__(self, layer, mapfile, fields):
        """
        """
        self.mapnik = None
        self.layer = layer
        self.mapfile = mapfile
        #De-Unicode the strings or mapnik gets upset
        self.fields = list(str(x) for x in fields)

        self.mercator = getProjectionByName('spherical mercator')

    def renderTile(self, width, height, srs, coord):
        """
        """
        if self.mapnik is None:
            self.mapnik = mapnik.Map(0, 0)
            mapnik.load_map(self.mapnik, str(self.mapfile))

        nw = self.layer.projection.coordinateLocation(coord)
        se = self.layer.projection.coordinateLocation(coord.right().down())
        ul = self.mercator.locationProj(nw)
        lr = self.mercator.locationProj(se)


        self.mapnik.width = width
        self.mapnik.height = height
        self.mapnik.zoom_to_box(mapnik.Box2d(ul.x, ul.y, lr.x, lr.y))

        # create grid as same size as map/image
        grid = mapnik.Grid(width, height)
        # render a layer to that grid array
        mapnik.render_layer(self.mapnik,grid,layer=0,fields=self.fields)
        # then encode the grid array as utf, resample to 1/4 the size, and dump features
        grid_utf = grid.encode('utf',resolution=4,add_features=True)

        return SaveableResponse('grid(' + json.dumps(grid_utf) + ')')

    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.

            This only accepts "json".
        """
        if extension.lower() != 'json':
            raise KnownUnknown('MapnikGrid only makes .json tiles, not "%s"' % extension)

        return 'text/json', 'JSON'

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
