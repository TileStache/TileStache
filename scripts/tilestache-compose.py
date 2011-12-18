from sys import stderr
from tempfile import mkstemp
from os import close, write, unlink
from os.path import abspath

import TileStache
import ModestMaps

config = TileStache.parseConfigfile('tilestache.cfg')

class Provider (ModestMaps.Providers.IMapProvider):

    def __init__(self, layer):
        self.projection = layer.projection
        self.layer = layer
        self.files = []

    def tileWidth(self):
        return 256

    def tileHeight(self):
        return 256

    def getTileUrls(self, coord):
        print >> stderr, coord, '...',

        mime_type, tile_data = TileStache.getTile(self.layer, coord, 'png')
        
        handle, filename = mkstemp(prefix='tile-', suffix='.png')
        write(handle, tile_data)
        close(handle)
        
        self.files.append(filename)
        
        print >> stderr, filename

        return ('file://' + abspath(filename), )
    
    def __del__(self):
        for filename in self.files:
            print >> stderr, 'no more', filename
            unlink(filename)

provider = Provider(config.layers['osm'])

lat, lon = 37.8044, -122.2712
width, height = 900, 600

dimensions = ModestMaps.Core.Point(width, height)
center = ModestMaps.Geo.Location(lat, lon)
zoom = 14

map = ModestMaps.mapByCenterZoom(provider, center, zoom, dimensions)

map.draw(True).save('composed.png')