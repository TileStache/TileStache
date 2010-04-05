""" The core class bits of TileStache.
"""

import Geography
import Providers

class Configuration:
    """ A complete site configuration, with a collection of Layer objects.
    """
    def __init__(self, cache):
        self.cache = cache
        self.layers = {}

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
        """ Render an image for a coordinate, return a PIL Image instance.
        """
        srs = self.projection.srs
        xmin, ymin, xmax, ymax = self.envelope(coord)
        
        img = self.provider.renderEnvelope(256, 256, srs, xmin, ymin, xmax, ymax)
        
        assert hasattr(img, 'size') and hasattr(img, 'save'), \
               'Return value of provider.renderEnvelope() must look like an image.'
        
        return img

    def envelope(self, coord):
        """ Projected rendering envelope (xmin, ymin, xmax, ymax) for a Coordinate.
        """
        ul = self.projection.coordinateProj(coord)
        lr = self.projection.coordinateProj(coord.down().right())
        
        return min(ul.x, lr.x), min(ul.y, lr.y), max(ul.x, lr.x), max(ul.y, lr.y)
