from re import search
from StringIO import StringIO

from . import Core
from . import getTile

import Image
import Blit

blend_modes = {
    'screen': Blit.blends.screen,
    'add': Blit.blends.add,
    'multiply': Blit.blends.multiply,
    'subtract': Blit.blends.subtract,
    'linear light': Blit.blends.linear_light,
    'hard light': Blit.blends.hard_light
    }

adjustment_names = {
    'threshold': Blit.adjustments.threshold,
    'curves': Blit.adjustments.curves,
    'curves2': Blit.adjustments.curves2
    }

class Provider:
    """
    """
    def __init__(self, layer, stack):
        self.config = layer.config
        self.stack = stack
    
    def renderTile(self, width, height, srs, coord):
        
        rendered = draw_stack(self.stack, coord, self.config, dict())
        
        if rendered.size() == (width, height):
            return rendered.image()
        else:
            return rendered.image().resize((width, height))

def draw_stack(stack, coord, config, tiles):
    """
    """
    # start with an empty base
    rendered = Blit.Color(0, 0, 0, 0x10)
    
    for layer in stack:
        if 'zoom' in layer and not in_zoom(coord, layer['zoom']):
            continue

        #
        # Prepare pixels from elsewhere.
        #
        
        source_name, mask_name, color_name = [layer.get(k, None) for k in ('src', 'mask', 'color')]
    
        if source_name and color_name and mask_name:
            raise Core.KnownUnknown("You can't specify src, color and mask together in a Sandwich Layer: %s, %s, %s" % (repr(source_name), repr(color_name), repr(mask_name)))
        
        if source_name and source_name not in tiles:
            tiles[source_name] = layer_bitmap(config.layers[source_name], coord)
        
        if mask_name and mask_name not in tiles:
            tiles[mask_name] = layer_bitmap(config.layers[mask_name], coord)
        
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
        # Do the final composition with adjustments and blend modes.
        #
        
        for (name, args) in layer.get('adjustments', []):
            adjustfunc = adjustment_names.get(name)(*args)
            foreground = foreground.adjust(adjustfunc)
        
        opacity = float(layer.get('opacity', 1.0))
        blendfunc = blend_modes.get(layer.get('mode', None), None)
        
        if mask_name:
            rendered = rendered.blend(foreground, tiles[mask_name], opacity, blendfunc)
        else:
            rendered = rendered.blend(foreground, None, opacity, blendfunc)
    
    return rendered

def layer_bitmap(layer, coord):
    """
    """
    mime, body = getTile(layer, coord, 'png')
    image = Image.open(StringIO(body)).convert('RGBA')

    return Blit.Bitmap(image)

def in_zoom(coord, range):
    """ Return True if the coordinate zoom is within the textual range.
    """
    zooms = search("^(\d+)-(\d+)$|^(\d+)$", range)
    
    if not zooms:
        raise Core.KnownUnknown("Bad zoom range in a Sandwich Layer: %s" % repr(range))
    
    min_zoom, max_zoom, at_zoom = zooms.groups()
    
    if min_zoom is not None and max_zoom is not None:
        min_zoom, max_zoom = int(min_zoom), int(max_zoom)

    elif at_zoom is not None:
        min_zoom, max_zoom = int(at_zoom), int(at_zoom)

    else:
        min_zoom, max_zoom = 0, float('inf')
    
    return min_zoom <= coord.zoom and coord.zoom <= max_zoom

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
