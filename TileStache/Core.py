""" The core class bits of TileStache.
"""

import Geography

class Layer:
    """ A Layer, with its own provider and projection.
    """
    def __init__(self, config, projection):
        self.provider = None
        self.config = config
        self.projection = Geography.getProjectionByName(projection)

    def name(self):
        """ Figure out what I'm called, return a name if there is one.
        """
        for (name, layer) in self.config.layers.items():
            if layer is self:
                return name

        return None

    def render(self, coord):
        """ Render a tile for a coordinate, return PIL Image-like object.
        
            
        """
        srs = self.projection.srs
        xmin, ymin, xmax, ymax = self.envelope(coord)
        
        tile = self.provider.renderArea(256, 256, srs, xmin, ymin, xmax, ymax)
        
        assert hasattr(tile, 'save'), \
               'Return value of provider.renderArea() must act like an image.'
        
        return tile

    def envelope(self, coord):
        """ Projected rendering envelope (xmin, ymin, xmax, ymax) for a Coordinate.
        """
        ul = self.projection.coordinateProj(coord)
        lr = self.projection.coordinateProj(coord.down().right())
        
        return min(ul.x, lr.x), min(ul.y, lr.y), max(ul.x, lr.x), max(ul.y, lr.y)
