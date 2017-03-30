#!/usr/bin/env python
"""tilestache-seed.py will warm your cache.

This script is intended to be run directly. This example seeds the area around
West Oakland (http://sta.mn/ck) in the "osm" layer, for zoom levels 12-15:

    tilestache-seed.py -c ./config.json -l osm -b 37.79 -122.35 37.83 -122.25 -e png 12 13 14 15

See `tilestache-seed.py --help` for more information.
"""
from __future__ import print_function

from sys import stderr, path, version
from os.path import realpath, dirname
from optparse import OptionParser

try:
    from urllib.parse import urlparse
    from urllib.request import urlopen
except ImportError:
    from urlparse import urlparse
    from urllib import urlopen

try:
    from json import dump as json_dump
    from json import load as json_load
except ImportError:
    from simplejson import dump as json_dump
    from simplejson import load as json_load


PY2 = bool(version.startswith('2.'))

#
# Most imports can be found below, after the --include-path option is known.
#

parser = OptionParser(usage="""%prog [options] [zoom...]

Seeds a single layer in your TileStache configuration - no images are returned,
but TileStache ends up with a pre-filled cache. Bounding box is given as a pair
of lat/lon coordinates, e.g. "37.788 -122.349 37.833 -122.246". Output is a list
of tile paths as they are created.

Example:

    tilestache-seed.py -b 52.55 13.28 52.46 13.51 -c tilestache.cfg -l osm 11 12 13

Protip: extract tiles from an MBTiles tileset to a directory like this:

    tilestache-seed.py --from-mbtiles filename.mbtiles --output-directory dirname

Configuration, bbox, and layer options are required; see `%prog --help` for info.""")

defaults = dict(padding=0, verbose=True, enable_retries=False, bbox=(37.777, -122.352, 37.839, -122.226))

parser.set_defaults(**defaults)

parser.add_option('-c', '--config', dest='config',
                  help='Path to configuration file, typically required.')

parser.add_option('-l', '--layer', dest='layer',
                  help='Layer name from configuration, typically required.')

parser.add_option('-b', '--bbox', dest='bbox',
                  help='Bounding box in floating point geographic coordinates: south west north east. Default value is %.7f, %.7f, %.7f, %.7f.' % defaults['bbox'],
                  type='float', nargs=4)

parser.add_option('-p', '--padding', dest='padding',
                  help='Extra margin of tiles to add around bounded area. Default value is %s (no extra tiles).' % repr(defaults['padding']),
                  type='int')

parser.add_option('-e', '--extension', dest='extension',
                  help='Optional file type for rendered tiles. Default value is "png" for most image layers and some variety of JSON for Vector or Mapnik Grid providers.')

parser.add_option('-f', '--progress-file', dest='progressfile',
                  help="Optional JSON progress file that gets written on each iteration, so you don't have to pay close attention.")

parser.add_option('-q', action='store_false', dest='verbose',
                  help='Suppress chatty output, --progress-file works well with this.')

parser.add_option('-i', '--include-path', dest='include_paths',
                  help="Add the following colon-separated list of paths to Python's include path (aka sys.path)")

parser.add_option('-d', '--output-directory', dest='outputdirectory',
                  help='Optional output directory for tiles, to override configured cache with the equivalent of: {"name": "Disk", "path": <output directory>, "dirs": "portable", "gzip": []}. More information in http://tilestache.org/doc/#caches.')

parser.add_option('--to-mbtiles', dest='mbtiles_output',
                  help='Optional output file for tiles, will be created as an MBTiles 1.1 tileset. See http://mbtiles.org for more information.')

parser.add_option('--to-s3', dest='s3_output',
                  help='Optional output bucket for tiles, will be populated with tiles in a standard Z/X/Y layout. Three required arguments: AWS access-key, secret, and bucket name.',
                  nargs=3)

parser.add_option('--from-mbtiles', dest='mbtiles_input',
                  help='Optional input file for tiles, will be read as an MBTiles 1.1 tileset. See http://mbtiles.org for more information. Overrides --extension, --bbox and --padding (this may change).')

parser.add_option('--tile-list', dest='tile_list',
                  help='Optional file of tile coordinates, a simple text list of Z/X/Y coordinates. Overrides --bbox and --padding.')

parser.add_option('--error-list', dest='error_list',
                  help='Optional file of failed tile coordinates, a simple text list of Z/X/Y coordinates. If provided, failed tiles will be logged to this file instead of stopping tilestache-seed.')

parser.add_option('--enable-retries', dest='enable_retries',
                  help='If true this will cause tilestache-seed to retry failed tile renderings up to (3) times. Default value is %s.' % repr(defaults['enable_retries']),
                  action='store_true')

parser.add_option('-x', '--ignore-cached', action='store_true', dest='ignore_cached',
                  help='Re-render every tile, whether it is in the cache already or not.')

parser.add_option('--jsonp-callback', dest='callback',
                  help='Add a JSONP callback for tiles with a json mime-type, causing "*.js" tiles to be written to the cache wrapped in the callback function. Ignored for non-JSON tiles.')

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

        range_ = xrange if PY2 else range

        for row in range_(int(ul_.row), int(lr_.row + 1)):
            for column in range_(int(ul_.column), int(lr_.column + 1)):
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

def tilesetCoordinates(filename):
    """ Generate a stream of (offset, count, coordinate) tuples for seeding.

        Read coordinates from an MBTiles tileset filename.
    """
    coords = MBTiles.list_tiles(filename)
    count = len(coords)

    for (offset, coord) in enumerate(coords):
        yield (offset, count, coord)

def parseConfig(configpath):
    """ Parse a configuration file and return a raw dictionary and dirpath.

        Return value can be passed to TileStache.Config.buildConfiguration().
    """
    if urlparse(configpath).scheme in ('', 'file'):
        with open(urlparse(configpath).path) as file:
            config_dict = json_load(file)
    else:
        config_dict = json_load(urlopen(configpath))

    scheme, host, path, p, q, f = urlparse(configpath)

    if scheme == '':
        scheme = 'file'
        path = realpath(path)

    dirpath = '%s://%s%s' % (scheme, host, dirname(path).rstrip('/') + '/')

    return config_dict, dirpath

if __name__ == '__main__':
    options, zooms = parser.parse_args()

    if options.include_paths:
        for p in options.include_paths.split(':'):
            path.insert(0, p)

    from TileStache import getTile, Config
    from TileStache.Core import KnownUnknown
    from TileStache.Config import buildConfiguration
    from TileStache import MBTiles
    import TileStache

    from ModestMaps.Core import Coordinate
    from ModestMaps.Geo import Location

    try:
        # determine if we have enough information to prep a config and layer

        has_fake_destination = bool(options.outputdirectory or options.mbtiles_output)
        has_fake_source = bool(options.mbtiles_input)

        if has_fake_destination and has_fake_source:
            config_dict, config_dirpath = dict(layers={}), '' # parseConfig(options.config)
            layer_dict = dict()

            config_dict['cache'] = dict(name='test')
            config_dict['layers'][options.layer or 'tiles-layer'] = layer_dict

        elif options.config is None:
            raise KnownUnknown('Missing required configuration (--config) parameter.')

        elif options.layer is None:
            raise KnownUnknown('Missing required layer (--layer) parameter.')

        else:
            config_dict, config_dirpath = parseConfig(options.config)

            if options.layer not in config_dict['layers']:
                raise KnownUnknown('"%s" is not a layer I know about. Here are some that I do know about: %s.' % (options.layer, ', '.join(sorted(config_dict['layers'].keys()))))

            layer_dict = config_dict['layers'][options.layer]
            layer_dict['write_cache'] = True # Override to make seeding guaranteed useful.

        # override parts of the config and layer if needed

        extension = options.extension

        if options.mbtiles_input:
            layer_dict['provider'] = dict(name='mbtiles', tileset=options.mbtiles_input)
            n, t, v, d, format, b = MBTiles.tileset_info(options.mbtiles_input)
            extension = format or extension

        # determine or guess an appropriate tile extension

        if extension is None:
            provider_name = layer_dict['provider'].get('name', '').lower()

            if provider_name == 'mapnik grid':
                extension = 'json'
            elif provider_name == 'vector':
                extension = 'geojson'
            else:
                extension = 'png'

        # override parts of the config and layer if needed

        tiers = []

        if options.mbtiles_output:
            tiers.append({'class': 'TileStache.MBTiles:Cache',
                          'kwargs': dict(filename=options.mbtiles_output,
                                         format=extension,
                                         name=options.layer)})

        if options.outputdirectory:
            tiers.append(dict(name='disk', path=options.outputdirectory,
                              dirs='portable', gzip=[]))

        if options.s3_output:
            access, secret, bucket = options.s3_output
            tiers.append(dict(name='S3', bucket=bucket,
                              access=access, secret=secret))

        if len(tiers) > 1:
            config_dict['cache'] = dict(name='multi', tiers=tiers)
        elif len(tiers) == 1:
            config_dict['cache'] = tiers[0]
        else:
            # Leave config_dict['cache'] as-is
            pass

        # create a real config object

        config = buildConfiguration(config_dict, config_dirpath)
        layer = config.layers[options.layer or 'tiles-layer']

        # do the actual work

        lat1, lon1, lat2, lon2 = options.bbox
        south, west = min(lat1, lat2), min(lon1, lon2)
        north, east = max(lat1, lat2), max(lon1, lon2)

        if not (-90.0 < south < 90.0) or not (-90.0 < north < 90.0):
            raise KnownUnknown(
                'Latitude must be a value between -90 and 90 '
                '(Hint: Maybe you did long/lat instead of lat/long?).'
            )
        if not (-180.0 < west < 180.0) or not (-180.0 < east < 180.0):
            raise KnownUnknown(
                'Longitude must be a value between -180 and 180.'
            )

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
        error_list = options.error_list

    except KnownUnknown as e:
        parser.error(str(e))

    if tile_list:
        coordinates = listCoordinates(tile_list)
    elif options.mbtiles_input:
        coordinates = tilesetCoordinates(options.mbtiles_input)
    else:
        coordinates = generateCoordinates(ul, lr, zooms, padding)

    for (offset, count, coord) in coordinates:
        path = '%s/%d/%d/%d.%s' % (layer.name(), coord.zoom, coord.column, coord.row, extension)

        progress = {"tile": path,
                    "offset": offset + 1,
                    "total": count}

        #
        # Fetch a tile.
        #

        attempts = options.enable_retries and 3 or 1
        rendered = False

        while not rendered:
            if options.verbose:
                print('%(offset)d of %(total)d...' % progress, end=' ', file=stderr)

            try:
                mimetype, content = getTile(layer, coord, extension, options.ignore_cached)

                if mimetype and 'json' in mimetype and options.callback:
                    js_path = '%s/%d/%d/%d.js' % (layer.name(), coord.zoom, coord.column, coord.row)
                    js_body = '%s(%s);' % (options.callback, content)
                    js_size = len(js_body) / 1024

                    layer.config.cache.save(js_body, layer, coord, 'JS')
                    print('%s (%dKB)' % (js_path, js_size), end=' ', file=stderr)

                elif options.callback:
                    print('(callback ignored)', end=' ', file=stderr)

            except:
                #
                # Something went wrong: try again? Log the error?
                #
                attempts -= 1

                if options.verbose:
                    print('Failed %s, will try %s more.' % (progress['tile'], ['no', 'once', 'twice'][attempts]), file=stderr)

                if attempts == 0:
                    if not error_list:
                        raise

                    fp = open(error_list, 'a')
                    fp.write('%(zoom)d/%(column)d/%(row)d\n' % coord.__dict__)
                    fp.close()
                    break

            else:
                #
                # Successfully got the tile.
                #
                rendered = True
                progress['size'] = '%dKB' % (len(content) / 1024)

                if options.verbose:
                    print('%(tile)s (%(size)s)' % progress, file=stderr)

        if options.progressfile:
            fp = open(options.progressfile, 'w')
            json_dump(progress, fp)
            fp.close()
