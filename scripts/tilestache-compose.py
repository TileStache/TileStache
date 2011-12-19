from sys import stderr
from tempfile import mkstemp
from thread import allocate_lock
from os import close, write, unlink
from os.path import abspath

import TileStache
import ModestMaps

config = TileStache.parseConfigfile('tilestache.cfg')

class Provider (ModestMaps.Providers.IMapProvider):

    def __init__(self, layer, use_threads=None):
        self.projection = layer.projection
        self.layer = layer
        self.files = []

        self.lock = allocate_lock()
        
        #
        # It's possible that Mapnik is not thread-safe, best to be cautious.
        # Otherwise, allow the constructor to specify whether to use threads.
        #
        if use_threads is None:
            self.threadsafe = self.layer.provider is not TileStache.Providers.Mapnik
        else:
            self.threadsafe = use_threads

    def tileWidth(self):
        return 256

    def tileHeight(self):
        return 256

    def getTileUrls(self, coord):
        """ Return tile URLs that start with file://, by first retrieving them.
        """
        if self.threadsafe or self.lock.acquire():
            mime_type, tile_data = TileStache.getTile(self.layer, coord, 'png')
            
            handle, filename = mkstemp(prefix='tilestache-compose-', suffix='.png')
            write(handle, tile_data)
            close(handle)
            
            self.files.append(filename)
            
            if self.lock.locked():
                self.lock.release()
    
            return ('file://' + abspath(filename), )
    
    def __del__(self):
        """ Delete any tile that was saved in self.getTileUrls().
        """
        for filename in self.files:
            unlink(filename)

provider = Provider(config.layers['osm'])

lat, lon = 37.8044, -122.2712
width, height = 900, 600

dimensions = ModestMaps.Core.Point(width, height)
center = ModestMaps.Geo.Location(lat, lon)
zoom = 14

map = ModestMaps.mapByCenterZoom(provider, center, zoom, dimensions)

map.draw(True).save('composed.png')