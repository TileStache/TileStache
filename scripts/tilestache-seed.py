#!/usr/bin/env python
"""tilestache-seed.py will warm your cache.

This script is intended to be run directly. This example seeds the area around
West Oakland (http://sta.mn/ck) in the "osm" layer, for zoom levels 12-15:

    tilestache-seed.py -c ./config.json -l osm -b 37.79 -122.35 37.83 -122.25 -e png 12 13 14 15

See `tilestache-seed.py --help` for more information.
"""

from sys import stderr, path
from optparse import OptionParser

try:
    from json import dump as json_dump
except ImportError:
    from simplejson import dump as json_dump

#
# Most imports can be found below, after the --include-path option is known.
#

parser = OptionParser(usage="""%prog [options] [zoom...]

Seeds a single layer in your TileStache configuration - no images are returned,
but TileStache ends up with a pre-filled cache. Bounding box is given as a pair
of lat/lon coordinates, e.g. "37.788 -122.349 37.833 -122.246". Output is a list
of tile paths as they are created.

Configuration, bbox, and layer options are required; see `%prog --help` for info.""")

defaults = dict(extension='png', padding=0, verbose=True, bbox=(37.777, -122.352, 37.839, -122.226), retries=False, graceful=False)

parser.set_defaults(**defaults)

parser.add_option('-c', '--config', dest='config',
                  help='Path to configuration file.')

parser.add_option('-l', '--layer', dest='layer',
                  help='Layer name from configuration.')

parser.add_option('-b', '--bbox', dest='bbox',
                  help='Bounding box in floating point geographic coordinates: south west north east.',
                  type='float', nargs=4)

parser.add_option('-p', '--padding', dest='padding',
                  help='Extra margin of tiles to add around bounded area. Default value is %s (no extra tiles).' % repr(defaults['padding']),
                  type='int')

parser.add_option('-e', '--extension', dest='extension',
                  help='Optional file type for rendered tiles. Default value is %s.' % repr(defaults['extension']))

parser.add_option('-f', '--progress-file', dest='progressfile',
                  help="Optional JSON progress file that gets written on each iteration, so you don't have to pay close attention.")

parser.add_option('-q', action='store_false', dest='verbose',
                  help='Suppress chatty output, --progress-file works well with this.')

parser.add_option('-i', '--include-path', dest='include',
                  help="Add the following colon-separated list of paths to Python's include path (aka sys.path)")

parser.add_option('-d', '--output-directory', dest='outputdirectory',
                  help='Optional output directory for tiles, to override configured cache with the equivalent of: {"name": "Disk", "path": <output directory>, "dirs": "portable", "gzip": []}. More information in http://tilestache.org/doc/#caches.')

parser.add_option('--to-mbtiles', dest='mbtiles_output',
                  help='Optional output file for tiles, will be created as an MBTiles 1.1 tileset. See http://mbtiles.org for more information.')

parser.add_option('--tile-list', dest='tile_list',
                  help='Optional file of tile coordinates, a simple text list of Z/X/Y coordinates. Overrides --bbox and --padding.')

parser.add_option('--enable-retries', dest='enable_retries', action='store_true', default=False,
                  help='If true this will cause tilestache-seed to retry failed tile renderings up to (3) times. Default value is %s.' % repr(defaults['retries']))

parser.add_option('--fail-gracefully', dest='fail_gracefully', action='store_true', default=False,
                  help='If true tilestache-seed will not throw a fatal exception if a tile fails to render. Instead it will write the tile to a log file and try to render the next tile. The log file is named "failed-{LAYER NAME}.log" and is written in such a way that it can (later) be passed to the --tile-list argument. Default value is %s.' % repr(defaults['graceful']))

parser.add_option('-x', '--ignore-cached', action='store_true', dest='ignore_cached',
                  help='Re-render every tile, whether it is in the cache already or not.')

def generateCoordinates(ul, lr, zooms, padding):
    """ Generate a stream of (offset, count, coordinate) tuples for seeding.

        Flood-fill coordinates based on two corners, a list of zooms and padding.
    """
    # start with a simple total of all the coordinates we will need.
    count = 0

    for zoom in zooms:
        ul_ = ul.zoomTo(zoom).container().left(padding).up(padding)
        lr_ = lr.zoomTo(zoom).container().right(padding).down(padding)

        rows = lr_.row + 1 - ul_.row
        cols = lr_.column + 1 - ul_.column

        count += int(rows * cols)

    # now generate the actual coordinates.
    # offset starts at zero
    offset = 0

    for zoom in zooms:
        ul_ = ul.zoomTo(zoom).container().left(padding).up(padding)
        lr_ = lr.zoomTo(zoom).container().right(padding).down(padding)

        for row in range(int(ul_.row), int(lr_.row + 1)):
            for column in range(int(ul_.column), int(lr_.column + 1)):
                coord = Coordinate(row, column, zoom)

                yield (offset, count, coord)

                offset += 1

def listCoordinates(filename):
    """ Generate a stream of (offset, count, coordinate) tuples for seeding.

        Read coordinates from a file with one Z/X/Y coordinate per line.
    """
    coords = (line.strip().split('/') for line in open(filename, 'r'))
    coords = (map(int, (row, column, zoom)) for (zoom, column, row) in coords)
    coords = [Coordinate(*args) for args in coords]

    count = len(coords)

    for (offset, coord) in enumerate(coords):
        yield (offset, count, coord)

if __name__ == '__main__':
    options, zooms = parser.parse_args()

    if options.include:
        for p in options.include.split(':'):
            path.insert(0, p)

    from TileStache import parseConfigfile, getTile
    from TileStache.Core import KnownUnknown
    from TileStache.Caches import Disk, Multi
    from TileStache import MBTiles

    from ModestMaps.Core import Coordinate
    from ModestMaps.Geo import Location

    try:
        if options.config is None:
            raise KnownUnknown('Missing required configuration (--config) parameter.')

        if options.layer is None:
            raise KnownUnknown('Missing required layer (--layer) parameter.')

        config = parseConfigfile(options.config)

        if options.layer not in config.layers:
            raise KnownUnknown('"%s" is not a layer I know about. Here are some that I do know about: %s.' % (options.layer, ', '.join(sorted(config.layers.keys()))))

        layer = config.layers[options.layer]

        verbose = options.verbose
        extension = options.extension
        progressfile = options.progressfile

        if options.outputdirectory and options.mbtiles_output:
            cache1 = Disk(options.outputdirectory, dirs='portable', gzip=[])
            cache2 = MBTiles.Cache(options.mbtiles_output, extension, options.layer)
            config.cache = Multi([cache1, cache2])

        elif options.outputdirectory:
            config.cache = Disk(options.outputdirectory, dirs='portable', gzip=[])

        elif options.mbtiles_output:
            config.cache = MBTiles.Cache(options.mbtiles_output, extension, options.layer)

        lat1, lon1, lat2, lon2 = options.bbox
        south, west = min(lat1, lat2), min(lon1, lon2)
        north, east = max(lat1, lat2), max(lon1, lon2)

        northwest = Location(north, west)
        southeast = Location(south, east)

        ul = layer.projection.locationCoordinate(northwest)
        lr = layer.projection.locationCoordinate(southeast)

        for (i, zoom) in enumerate(zooms):
            if not zoom.isdigit():
                raise KnownUnknown('"%s" is not a valid numeric zoom level.' % zoom)

            zooms[i] = int(zoom)

        if options.padding < 0:
            raise KnownUnknown('A negative padding will not work.')

        padding = options.padding
        tile_list = options.tile_list

    except KnownUnknown, e:
        parser.error(str(e))

    if tile_list:
        coordinates = listCoordinates(tile_list)
    else:
        coordinates = generateCoordinates(ul, lr, zooms, padding)

    for (offset, count, coord) in coordinates:
        path = '%s/%d/%d/%d.%s' % (layer.name(), coord.zoom, coord.column, coord.row, extension)

        progress = {"tile": path,
                    "offset": offset + 1,
                    "total": count}

        if options.verbose:
            print >> stderr, '%(offset)d of %(total)d...' % progress,

        # Now we fetch a tile.

        max_tries = 3
        tries = 0
        ok = False

        while not ok:

            try:

                # See this? This is where we fetch the tile. Just
                # about everything below is error-handling...

                mimetype, content = getTile(layer, coord, extension, options.ignore_cached)
                progress['size'] = '%dKB' % (len(content) / 1024)
                ok = True

            except Exception, e:

                # Plain old tilestache-seed, something went wrong
                # so just stop until we can fix the problem

                if not options.enable_retries and not options.fail_gracefully:
                    raise Exception, e

                failed_log = "failed-%s.log" % options.layer

                # Something went wrong, but we are not going to
                # retry. Instead we're just going to write to a log
                # file and carry on.

                if not options.enable_retries and options.fail_gracefully:

                    fh = open(failed_log, 'a')
                    fh.write("%s/%s/%s\n" % (coord.zoom, coord.column, coord.row))
                    fh.close()
                    break

                # Something went wrong but we *are* going to retry to
                # render the tile (up to 'max_tries' times).

                tries += 1

                if options.verbose:
                    print >> stderr, "tile rendering failed (%s of %s attempts) : %s" % (tries, max_tries, e)

                # Okay, just give up. The tile will not render so now
                # the only question is whether we throw a fatal error
                # or just move on to the next tile.

                if tries >= max_tries:

                    if not options.fail_gracefully:
                        raise Exception, "Failed to render tiles"

                    fh = open(failed_log, 'a')
                    fh.write("%s/%s/%s\n" % (coord.zoom, coord.column, coord.row))
                    fh.close()
                    break

        if options.verbose and ok:
            print >> stderr, '%(tile)s (%(size)s)' % progress

        if progressfile:
            fp = open(progressfile, 'w')
            json_dump(progress, fp)
            fp.close()
