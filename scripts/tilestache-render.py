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

pathinfo_pat = re.compile(r'^(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)\.(?P<e>\w+)$')

if __name__ == '__main__':
    options, paths = parser.parse_args()
    
    try:
        if options.config is None:
            raise KnownUnknown('Missing required configuration (--config) parameter.')
    
        if options.layer is None:
            raise KnownUnknown('Missing required layer (--layer) parameter.')
    
        config = parseConfigfile(options.config)
        
        if options.layer not in config.layers:
            raise KnownUnknown('"%s" is not a layer I know about. Here are some that I do know about: %s.' % (options.layer, ', '.join(config.layers.keys())))
        
        layer = config.layers[options.layer]
        
        coords = []
        
        for path in paths:
            path_ = pathinfo_pat.match(path)
            
            if path_ is None:
                raise KnownUnknown('"%s" is not a path I understand. I was expecting something more like "0/0/0.png".' % path)
            
            row, column, zoom, extension = [path_.group(p) for p in 'yxze']
            coord = Coordinate(int(row), int(column), int(zoom))

            coords.append(coord)

    except KnownUnknown, e:
        parser.error(str(e))
    
    for coord in coords:
        # render
        mimetype, content = handleRequest(layer, coord, extension)
        
        # save
        handle, filename = mkstemp(prefix='tile-', suffix='.'+extension)
        os.write(handle, content)
        os.close(handle)
        
        # inform
        print filename
