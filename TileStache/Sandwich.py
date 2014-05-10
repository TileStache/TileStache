""" Layered, composite rendering for TileStache.

The Sandwich Provider supplies a Photoshop-like rendering pipeline, making it
possible to use the output of other configured tile layers as layers or masks
to create a combined output. Sandwich is modeled on Lars Ahlzen's TopOSM.

The external "Blit" library is required by Sandwich, and can be installed
via Pip, easy_install, or directly from Github:

    https://github.com/migurski/Blit

The "stack" configuration parameter describes a layer or stack of layers that
can be combined to create output. A simple stack that merely outputs a single
color orange tile looks like this:

    {"color" "#ff9900"}

Other layers in the current TileStache configuration can be reference by name,
as in this example stack that simply echoes another layer:

    {"src": "layer-name"}

Bitmap images can also be referenced by local filename or URL, and will be
tiled seamlessly, assuming 256x256 parent tiles:

    {"src": "image.png"}
    {"src": "http://example.com/image.png"}

Layers can be limited to appear at certain zoom levels, given either as a range
or as a single number:

    {"src": "layer-name", "zoom": "12"}
    {"src": "layer-name", "zoom": "12-18"}

Layers can also be used as masks, as in this example that uses one layer
to mask another layer:

    {"mask": "layer-name", "src": "other-layer"}

Many combinations of "src", "mask", and "color" can be used together, but it's
an error to provide all three.

Layers can be combined through the use of opacity and blend modes. Opacity is
specified as a value from 0.0-1.0, and blend mode is specified as a string.
This example layer is blended using the "hard light" mode at 50% opacity:

    {"src": "hillshading", "mode": "hard light", "opacity": 0.5}

Currently-supported blend modes include "screen", "add", "multiply", "subtract",
"linear light", and "hard light".

Layers can also be affected by adjustments. Adjustments are specified as an
array of names and parameters. This example layer has been slightly darkened
using the "curves" adjustment, moving the input value of 181 (light gray)
to 50% gray while leaving black and white alone:

    {"src": "hillshading", "adjustments": [ ["curves", [0, 181, 255]] ]}

Available adjustments:
  "threshold" - Blit.adjustments.threshold()
  "curves" - Blit.adjustments.curves()
  "curves2" - Blit.adjustments.curves2()

See detailed information about adjustments in Blit documentation:

    https://github.com/migurski/Blit#readme

Finally, the stacking feature allows layers to combined in more complex ways.
This example stack combines a background color and foreground layer:

    [
      {"color": "#ff9900"},
      {"src": "layer-name"}
    ]

A complete example configuration might look like this:

    {
      "cache":
      {
        "name": "Test"
      },
      "layers": 
      {
        "base":
        {
          "provider": {"name": "mapnik", "mapfile": "mapnik-base.xml"}
        },
        "halos":
        {
          "provider": {"name": "mapnik", "mapfile": "mapnik-halos.xml"},
          "metatile": {"buffer": 128}
        },
        "outlines":
        {
          "provider": {"name": "mapnik", "mapfile": "mapnik-outlines.xml"},
          "metatile": {"buffer": 16}
        },
        "streets":
        {
          "provider": {"name": "mapnik", "mapfile": "mapnik-streets.xml"},
          "metatile": {"buffer": 128}
        },
        "sandwiches":
        {
          "provider":
          {
            "name": "Sandwich",
            "stack":
            [
              {"src": "base"},
              {"src": "outlines", "mask": "halos"},
              {"src": "streets"}
            ]
          }
        }
      }
    }
"""
from re import search
from StringIO import StringIO
from itertools import product
from urlparse import urljoin
from urllib import urlopen

from . import Core

try:
    import Image
except ImportError:
    try:
        from Pillow import Image
    except ImportError:
        from PIL import Image

try:
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

except ImportError:
    # Well, this will not work.
    pass

class Provider:
    """ Sandwich Provider.
    
        Stack argument is a list of layer dictionaries described in module docs.
    """
    def __init__(self, layer, stack):
        self.layer = layer
        self.config = layer.config
        self.stack = stack
    
    @staticmethod
    def prepareKeywordArgs(config_dict):
        """ Convert configured parameters to keyword args for __init__().
        """
        return {'stack': config_dict['stack']}
    
    def renderTile(self, width, height, srs, coord):
        
        rendered = self.draw_stack(coord, dict())
        
        if rendered.size() == (width, height):
            return rendered.image()
        else:
            return rendered.image().resize((width, height))

    def draw_stack(self, coord, tiles):
        """ Render this image stack.

            Given a coordinate, return an output image with the results of all the
            layers in this stack pasted on in turn.
        
            Final argument is a dictionary used to temporarily cache results
            of layers retrieved from layer_bitmap(), to speed things up in case
            of repeatedly-used identical images.
        """
        # start with an empty base
        rendered = Blit.Color(0, 0, 0, 0)
    
        for layer in self.stack:
            if 'zoom' in layer and not in_zoom(coord, layer['zoom']):
                continue

            #
            # Prepare pixels from elsewhere.
            #
        
            source_name, mask_name, color_name = [layer.get(k, None) for k in ('src', 'mask', 'color')]
    
            if source_name and color_name and mask_name:
                raise Core.KnownUnknown("You can't specify src, color and mask together in a Sandwich Layer: %s, %s, %s" % (repr(source_name), repr(color_name), repr(mask_name)))
        
            if source_name and source_name not in tiles:
                if source_name in self.config.layers:
                    tiles[source_name] = layer_bitmap(self.config.layers[source_name], coord)
                else:
                    tiles[source_name] = local_bitmap(source_name, self.config, coord, self.layer.dim)
        
            if mask_name and mask_name not in tiles:
                tiles[mask_name] = layer_bitmap(self.config.layers[mask_name], coord)
        
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

def local_bitmap(source, config, coord, dim):
    """ Return Blit.Bitmap representation of a raw image.
    """
    address = urljoin(config.dirpath, source)
    bytes = urlopen(address).read()
    image = Image.open(StringIO(bytes)).convert('RGBA')
    
    coord = coord.zoomBy(8)
    w, h, col, row = image.size[0], image.size[1], int(coord.column), int(coord.row)
    
    x = w * (col / w) - col
    y = h * (row / h) - row
    
    output = Image.new('RGBA', (dim, dim))
    
    for (x, y) in product(range(x, dim, w), range(y, dim, h)):
        # crop the top-left if needed
        xmin = 0 if x > 0 else -x
        ymin = 0 if y > 0 else -y
        
        # don't paste up and to the left
        x = x if x >= 0 else 0
        y = y if y >= 0 else 0
        
        output.paste(image.crop((xmin, ymin, w, h)), (x, y))
    
    return Blit.Bitmap(output)

def layer_bitmap(layer, coord):
    """ Return Blit.Bitmap representation of tile from a given layer.
    
        Uses TileStache.getTile(), so caches are read and written as normal.
    """
    from . import getTile

    mime, body = getTile(layer, coord, 'png')
    image = Image.open(StringIO(body)).convert('RGBA')

    return Blit.Bitmap(image)

def in_zoom(coord, range):
    """ Return True if the coordinate zoom is within the textual range.
    
        Range might look like "1-10" or just "5".
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
        raise Core.KnownUnknown('Color must have three, four, six or eight hex chars: "%s"' % color)

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
