#!/usr/bin/env python
"""tilestache-list.py will list your tiles.

This script is intended to be run directly. This example lists tiles in the area
around West Oakland (http://sta.mn/ck) in the "osm" layer, for zoom levels 12-15:

    tilestache-list.py -b 37.79 -122.35 37.83 -122.25 12 13 14 15

See `tilestache-list.py --help` for more information.
"""

from sys import stderr, path
from optparse import OptionParser

from TileStache.Core import KnownUnknown
from TileStache import MBTiles

from ModestMaps.Core import Coordinate
from ModestMaps.Geo import Location
from ModestMaps.OpenStreetMap import Provider

parser = OptionParser(usage="""%prog [options] [zoom...]

Generates a list of tiles based on geographic or other criteria. No images are
created and no Tilestache configuration is read, but a list of tile coordinates
in Z/X/Y form compatible with `tilestache-seed --tile-list` is output.

Example:

    tilestache-list.py -b 52.55 13.28 52.46 13.51 11 12 13

Protip: seed a cache in parallel on 8 CPUs with split and xargs like this:

    tilestache-list.py 12 13 14 15 | split -l 20 - tiles/list-
    ls -1 tiles/list-* | xargs -n1 -P8 tilestache-seed.py -c tilestache.cfg -l osm --tile-list

See `%prog --help` for info.""")

defaults = dict(padding=0, bbox=(37.777, -122.352, 37.839, -122.226))

parser.set_defaults(**defaults)

parser.add_option('-b', '--bbox', dest='bbox',
                  help='Bounding box in floating point geographic coordinates: south west north east. Default value is %.7f, %.7f, %.7f, %.7f.' % defaults['bbox'],
                  type='float', nargs=4)

parser.add_option('-p', '--padding', dest='padding',
                  help='Extra margin of tiles to add around bounded area. Default value is %s (no extra tiles).' % repr(defaults['padding']),
                  type='int')

parser.add_option('--from-mbtiles', dest='mbtiles_input',
                  help='Optional input file for tiles, will be read as an MBTiles 1.1 tileset. See http://mbtiles.org for more information. Overrides --bbox and --padding.')

def generateCoordinates(ul, lr, zooms, padding):
    """ Generate a stream of coordinates for seeding.
    
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
                
                yield coord
                offset += 1

def tilesetCoordinates(filename):
    """ Generate a stream of (offset, count, coordinate) tuples for seeding.
    
        Read coordinates from an MBTiles tileset filename.
    """
    coords = MBTiles.list_tiles(filename)
    count = len(coords)
    
    for (offset, coord) in enumerate(coords):
        yield coord

if __name__ == '__main__':
    options, zooms = parser.parse_args()

    if bool(options.mbtiles_input):
        coordinates = MBTiles.list_tiles(options.mbtiles_input)

    else:
        lat1, lon1, lat2, lon2 = options.bbox
        south, west = min(lat1, lat2), min(lon1, lon2)
        north, east = max(lat1, lat2), max(lon1, lon2)

        northwest = Location(north, west)
        southeast = Location(south, east)
        
        osm = Provider()

        ul = osm.locationCoordinate(northwest)
        lr = osm.locationCoordinate(southeast)

        for (i, zoom) in enumerate(zooms):
            if not zoom.isdigit():
                raise KnownUnknown('"%s" is not a valid numeric zoom level.' % zoom)

            zooms[i] = int(zoom)
        
        if options.padding < 0:
            raise KnownUnknown('A negative padding will not work.')

        coordinates = generateCoordinates(ul, lr, zooms, options.padding)
    
    for coord in coordinates:
        print '%(zoom)d/%(column)d/%(row)d' % coord.__dict__
