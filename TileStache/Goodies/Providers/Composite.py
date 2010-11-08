""" Layered, composite rendering for TileStache.

Example configuration:

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
        "composite":
        {
            "provider": {"class": "TileStache.Goodies.Providers.Composite.Composite",
                         "kwargs": {"stackfile": "composite-stack.xml"}}
        }
      }
    }

Corresponding example composite-stack.xml:

    <?xml version="1.0"?>
    <stack>
        <layer src="base" />
    
        <stack>
            <layer src="outlines">
                <mask src="halos" />
            </layer>
            <layer src="streets" />
        </stack>
    </stack>

New configuration JSON blob or file:

    [
        {"src": "base"},
        [
            {"src": "outlines", "mask": "halos"},
            {"src": "streets"}
        ]
    ]

Note that each layer in this file refers to a TileStache layer by name.
This complete example can be found in the included examples directory.
"""

import sys

from os.path import join as pathjoin
from xml.dom.minidom import parse as parseXML
from StringIO import StringIO

import PIL.Image
import TileStache

class Layer:

    def __init__(self, layername=None, colorname=None, maskname=None):
        self.layername = layername
        self.colorname = colorname
        self.maskname = maskname

    def render(self, config, input_img, coord):
        
        layer_img, color_img, mask_img = None, None, None
        
        if self.layername:
            layer = config.layers[self.layername]
            mime, body = TileStache.getTile(layer, coord, 'png')
            layer_img = PIL.Image.open(StringIO(body))
        
        if self.maskname:
            layer = config.layers[self.maskname]
            mime, body = TileStache.getTile(layer, coord, 'png')
            mask_img = PIL.Image.open(StringIO(body)).convert('L')

        if self.colorname:
            color = makeColor(self.colorname)
            color_img = PIL.Image.new('RGBA', input_img.size, color)

        output_img = input_img.copy()

        if layer_img and color_img and mask_img:
            raise Exception('could be ugly')
        
        elif layer_img and color_img:
            output_img.paste(color_img, None, color_img)
            output_img.paste(layer_img, None, layer_img)

        elif layer_img and mask_img:
            # need to combine the masks here
            layermask_img = PIL.Image.new('RGBA', layer_img.size, (0, 0, 0, 0))
            layermask_img.paste(layer_img, None, mask_img)
            output_img.paste(layermask_img, None, layermask_img)

        elif color_img and mask_img:
            output_img.paste(color_img, None, mask_img)
        
        elif layer_img:
            output_img.paste(layer_img, None, layer_img)
        
        elif color_img:
            output_img.paste(color_img, None, color_img)

        elif mask_img:
            raise Exception('nothing')

        else:
            raise Exception('nothing')

        return output_img

class Stack:

    def __init__(self, layers):
        self.layers = layers

    def render(self, config, input_img, coord):
    
        stack_img = PIL.Image.new('RGBA', input_img.size, (0, 0, 0, 0))
        
        for layer in self.layers:
            stack_img = layer.render(config, stack_img, coord)

        output_img = input_img.copy()
        output_img.paste(stack_img, (0, 0), stack_img)
        
        return output_img

def makeColor(color):
    """ Convert colors expressed as HTML-style RGB(A) strings to tuples.
    
        Examples:
          white: "#ffffff", "#fff", "#ffff", "#ffffffff"
          black: "#000000", "#000", "#000f", "#000000ff"
          null: "#0000", "#00000000"
          orange: "#f90", "#ff9900", "#ff9900ff"
          transparent orange: "#f908", "#ff990088"
    """
    if type(color) not in (str, unicode):
        raise Exception('Color must be a string: %s' % repr(color))

    if color[0] != '#':
        raise Exception('Color must start with hash: "%s"' % color)

    if len(color) not in (4, 5, 7, 9):
        raise Exception('Color must have three, four, six or seven hex chars: "%s"' % color)

    if len(color) == 4:
        color = ''.join([color[i] for i in (0, 1, 1, 2, 2, 3, 3)])

    elif len(color) == 5:
        color = ''.join([color[i] for i in (0, 1, 1, 2, 2, 3, 3, 4, 4)])
    
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    a = len(color) == 7 and 0xFF or int(color[7:9], 16)

    return r, g, b, a
    
def makeLayer(element):
    """
    """
    kwargs = {}
    
    if element.hasAttribute('src'):
        kwargs['layername'] = element.getAttribute('src')

    if element.hasAttribute('color'):
        kwargs['colorname'] = element.getAttribute('color')
    
    for child in element.childNodes:
        if child.nodeType == child.ELEMENT_NODE:
            if child.tagName == 'mask' and child.hasAttribute('src'):
                kwargs['maskname'] = child.getAttribute('src')

    print >> sys.stderr, 'Making a layer from', kwargs
    
    return Layer(**kwargs)

def makeStack(element):
    """
    """
    layers = []
    
    for child in element.childNodes:
        if child.nodeType == child.ELEMENT_NODE:
            if child.tagName == 'stack':
                stack = makeStack(child)
                layers.append(stack)
            
            elif child.tagName == 'layer':
                layer = makeLayer(child)
                layers.append(layer)

            else:
                raise Exception('Unknown element "%s"' % child.tagName)

    print >> sys.stderr, 'Making a stack with %d layers' % len(layers)

    return Stack(layers)

class Composite:

    def __init__(self, layer, stackfile=None):
        self.layer = layer
        
        stackfile = pathjoin(self.layer.config.dirpath, stackfile)
        stack = parseXML(stackfile).firstChild
        
        assert stack.tagName == 'stack', \
               'Expecting root element "stack" but got "%s"' % stack.tagName

        self.stack = makeStack(stack)

    def renderTile(self, width, height, srs, coord):
    
        image = PIL.Image.new('RGBA', (width, height), (0, 0, 0, 0))
        
        image = self.stack.render(self.layer.config, image, coord)
        
        return image
    
        layer = self.layer.config.layers['base']
        mime, body = TileStache.getTile(layer, coord, 'png')
        img_base = PIL.Image.open(StringIO(body))

        layer = self.layer.config.layers['outlines']
        mime, body = TileStache.getTile(layer, coord, 'png')
        img_outlines = PIL.Image.open(StringIO(body))
        
        layer = self.layer.config.layers['halos']
        mime, body = TileStache.getTile(layer, coord, 'png')
        img_halos = PIL.Image.open(StringIO(body))
        
        img_outlinesmask = PIL.Image.new('RGBA', img_outlines.size, (0, 0, 0, 0))
        img_outlinesmask.paste(img_outlines, None, img_halos.convert('L'))

        layer = self.layer.config.layers['streets']
        mime, body = TileStache.getTile(layer, coord, 'png')
        img_streets = PIL.Image.open(StringIO(body))
        
        img = PIL.Image.new('RGBA', (256, 256))
        
        img.paste(img_base, (0, 0), img_base)
        img.paste(img_outlines, None, img_outlinesmask)
        img.paste(img_streets, (0, 0), img_streets)
        
        return img
    
        pass

def doStuff(thing):
    
    if type(thing) is list:
        layers = map(doStuff, thing)
        return Stack(layers)
    
    elif type(thing) is dict:
        layername, colorname, maskname = [thing.get(k, None) for k in ('src', 'color', 'mask')]
        return Layer(layername, colorname, maskname)

    else:
        raise Exception('Uh oh')

if __name__ == '__main__':

    import unittest
    
    import TileStache.Core
    import TileStache.Caches
    import TileStache.Geography
    import TileStache.Config
    import ModestMaps.Core
    
    class TinyBitmap:
        """ A minimal provider that only returns 3x3 bitmaps from strings.
        """
        def __init__(self, string):
            self.img = PIL.Image.fromstring('RGBA', (3, 3), string)

        def renderTile(self, *args, **kwargs):
            return self.img

    def tinybitmap_layer(config, string):
        """ Gin up a fake layer with a TinyBitmap provider.
        """
        meta = TileStache.Core.Metatile()
        proj = TileStache.Geography.SphericalMercator()
        layer = TileStache.Core.Layer(config, proj, meta)
        layer.provider = TinyBitmap(string)

        return layer
    
    class ColorTests(unittest.TestCase):
        """
        """
        def testColors(self):
            assert makeColor('#ffffff') == (0xFF, 0xFF, 0xFF, 0xFF), 'white'
            assert makeColor('#fff') == (0xFF, 0xFF, 0xFF, 0xFF), 'white again'
            assert makeColor('#ffff') == (0xFF, 0xFF, 0xFF, 0xFF), 'white again again'
            assert makeColor('#ffffffff') == (0xFF, 0xFF, 0xFF, 0xFF), 'white again again again'

            assert makeColor('#000000') == (0x00, 0x00, 0x00, 0xFF), 'black'
            assert makeColor('#000') == (0x00, 0x00, 0x00, 0xFF), 'black again'
            assert makeColor('#000f') == (0x00, 0x00, 0x00, 0xFF), 'black again'
            assert makeColor('#000000ff') == (0x00, 0x00, 0x00, 0xFF), 'black again again'

            assert makeColor('#0000') == (0x00, 0x00, 0x00, 0x00), 'null'
            assert makeColor('#00000000') == (0x00, 0x00, 0x00, 0x00), 'null again'

            assert makeColor('#f90') == (0xFF, 0x99, 0x00, 0xFF), 'orange'
            assert makeColor('#ff9900') == (0xFF, 0x99, 0x00, 0xFF), 'orange again'
            assert makeColor('#ff9900ff') == (0xFF, 0x99, 0x00, 0xFF), 'orange again again'

            assert makeColor('#f908') == (0xFF, 0x99, 0x00, 0x88), 'transparent orange'
            assert makeColor('#ff990088') == (0xFF, 0x99, 0x00, 0x88), 'transparent orange again'
    
    class CompositeTests(unittest.TestCase):
        """
        """
        def setUp(self):
    
            cache = TileStache.Caches.Test()
            self.config = TileStache.Config.Configuration(cache, '.')
            
            # Sort of a sw/ne diagonal street, with a top-left corner halo:
            # 
            # +------+   +------+   +------+   +------+   +------+
            # |\\\\\\|   |++++--|   |  ////|   |    ''|   |\\//''|
            # |\\\\\\| + |++++--| + |//////| + |  ''  | > |//''\\|
            # |\\\\\\|   |------|   |////  |   |''    |   |''\\\\|
            # +------+   +------+   +------+   +------+   +------+
            #
            # Just trust the tests.
            #
            _fff, _ccc, _999, _000, _nil = '\xFF\xFF\xFF\xFF', '\xCC\xCC\xCC\xFF', '\x99\x99\x99\xFF', '\x00\x00\x00\xFF', '\x00\x00\x00\x00'
            
            self.config.layers = \
            {
                'base':     tinybitmap_layer(self.config, _ccc * 9),
                'halos':    tinybitmap_layer(self.config, _fff + _fff + _000 + _fff + _fff + (_000 * 4)),
                'outlines': tinybitmap_layer(self.config, _nil + (_999 * 7) + _nil),
                'streets':  tinybitmap_layer(self.config, _nil + _nil + _fff + _nil + _fff + _nil + _fff + _nil + _nil)
            }
            
            self.start_img = PIL.Image.new('RGBA', (3, 3), (0x00, 0x00, 0x00, 0x00))
        
        def test0(self):
    
            stack = \
                [
                    {"src": "base"},
                    [
                        {"src": "outlines"},
                        {"src": "streets"}
                    ]
                ]
            
            stack = doStuff(stack)
            img = stack.render(self.config, self.start_img, ModestMaps.Core.Coordinate(0, 0, 0))
            
            assert img.getpixel((0, 0)) == (0xCC, 0xCC, 0xCC, 0xFF), 'top left pixel'
            assert img.getpixel((1, 0)) == (0x99, 0x99, 0x99, 0xFF), 'top center pixel'
            assert img.getpixel((2, 0)) == (0xFF, 0xFF, 0xFF, 0xFF), 'top right pixel'
            assert img.getpixel((0, 1)) == (0x99, 0x99, 0x99, 0xFF), 'center left pixel'
            assert img.getpixel((1, 1)) == (0xFF, 0xFF, 0xFF, 0xFF), 'middle pixel'
            assert img.getpixel((2, 1)) == (0x99, 0x99, 0x99, 0xFF), 'center right pixel'
            assert img.getpixel((0, 2)) == (0xFF, 0xFF, 0xFF, 0xFF), 'bottom left pixel'
            assert img.getpixel((1, 2)) == (0x99, 0x99, 0x99, 0xFF), 'bottom center pixel'
            assert img.getpixel((2, 2)) == (0xCC, 0xCC, 0xCC, 0xFF), 'bottom right pixel'
        
        def test1(self):
    
            stack = \
                [
                    {"src": "base"},
                    [
                        {"src": "outlines", "mask": "halos"},
                        {"src": "streets"}
                    ]
                ]
            
            stack = doStuff(stack)
            img = stack.render(self.config, self.start_img, ModestMaps.Core.Coordinate(0, 0, 0))
            
            assert img.getpixel((0, 0)) == (0xCC, 0xCC, 0xCC, 0xFF), 'top left pixel'
            assert img.getpixel((1, 0)) == (0x99, 0x99, 0x99, 0xFF), 'top center pixel'
            assert img.getpixel((2, 0)) == (0xFF, 0xFF, 0xFF, 0xFF), 'top right pixel'
            assert img.getpixel((0, 1)) == (0x99, 0x99, 0x99, 0xFF), 'center left pixel'
            assert img.getpixel((1, 1)) == (0xFF, 0xFF, 0xFF, 0xFF), 'middle pixel'
            assert img.getpixel((2, 1)) == (0xCC, 0xCC, 0xCC, 0xFF), 'center right pixel'
            assert img.getpixel((0, 2)) == (0xFF, 0xFF, 0xFF, 0xFF), 'bottom left pixel'
            assert img.getpixel((1, 2)) == (0xCC, 0xCC, 0xCC, 0xFF), 'bottom center pixel'
            assert img.getpixel((2, 2)) == (0xCC, 0xCC, 0xCC, 0xFF), 'bottom right pixel'
        
        def test2(self):
    
            stack = \
                [
                    {"color": "#ccc"},
                    [
                        {"src": "outlines", "mask": "halos"},
                        {"src": "streets"}
                    ]
                ]
            
            stack = doStuff(stack)
            img = stack.render(self.config, self.start_img, ModestMaps.Core.Coordinate(0, 0, 0))
            
            assert img.getpixel((0, 0)) == (0xCC, 0xCC, 0xCC, 0xFF), 'top left pixel'
            assert img.getpixel((1, 0)) == (0x99, 0x99, 0x99, 0xFF), 'top center pixel'
            assert img.getpixel((2, 0)) == (0xFF, 0xFF, 0xFF, 0xFF), 'top right pixel'
            assert img.getpixel((0, 1)) == (0x99, 0x99, 0x99, 0xFF), 'center left pixel'
            assert img.getpixel((1, 1)) == (0xFF, 0xFF, 0xFF, 0xFF), 'middle pixel'
            assert img.getpixel((2, 1)) == (0xCC, 0xCC, 0xCC, 0xFF), 'center right pixel'
            assert img.getpixel((0, 2)) == (0xFF, 0xFF, 0xFF, 0xFF), 'bottom left pixel'
            assert img.getpixel((1, 2)) == (0xCC, 0xCC, 0xCC, 0xFF), 'bottom center pixel'
            assert img.getpixel((2, 2)) == (0xCC, 0xCC, 0xCC, 0xFF), 'bottom right pixel'
        
        def test3(self):
            
            stack = \
                [
                    {"color": "#ccc"},
                    [
                        {"color": "#999", "mask": "halos"},
                        {"src": "streets"}
                    ]
                ]
            
            stack = doStuff(stack)
            img = stack.render(self.config, self.start_img, ModestMaps.Core.Coordinate(0, 0, 0))
            
            assert img.getpixel((0, 0)) == (0x99, 0x99, 0x99, 0xFF), 'top left pixel'
            assert img.getpixel((1, 0)) == (0x99, 0x99, 0x99, 0xFF), 'top center pixel'
            assert img.getpixel((2, 0)) == (0xFF, 0xFF, 0xFF, 0xFF), 'top right pixel'
            assert img.getpixel((0, 1)) == (0x99, 0x99, 0x99, 0xFF), 'center left pixel'
            assert img.getpixel((1, 1)) == (0xFF, 0xFF, 0xFF, 0xFF), 'middle pixel'
            assert img.getpixel((2, 1)) == (0xCC, 0xCC, 0xCC, 0xFF), 'center right pixel'
            assert img.getpixel((0, 2)) == (0xFF, 0xFF, 0xFF, 0xFF), 'bottom left pixel'
            assert img.getpixel((1, 2)) == (0xCC, 0xCC, 0xCC, 0xFF), 'bottom center pixel'
            assert img.getpixel((2, 2)) == (0xCC, 0xCC, 0xCC, 0xFF), 'bottom right pixel'
        
        def test4(self):
    
            stack = \
                [
                    [
                        {"color": "#999", "mask": "halos"},
                        {"src": "streets"}
                    ]
                ]
            
            stack = doStuff(stack)
            img = stack.render(self.config, self.start_img, ModestMaps.Core.Coordinate(0, 0, 0))
            
            assert img.getpixel((0, 0)) == (0x99, 0x99, 0x99, 0xFF), 'top left pixel'
            assert img.getpixel((1, 0)) == (0x99, 0x99, 0x99, 0xFF), 'top center pixel'
            assert img.getpixel((2, 0)) == (0xFF, 0xFF, 0xFF, 0xFF), 'top right pixel'
            assert img.getpixel((0, 1)) == (0x99, 0x99, 0x99, 0xFF), 'center left pixel'
            assert img.getpixel((1, 1)) == (0xFF, 0xFF, 0xFF, 0xFF), 'middle pixel'
            assert img.getpixel((2, 1)) == (0x00, 0x00, 0x00, 0x00), 'center right pixel'
            assert img.getpixel((0, 2)) == (0xFF, 0xFF, 0xFF, 0xFF), 'bottom left pixel'
            assert img.getpixel((1, 2)) == (0x00, 0x00, 0x00, 0x00), 'bottom center pixel'
            assert img.getpixel((2, 2)) == (0x00, 0x00, 0x00, 0x00), 'bottom right pixel'

    unittest.main()
