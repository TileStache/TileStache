#!/usr/bin/env python
"""tilestache-render.py will warm your cache.

This script is *deprecated* and will be removed in a future TileStache 2.0.

This script is intended to be run directly. This example will save two tiles
for San Francisco and Oakland to local temporary files:

    tilestache-render.py -c ./config.json -l osm 12/655/1582.png 12/656/1582.png

Output for this sample might look like this:

    /tmp/tile-_G3uHX.png
    /tmp/tile-pWNfQQ.png

...where each line corresponds to one of the given coordinates, in order.
You are expected to use these files and then dispose of them.

See `tilestache-render.py --help` for more information.
"""
from __future__ import print_function

import re
import os
from tempfile import mkstemp
from optparse import OptionParser

from TileStache import parseConfig, getTile
from TileStache.Core import KnownUnknown

from ModestMaps.Core import Coordinate

parser = OptionParser(usage="""%prog [options] [coord...]

Each coordinate in the argument list should look like "12/656/1582.png", similar
to URL paths in web server usage. Coordinates are processed in order, each one
rendered to an image file in a temporary location and output to stdout in order.

Configuration and layer options are required; see `%prog --help` for info.""")

parser.add_option('-c', '--config', dest='config',
                  help='Path to configuration file.')

parser.add_option('-l', '--layer', dest='layer',
                  help='Layer name from configuration.')

pathinfo_pat = re.compile(r'^(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)\.(?P<e>\w+)$')

if __name__ == '__main__':
    options, paths = parser.parse_args()

    try:
        if options.config is None:
            raise KnownUnknown('Missing required configuration (--config) parameter.')

        if options.layer is None:
            raise KnownUnknown('Missing required layer (--layer) parameter.')

        config = parseConfig(options.config)

        if options.layer not in config.layers:
            raise KnownUnknown('"%s" is not a layer I know about. Here are some that I do know about: %s.' % (options.layer, ', '.join(sorted(config.layers.keys()))))

        layer = config.layers[options.layer]

        coords = []

        for path in paths:
            path_ = pathinfo_pat.match(path)

            if path_ is None:
                raise KnownUnknown('"%s" is not a path I understand. I was expecting something more like "0/0/0.png".' % path)

            row, column, zoom, extension = [path_.group(p) for p in 'yxze']
            coord = Coordinate(int(row), int(column), int(zoom))

            coords.append(coord)

    except KnownUnknown as e:
        parser.error(str(e))

    for coord in coords:
        # render
        mimetype, content = getTile(layer, coord, extension)

        # save
        handle, filename = mkstemp(prefix='tile-', suffix='.'+extension)
        os.write(handle, content)
        os.close(handle)

        # inform
        print(filename)
