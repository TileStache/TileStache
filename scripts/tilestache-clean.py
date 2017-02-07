#!/usr/bin/env python
"""tilestache-clean.py will flush your cache.

This script is intended to be run directly. This example cleans the area around
West Oakland (http://sta.mn/ck) in the "osm" layer, for zoom levels 12-15:

    tilestache-clean.py -c ./config.json -l osm -b 37.79 -122.35 37.83 -122.25 -e png 12 13 14 15

See `tilestache-clean.py --help` for more information.
"""
from __future__ import print_function

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

Cleans a single layer in your TileStache configuration - no images are returned,
and TileStache ends up with an empty in selected areas cache. Bounding box is
given as a pair of lat/lon coordinates, e.g. "37.788 -122.349 37.833 -122.246".
Output is a list of tile paths as they are created.

Configuration, bbox, and layer options are required; see `%prog --help` for info.""")

defaults = dict(extension='png', padding=0, verbose=True, bbox=(37.777, -122.352, 37.839, -122.226))

parser.set_defaults(**defaults)

parser.add_option('-c', '--config', dest='config',
                  help='Path to configuration file.')

parser.add_option('-l', '--layer', dest='layer',
                  help='Layer name from configuration. "ALL" is a special value that will clean all layers in turn. If you have an actual layer named "ALL", use "ALL LAYERS" instead.')

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

parser.add_option('--tile-list', dest='tile_list',
                  help='Optional file of tile coordinates, a simple text list of Z/X/Y coordinates. Overrides --bbox and --padding.')

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

    from TileStache import parseConfig, getTile
    from TileStache.Core import KnownUnknown
    from TileStache.Caches import Disk, Multi

    from ModestMaps.Core import Coordinate
    from ModestMaps.Geo import Location

    try:
        if options.config is None:
            raise KnownUnknown('Missing required configuration (--config) parameter.')

        if options.layer is None:
            raise KnownUnknown('Missing required layer (--layer) parameter.')

        config = parseConfig(options.config)

        if options.layer in ('ALL', 'ALL LAYERS') and options.layer not in config.layers:
            # clean every layer in the config
            layers = config.layers.values()

        elif options.layer not in config.layers:
            raise KnownUnknown('"%s" is not a layer I know about. Here are some that I do know about: %s.' % (options.layer, ', '.join(sorted(config.layers.keys()))))

        else:
            # clean just one layer in the config
            layers = [config.layers[options.layer]]

        verbose = options.verbose
        extension = options.extension
        progressfile = options.progressfile

        lat1, lon1, lat2, lon2 = options.bbox
        south, west = min(lat1, lat2), min(lon1, lon2)
        north, east = max(lat1, lat2), max(lon1, lon2)

        northwest = Location(north, west)
        southeast = Location(south, east)

        for (i, zoom) in enumerate(zooms):
            if not zoom.isdigit():
                raise KnownUnknown('"%s" is not a valid numeric zoom level.' % zoom)

            zooms[i] = int(zoom)

        if options.padding < 0:
            raise KnownUnknown('A negative padding will not work.')

        padding = options.padding
        tile_list = options.tile_list

    except KnownUnknown as e:
        parser.error(str(e))

    for layer in layers:

        if tile_list:
            coordinates = listCoordinates(tile_list)
        else:
            ul = layer.projection.locationCoordinate(northwest)
            lr = layer.projection.locationCoordinate(southeast)

            coordinates = generateCoordinates(ul, lr, zooms, padding)

        for (offset, count, coord) in coordinates:
            path = '%s/%d/%d/%d.%s' % (layer.name(), coord.zoom, coord.column, coord.row, extension)

            progress = {"tile": path,
                        "offset": offset + 1,
                        "total": count}

            if options.verbose:
                print('%(offset)d of %(total)d...' % progress, end=' ', file=stderr)

            try:
                mimetype, format = layer.getTypeByExtension(extension)
            except:
                #
                # It's not uncommon for layers to lack support for certain
                # extensions, so just don't attempt to remove a cached tile
                # for an unsupported format.
                #
                pass
            else:
                config.cache.remove(layer, coord, format)

            if options.verbose:
                print('%(tile)s' % progress, file=stderr)

            if progressfile:
                fp = open(progressfile, 'w')
                json_dump(progress, fp)
                fp.close()
