from . import Core

import Blit

blend_modes = {
    'screen': Blit.blends.screen,
    'add': Blit.blends.add,
    'multiply': Blit.blends.multiply,
    'subtract': Blit.blends.subtract,
    'linear light': Blit.blends.linear_light,
    'hard light': Blit.blends.hard_light
    }

class Provider:
    """
    """
    def __init__(self, layer, stack):
        self.config = layer.config
        self.stack = stack
    
    def renderTile(self, width, height, srs, coord):
        
        # start with an empty base
        rendered = Blit.Color(0, 0, 0, 0x10)
        
        # a place to put rendered tiles
        tiles = dict()
        
        for layer in self.stack:
            #
            # Prepare pixels from elsewhere.
            #
            
            source_name, mask_name, color_name = [layer.get(k, None) for k in ('src', 'mask', 'color')]
        
            if source_name and color_name and mask_name:
                raise Core.KnownUnknown("You can't specify src, color and mask together in a Sandwich Layer: %s, %s, %s" % (repr(source_name), repr(color_name), repr(mask_name)))
            
            if source_name and source_name not in tiles:
                provider = self.config.layers[source_name].provider
                tiles[source_name] = Blit.Bitmap(provider.renderTile(width, height, srs, coord))
            
            if mask_name and mask_name not in tiles:
                provider = self.config.layers[mask_name].provider
                tiles[mask_name] = Blit.Bitmap(provider.renderTile(width, height, srs, coord))
            
            #
            # Build up the foreground layer.
            #
            
            if source_name and color_name:
                # color first, then layer
                foreground = make_color(color_name).blend(tiles[source_name])
            
            elif source_name:
                foreground = tiles[source_name]
            
            elif color_name:
                foreground = make_color(color_name)
    
            elif mask_name:
                raise Core.KnownUnknown("You have to provide more than just a mask to Sandwich Layer: %s" % repr(mask_name))
    
            else:
                raise Core.KnownUnknown("You have to provide at least some combination of src, color and mask to Sandwich Layer")
            
            #
            # Do the final composition.
            #
            
            kwargs = dict(opacity=float(layer.get('opacity', 1.0)))
            kwargs['blendfunc'] = blend_modes.get(layer.get('mode', None), None)
            
            if mask_name:
                rendered = rendered.blend(foreground, tiles[mask_name], **kwargs)
            
            else:
                rendered = rendered.blend(foreground, **kwargs)
    
        #
        
        if rendered.size() == (width, height):
            return rendered.image()
        else:
            return rendered.image().resize((width, height))

def make_color(color):
    """ Convert colors expressed as HTML-style RGB(A) strings to Blit.Color.
        
        Examples:
          white: "#ffffff", "#fff", "#ffff", "#ffffffff"
          black: "#000000", "#000", "#000f", "#000000ff"
          null: "#0000", "#00000000"
          orange: "#f90", "#ff9900", "#ff9900ff"
          transparent orange: "#f908", "#ff990088"
    """
    if type(color) not in (str, unicode):
        raise Core.KnownUnknown('Color must be a string: %s' % repr(color))

    if color[0] != '#':
        raise Core.KnownUnknown('Color must start with hash: "%s"' % color)

    if len(color) not in (4, 5, 7, 9):
        raise Core.KnownUnknown('Color must have three, four, six or seven hex chars: "%s"' % color)

    if len(color) == 4:
        color = ''.join([color[i] for i in (0, 1, 1, 2, 2, 3, 3)])

    elif len(color) == 5:
        color = ''.join([color[i] for i in (0, 1, 1, 2, 2, 3, 3, 4, 4)])
    
    try:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        a = len(color) == 7 and 0xFF or int(color[7:9], 16)

    except ValueError:
        raise Core.KnownUnknown('Color must be made up of valid hex chars: "%s"' % color)

    return Blit.Color(r, g, b, a)
