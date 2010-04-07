""" The core class bits of TileStache.
"""

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

    def render(self, coord):
        """ Render a tile for a coordinate, return PIL Image-like object.
        
            Perform metatile slicing here *** NOT YET IMPLEMENTED ***
        """
        srs = self.projection.srs
        xmin, ymin, xmax, ymax = self.envelope(coord)
        
        provider = self.provider
        metatile = self.metatile.isForReal() and provider.metatileOK
        
        if metatile:
            # do something here to expand the envelope or whatever.
            pass
        
        if not metatile and hasattr(provider, 'renderTile'):
            # draw a single tile
            tile = provider.renderTile(256, 256, srs, coord)

        elif hasattr(provider, 'renderArea'):
            # draw an area, defined in projected coordinates
            tile = provider.renderArea(256, 256, srs, xmin, ymin, xmax, ymax)

        else:
            raise Exception('Your provider lacks renderTile and renderArea methods')

        if metatile:
            # now do something to slice up the metatile, cache the rest, etc.
            pass
        
        assert hasattr(tile, 'save'), \
               'Return value of provider.renderArea() must act like an image.'
        
        return tile

    def envelope(self, coord):
        """ Projected rendering envelope (xmin, ymin, xmax, ymax) for a Coordinate.
        """
        ul = self.projection.coordinateProj(coord)
        lr = self.projection.coordinateProj(coord.down().right())
        
        return min(ul.x, lr.x), min(ul.y, lr.y), max(ul.x, lr.x), max(ul.y, lr.y)
