""" Mapnik UTFGrid Provider.

Sample configuration:

    "provider":
    {
      "class": "TileStache.Goodies.Providers.MapnikGrid:Provider",
      "kwargs": { "mapfile": "mymap.xml" }
    }

"""
import json
import mapnik2 as mapnik
from TileStache.Geography import getProjectionByName

class Provider:

    def __init__(self, layer, mapfile):
        """
        """
	self.mapnik = None
        self.layer = layer
	self.mapfile = mapfile

	self.mercator = getProjectionByName('spherical mercator')

    def renderTile(self, width, height, srs, coord):
        """
        """
        if self.mapnik is None:
            self.mapnik = mapnik.Map(0, 0)

 #       if exists(self.mapfile):
            mapnik.load_map(self.mapnik, str(self.mapfile))

  #      else:
   #         handle, filename = mkstemp()
    #        os.write(handle, urlopen(self.mapfile).read())
     #       os.close(handle)

      #      mapnik.load_map(self.mapnik, filename)
       #     os.unlink(filename)

	nw = self.layer.projection.coordinateLocation(coord)
	se = self.layer.projection.coordinateLocation(coord.right().down())
	ul = self.mercator.locationProj(nw)
        lr = self.mercator.locationProj(se)


        self.mapnik.width = width
        self.mapnik.height = height
        #self.mapnik.zoom_to_box(mapnik.Envelope(xmin, ymin, xmax, ymax))
        #self.mapnik.zoom_to_box(mapnik.Envelope(ul.x, ul.y, lr.x, lr.y))
        self.mapnik.zoom_to_box(mapnik.Box2d(ul.x, ul.y, lr.x, lr.y))

        #img = mapnik.Image(width, height)
        #mapnik.render(self.mapnik, img)

        #img = Image.fromstring('RGBA', (width, height), img.tostring())

	# create grid as same size as map/image
	grid = mapnik.Grid(width, height)
	#FIXME: Fields should be passed as a parameter
	# render a layer to that grid array
	mapnik.render_layer(self.mapnik,grid,layer=0,fields=['name','address'])
	# then encode the grid array as utf, resample to 1/4 the size, and dump features
	grid_utf = grid.encode('utf',resolution=4,add_features=True)

        return SaveableResponse('grid(' + json.dumps(grid_utf) + ')')

    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.

            This only accepts "json".
        """
        if extension.lower() != 'json':
            raise KnownUnknown('PostGeoJSON only makes .json tiles, not "%s"' % extension)

        return 'text/json', 'JSON'

class SaveableResponse:
    """ Wrapper class for JSON response that makes it behave like a PIL.Image object.

        TileStache.getTile() expects to be able to save one of these to a buffer.
    """
    def __init__(self, content):
        self.content = content
#        self.indent = indent
 #       self.precision = precision

    def save(self, out, format):
        if format != 'JSON':
            raise KnownUnknown('PostGeoJSON only saves .json tiles, not "%s"' % format)

	out.write(self.content)
