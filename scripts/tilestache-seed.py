#!/usr/bin/env python

from sys import stderr
from optparse import OptionParser

from TileStache import parseConfigfile, handleRequest
from TileStache.Core import KnownUnknown

from ModestMaps.Core import Coordinate
from ModestMaps.Geo import Location

parser = OptionParser(usage="""%prog [options] [zoom...]

Configuration and layer options are required; see `%prog --help` for info.

""")

parser.set_defaults(extension='png')

parser.add_option('-c', '--config', dest='config',
                  help='Path to configuration file.')

parser.add_option('-l', '--layer', dest='layer',
                  help='Layer name from configuration.')

parser.add_option('-b', '--bbox', dest='bbox',
                  help='Bounding box in floating point geographic coordinates: west south east north.',
                  type='float', nargs=4)

parser.add_option('-e', '--extension', dest='extension',
                  help='Optional file type for rendered tiles. Default value is "png".')

if __name__ == '__main__':
    options, zooms = parser.parse_args()
    
    try:
        if options.config is None:
            raise KnownUnknown('Missing required configuration (--config) parameter.')
    
        if options.layer is None:
            raise KnownUnknown('Missing required layer (--layer) parameter.')
    
        config = parseConfigfile(options.config)
        
        if options.layer not in config.layers:
            raise KnownUnknown('"%s" is not a layer I know about. Here are some that I do know about: %s.' % (options.layer, ', '.join(config.layers.keys())))
        
        layer = config.layers[options.layer]
        
        extension = options.extension
        west, south, east, north = options.bbox
        
        northwest = Location(north, west)
        southeast = Location(south, east)
        
        ul = layer.projection.locationCoordinate(northwest)
        lr = layer.projection.locationCoordinate(southeast)

    except KnownUnknown, e:
        parser.error(str(e))
    
    coords = []
    
    for zoom in zooms:
        if not zoom.isdigit():
            raise KnownUnknown('"%s" is not a valid numeric zoom level.' % zoom)

        zoom = int(zoom)
        
        ul_ = ul.zoomTo(zoom).container()
        lr_ = lr.zoomTo(zoom).container()
        
        for row in range(int(ul_.row), int(lr_.row + 1)):
            for column in range(int(ul_.column), int(lr_.column + 1)):
                coord = Coordinate(row, column, zoom)
                coords.append(coord)
    
    for (i, coord) in enumerate(coords):
        print >> stderr, '%d of %d...' % (i + 1, len(coords)),
    
        mimetype, content = handleRequest(layer, coord, extension)
        path = '%s/%d/%d/%d.%s' % (layer.name(), coord.zoom, coord.column, coord.row, extension)
        
        print >> stderr, '%s (%dKB)' % (path, len(content) / 1024)
