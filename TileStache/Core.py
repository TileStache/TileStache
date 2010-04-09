""" The core class bits of TileStache.
"""

from StringIO import StringIO

from ModestMaps.Core import Coordinate

class Metatile:
    """ Some basic characteristics of a metatile.
    
        Properties:
        - rows: number of tile rows this metatile covers vertically.
        - columns: number of tile columns this metatile covers horizontally.
        - buffer: pixel width of outer edge.
    """
    def __init__(self, buffer=0, rows=1, columns=1):
        assert rows >= 1
        assert columns >= 1
        assert buffer >= 0

        self.rows = rows
        self.columns = columns
        self.buffer = buffer

    def isForReal(self):
        """ Return True if this is really a metatile with a buffer or multiple tiles.
        
            A default 1x1 metatile with buffer=0 is not for real.
        """
        return self.buffer > 0 or self.rows > 1 or self.columns > 1

    def firstCoord(self, coord):
        """ Return a new coordinate for the upper-left corner of a metatile.
        """
        return self.allCoords(coord)[0]

    def allCoords(self, coord):
        """ Return a list of coordinates for a complete metatile.
        
            Results are guaranteed to be ordered left-to-right, top-to-bottom.
        """
        rows, columns = int(self.rows), int(self.columns)
        
        # upper-left corner of coord's metatile
        row = rows * (int(coord.row) / rows)
        column = columns * (int(coord.column) / columns)
        
        coords = []
        
        for r in range(rows):
            for c in range(columns):
                coords.append(Coordinate(row + r, column + c, coord.zoom))

        return coords

class Layer:
    """ A Layer.
    
        Properties:
        - provider: render provider, see Providers module.
        - config: Configuration instance, see Config module.
        - projection: geographic projection, see Geography module.
        - metatile: some information on drawing many tiles at once.
    """
    def __init__(self, config, projection, metatile):
        self.provider = None
        self.config = config
        self.projection = projection
        self.metatile = metatile

    def name(self):
        """ Figure out what I'm called, return a name if there is one.
        """
        for (name, layer) in self.config.layers.items():
            if layer is self:
                return name

        return None

    def doMetatile(self):
        """
        """
        return self.metatile.isForReal() and self.provider.metatileOK
    
    def render(self, coord, format):
        """ Render a tile for a coordinate, return PIL Image-like object.
        
            Perform metatile slicing here *** NOT YET IMPLEMENTED ***
        """
        srs = self.projection.srs
        width, height = 256, 256
        xmin, ymin, xmax, ymax = self.envelope(coord)
        
        provider = self.provider
        metatile = self.metatile
        
        if self.doMetatile():
            coords = metatile.allCoords(coord)
            
            # size of buffer expressed as fraction of tile size
            buffer = float(metatile.buffer) / 256
            
            # new master image render size
            width = int(256 * (buffer * 2 + metatile.columns))
            height = int(256 * (buffer * 2 + metatile.rows))
            
            ul = coords[0].left(buffer).up(buffer)
            lr = coords[-1].right(1 + buffer).down(1 + buffer)

            ul = self.projection.coordinateProj(ul)
            lr = self.projection.coordinateProj(lr)
            
            # new render area coverage in projected coordinates
            xmin, ymin, xmax, ymax = min(ul.x, lr.x), min(ul.y, lr.y), max(ul.x, lr.x), max(ul.y, lr.y)
            
            subtiles = []
            
            for other in coords:
                r = other.row - coords[0].row
                c = other.column - coords[0].column
                
                x = c * 256 + metatile.buffer
                y = r * 256 + metatile.buffer
                
                
                subtiles.append((other, x, y))
        
        
            # do something here to expand the envelope or whatever.
            pass
        
        if not self.doMetatile() and hasattr(provider, 'renderTile'):
            # draw a single tile
            tile = provider.renderTile(256, 256, srs, coord)

        elif hasattr(provider, 'renderArea'):
            # draw an area, defined in projected coordinates
            tile = provider.renderArea(width, height, srs, xmin, ymin, xmax, ymax)

        else:
            raise Exception('Your provider lacks renderTile and renderArea methods')

        assert hasattr(tile, 'save'), \
               'Return value of provider.renderArea() must act like an image.'
        
        if self.doMetatile():
            
            
            surtile = tile.copy()
            
            for (other, x, y) in subtiles:
                
                bbox = (x, y, x + 256, y + 256)
                buff = StringIO()
                subtile = surtile.crop(bbox).copy()
                subtile.save(buff, format)
                body = buff.getvalue()

                
                self.config.cache.save(body, self, other, format)
                
                if other == coord:
                    tile = subtile.copy()

            # now do something to slice up the metatile, cache the rest, etc.
            pass
        
        return tile

    def envelope(self, coord):
        """ Projected rendering envelope (xmin, ymin, xmax, ymax) for a Coordinate.
        """
        ul = self.projection.coordinateProj(coord)
        lr = self.projection.coordinateProj(coord.down().right())
        
        return min(ul.x, lr.x), min(ul.y, lr.y), max(ul.x, lr.x), max(ul.y, lr.y)
