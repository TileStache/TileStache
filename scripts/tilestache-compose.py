#!/usr/bin/env python
from __future__ import print_function

from sys import stderr, path
from tempfile import mkstemp
from os import close, write, unlink
from optparse import OptionParser
from os.path import abspath

try:
    from _thread import allocate_lock
except ImportError:
    from thread import allocate_lock

import ModestMaps

mmaps_version = tuple(map(int, getattr(ModestMaps, '__version__', '0.0.0').split('.')))

if mmaps_version < (1, 3, 0):
    raise ImportError('tilestache-compose.py requires ModestMaps 1.3.0 or newer.')

#
# More imports can be found below, after the --include-path option is known.
#

class Provider (ModestMaps.Providers.IMapProvider):
    """ Wrapper for TileStache Layer objects that makes them behave like ModestMaps Provider objects.

        Requires ModestMaps 1.3.0 or better to support "file://" URLs.
    """
    def __init__(self, layer, verbose=False, ignore_cached=None):
        self.projection = layer.projection
        self.layer = layer
        self.files = []

        self.verbose = bool(verbose)
        self.ignore_cached = bool(ignore_cached)
        self.lock = allocate_lock()

        #
        # It's possible that Mapnik is not thread-safe, best to be cautious.
        #
        self.threadsafe = self.layer.provider is not TileStache.Providers.Mapnik

    def tileWidth(self):
        return 256

    def tileHeight(self):
        return 256

    def getTileUrls(self, coord):
        """ Return tile URLs that start with file://, by first retrieving them.
        """
        if self.threadsafe or self.lock.acquire():
            mime_type, tile_data = TileStache.getTile(self.layer, coord, 'png', self.ignore_cached)

            handle, filename = mkstemp(prefix='tilestache-compose-', suffix='.png')
            write(handle, tile_data)
            close(handle)

            self.files.append(filename)

            if not self.threadsafe:
                # must be locked, right?
                self.lock.release()

            if self.verbose:
                size = len(tile_data) / 1024.
                printlocked(self.lock, self.layer.name() + '/%(zoom)d/%(column)d/%(row)d.png' % coord.__dict__, '(%dKB)' % size)

            return ('file://' + abspath(filename), )

    def __del__(self):
        """ Delete any tile that was saved in self.getTileUrls().
        """
        for filename in self.files:
            unlink(filename)

class BadComposure(Exception):
    pass

def printlocked(lock, *stuff):
    """
    """
    if lock.acquire():
        print(' '.join([str(thing) for thing in stuff]))
        lock.release()

parser = OptionParser(usage="""tilestache-compose.py [options] file

There are three ways to set a map coverage area.

1) Center, zoom, and dimensions: create a map of the specified size,
   centered on a given geographical point at a given zoom level:

   tilestache-compose.py -c config.json -l layer-name -d 800 800 -n 37.8 -122.3 -z 11 out.jpg

2) Extent and dimensions: create a map of the specified size that
   adequately covers the given geographical extent:

   tilestache-compose.py -c config.json -l layer-name -d 800 800 -e 36.9 -123.5 38.9 -121.2 out.png

3) Extent and zoom: create a map at the given zoom level that covers
   the precise geographical extent, at whatever pixel size is necessary:

   tilestache-compose.py -c config.json -l layer-name -e 36.9 -123.5 38.9 -121.2 -z 9 out.jpg""")

defaults = dict(center=(37.8044, -122.2712), zoom=14, dimensions=(900, 600), verbose=True)

parser.set_defaults(**defaults)

parser.add_option('-c', '--config', dest='config',
                  help='Path to configuration file.')

parser.add_option('-l', '--layer', dest='layer',
                  help='Layer name from configuration.')

parser.add_option('-n', '--center', dest='center', nargs=2,
                  help='Geographic center of map. Default %.4f, %.4f.' % defaults['center'], type='float',
                  action='store')

parser.add_option('-e', '--extent', dest='extent', nargs=4,
                  help='Geographic extent of map. Two lat, lon pairs', type='float',
                  action='store')

parser.add_option('-z', '--zoom', dest='zoom',
                  help='Zoom level. Default %(zoom)d.' % defaults, type='int',
                  action='store')

parser.add_option('-d', '--dimensions', dest='dimensions', nargs=2,
                  help='Pixel width, height of output image. Default %d, %d.' % defaults['dimensions'], type='int',
                  action='store')

parser.add_option('-v', '--verbose', dest='verbose',
                  help='Make a bunch of noise.',
                  action='store_true')

parser.add_option('-i', '--include-path', dest='include_paths',
                  help="Add the following colon-separated list of paths to Python's include path (aka sys.path)")

parser.add_option('-x', '--ignore-cached', action='store_true', dest='ignore_cached',
                  help='Re-render every tile, whether it is in the cache already or not.')

if __name__ == '__main__':

    (options, args) = parser.parse_args()

    if options.include_paths:
        for p in options.include_paths.split(':'):
            path.insert(0, p)

    import TileStache

    try:
        if options.config is None:
            raise TileStache.Core.KnownUnknown('Missing required configuration (--config) parameter.')

        if options.layer is None:
            raise TileStache.Core.KnownUnknown('Missing required layer (--layer) parameter.')

        config = TileStache.parseConfig(options.config)

        if options.layer not in config.layers:
            raise TileStache.Core.KnownUnknown('"%s" is not a layer I know about. Here are some that I do know about: %s.' % (options.layer, ', '.join(sorted(config.layers.keys()))))

        provider = Provider(config.layers[options.layer], options.verbose, options.ignore_cached)

        try:
            outfile = args[0]
        except IndexError:
            raise BadComposure('Error: Missing output file.')

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

    except BadComposure as e:
        print(parser.usage, file=stderr)
        print('', file=stderr)
        print('%s --help for possible options.' % __file__, file=stderr)
        print('', file=stderr)
        print(e, file=stderr)
        exit(1)

    if options.verbose:
        print(map.coordinate, map.offset, '->', outfile, (map.dimensions.x, map.dimensions.y))

    map.draw(False).save(outfile)
