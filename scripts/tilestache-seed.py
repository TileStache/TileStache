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

from TileStache import parseConfigfile, handleRequest
from TileStache.Core import KnownUnknown

from ModestMaps.Core import Coordinate
from ModestMaps.Geo import Location

parser = OptionParser(usage="""%prog [options] [zoom...]

Seeds a single layer in your TileStache configuration - no images are returned,
but TileStache ends up with a pre-filled cache. Bounding box is given as a pair
of lat/lon coordinates, e.g. "37.788 -122.349 37.833 -122.246". Output is a list
of tile paths as they are created.

Configuration, bbox, and layer options are required; see `%prog --help` for info.""")

parser.set_defaults(extension='png', verbose=True)

parser.add_option('-c', '--config', dest='config',
                  help='Path to configuration file.')

parser.add_option('-l', '--layer', dest='layer',
                  help='Layer name from configuration.')

parser.add_option('-b', '--bbox', dest='bbox',
                  help='Bounding box in floating point geographic coordinates: south west north east.',
                  type='float', nargs=4)

parser.add_option('-e', '--extension', dest='extension',
                  help='Optional file type for rendered tiles. Default value is "png".')

parser.add_option('-p', '--progress-file', dest='progressfile',
                  help="Optional JSON progress file that gets written on each iteration, so you don't have to pay close attention.")

parser.add_option('-q', action='store_false', dest='verbose',
                  help='Suppress chatty output, --progress-file works well with this.')

parser.add_option('-i', '--include-path', dest='include',
                  help="Add the following colon-separated list of paths to Python's include path (aka sys.path)")

if __name__ == '__main__':
    options, zooms = parser.parse_args()

    if options.include:

        for p in options.include.split(':'):
            path.insert(0, p)

    try:
        if options.config is None:
            raise KnownUnknown('Missing required configuration (--config) parameter.')

        if options.layer is None:
            raise KnownUnknown('Missing required layer (--layer) parameter.')

        config = parseConfigfile(options.config)

        if options.layer not in config.layers:
            raise KnownUnknown('"%s" is not a layer I know about. Here are some that I do know about: %s.' % (options.layer, ', '.join(config.layers.keys())))

        layer = config.layers[options.layer]

        verbose = options.verbose
        extension = options.extension
        progressfile = options.progressfile

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

    except KnownUnknown, e:
        parser.error(str(e))

    # this list might get long, but we want to know how many
    # total tiles there are to render so progress can be shown.
    coords = []

    for zoom in zooms:
        ul_ = ul.zoomTo(zoom).container()
        lr_ = lr.zoomTo(zoom).container()

        for row in range(int(ul_.row), int(lr_.row + 1)):
            for column in range(int(ul_.column), int(lr_.column + 1)):
                coord = Coordinate(row, column, zoom)
                coords.append(coord)

    for (i, coord) in enumerate(coords):
        path = '%s/%d/%d/%d.%s' % (layer.name(), coord.zoom, coord.column, coord.row, extension)

        progress = {"tile": path,
                    "offset": i + 1,
                    "total": len(coords)}

        if options.verbose:
            print >> stderr, '%(offset)d of %(total)d...' % progress,

        mimetype, content = handleRequest(layer, coord, extension)
        progress['size'] = '%dKB' % (len(content) / 1024)

        if options.verbose:
            print >> stderr, '%(tile)s (%(size)s)' % progress

        if progressfile:
            fp = open(progressfile, 'w')
            json_dump(progress, fp)
            fp.close()
