from sys import stderr
from tempfile import mkstemp
from thread import allocate_lock
from os import close, write, unlink
from optparse import OptionParser
from os.path import abspath

import TileStache
import ModestMaps

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

class BadComposure(Exception):
    pass

parser = OptionParser(usage="""compose.py [options] file

There are three ways to set a map coverage area.

1) Center, zoom, and dimensions: create a map of the specified size,
   centered on a given geographical point at a given zoom level:

   python compose.py -p OPENSTREETMAP -d 800 800 -c 37.8 -122.3 -z 11 out.jpg

2) Extent and dimensions: create a map of the specified size that
   adequately covers the given geographical extent:

   python compose.py -p MICROSOFT_ROAD -d 800 800 -e 36.9 -123.5 38.9 -121.2 out.png

3) Extent and zoom: create a map at the given zoom level that covers
   the precise geographical extent, at whatever pixel size is necessary:
   
   python compose.py -p BLUE_MARBLE -e 36.9 -123.5 38.9 -121.2 -z 9 out.jpg""")

defaults = dict(center=(37.8044, -122.2712), zoom=14, dimensions=(900, 600), verbose=True)

parser.set_defaults(**defaults)

parser.add_option('-v', '--verbose', dest='verbose',
                  help='Make a bunch of noise',
                  action='store_true')

parser.add_option('-c', '--center', dest='center', nargs=2,
                  help='Center. lat, lon, e.g.: 37.804 -122.263', type='float',
                  action='store')

parser.add_option('-e', '--extent', dest='extent', nargs=4,
                  help='Geographical extent. Two lat, lon pairs', type='float',
                  action='store')

parser.add_option('-z', '--zoom', dest='zoom',
                  help='Zoom level', type='int',
                  action='store')

parser.add_option('-d', '--dimensions', dest='dimensions', nargs=2,
                  help='Pixel dimensions of image', type='int',
                  action='store')

if __name__ == '__main__':

    (options, args) = parser.parse_args()
    
    try:
        try:
            outfile = args[0]
        except IndexError:
            raise BadComposure('Error: Missing output file.')
        
        config = TileStache.parseConfigfile('tilestache.cfg')
        provider = Provider(config.layers['osm'])
        
        if options.center and options.extent:
            raise BadComposure("Error: bad map coverage, center and extent can't both be set.")
        
        elif options.extent and options.dimensions and options.zoom:
            raise BadComposure("Error: bad map coverage, dimensions and zoom can't be set together with extent.")
        
        elif options.center and options.zoom and options.dimensions:
            lat, lon = options.center[0], options.center[1]
            width, height = options.dimensions[0], options.dimensions[1]

            dimensions = ModestMaps.Core.Point(width, height)
            center = ModestMaps.Geo.Location(lat, lon)
            zoom = options.zoom

            map = ModestMaps.mapByCenterZoom(provider, center, zoom, dimensions)
            
        elif options.extent and options.dimensions:
            latA, lonA = options.extent[0], options.extent[1]
            latB, lonB = options.extent[2], options.extent[3]
            width, height = options.dimensions[0], options.dimensions[1]

            dimensions = ModestMaps.Core.Point(width, height)
            locationA = ModestMaps.Geo.Location(latA, lonA)
            locationB = ModestMaps.Geo.Location(latB, lonB)

            map = ModestMaps.mapByExtent(provider, locationA, locationB, dimensions)
    
        elif options.extent and options.zoom:
            latA, lonA = options.extent[0], options.extent[1]
            latB, lonB = options.extent[2], options.extent[3]

            locationA = ModestMaps.Geo.Location(latA, lonA)
            locationB = ModestMaps.Geo.Location(latB, lonB)
            zoom = options.zoom

            map = ModestMaps.mapByExtentZoom(provider, locationA, locationB, zoom)
    
        else:
            raise BadComposure("Error: not really sure what's going on.")

    except BadComposure, e:
        print >> stderr, parser.usage
        print >> stderr, ''
        print >> stderr, '%s --help for possible options.' % __file__
        print >> stderr, ''
        print >> stderr, e
        exit(1)

    if options.verbose:
        print map.coordinate, map.offset, '->', outfile, (map.dimensions.x, map.dimensions.y)

    map.draw(options.verbose).save(outfile)
