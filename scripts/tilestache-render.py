#!/usr/bin/env python

import re
import os
from tempfile import mkstemp
from optparse import OptionParser

from TileStache import parseConfigfile, handleRequest
from TileStache.Core import KnownUnknown

from ModestMaps.Core import Coordinate

parser = OptionParser(usage="""%prog [options] [coord...]

Configuration and layer options are required; see `%prog --help` for info.

Each coordinate in the argument list should look like "12/656/1582.png", similar
to URL paths in web server usage. Coordinates are processed in order, each one
rendered to an image file in a temporary location and output to stdout in order.""")

parser.add_option('-c', '--config', dest='config',
                  help='Path to configuration file.')

parser.add_option('-l', '--layer', dest='layer',
                  help='Layer name from configuration.')

if __name__ == '__main__':
    try:
        pathinfo_pat = re.compile(r'^(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)\.(?P<e>\w+)$')
    
        options, paths = parser.parse_args()
        
        if options.config is None:
            raise KnownUnknown('Missing required configuration (--config) parameter.')
    
        if options.layer is None:
            raise KnownUnknown('Missing required layer (--layer) parameter.')
    
        config = parseConfigfile(options.config)
        
        if options.layer not in config.layers:
            raise KnownUnknown('"%s" is not a layer I know about. Here are some that I do know about: %s.' % (options.layer, ', '.join(config.layers.keys())))
        
        layer = config.layers[options.layer]
        
        for path in paths:
            # prepare
            path = pathinfo_pat.match(path)
            row, column, zoom, extension = [path.group(p) for p in 'yxze']
            coord = Coordinate(int(row), int(column), int(zoom))
            
            # render
            mimetype, content = handleRequest(layer, coord, extension)
            
            # save
            handle, filename = mkstemp(prefix='tile-', suffix='.'+extension)
            os.write(handle, content)
            os.close(handle)
            
            # inform
            print filename

    except KnownUnknown, e:
        parser.error(str(e))
