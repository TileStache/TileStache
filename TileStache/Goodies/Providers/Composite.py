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
            mime, body = TileStache.handleRequest(layer, coord, 'png')
            layer_img = PIL.Image.open(StringIO(body))
        
        if self.maskname:
            layer = config.layers[self.maskname]
            mime, body = TileStache.handleRequest(layer, coord, 'png')
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
    """
    """
    if type(color) not in (str, unicode):
        raise Exception('Color must be a string: %s' % repr(color))

    if color[0] != '#':
        raise Exception('Color must start with hash: "%s"' % color)

    if len(color) not in (4, 7):
        raise Exception('Color must have three or six hex chars: "%s"' % color)

    r = int(len(color) == 7 and color[1:3] or color[1]+color[1], 16)
    g = int(len(color) == 7 and color[3:5] or color[2]+color[2], 16)
    b = int(len(color) == 7 and color[5:7] or color[3]+color[3], 16)

    return r, g, b, 0xFF
    
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

    metatileOK = False

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
        mime, body = TileStache.handleRequest(layer, coord, 'png')
        img_base = PIL.Image.open(StringIO(body))

        layer = self.layer.config.layers['outlines']
        mime, body = TileStache.handleRequest(layer, coord, 'png')
        img_outlines = PIL.Image.open(StringIO(body))
        
        layer = self.layer.config.layers['halos']
        mime, body = TileStache.handleRequest(layer, coord, 'png')
        img_halos = PIL.Image.open(StringIO(body))
        
        img_outlinesmask = PIL.Image.new('RGBA', img_outlines.size, (0, 0, 0, 0))
        img_outlinesmask.paste(img_outlines, None, img_halos.convert('L'))

        layer = self.layer.config.layers['streets']
        mime, body = TileStache.handleRequest(layer, coord, 'png')
        img_streets = PIL.Image.open(StringIO(body))
        
        img = PIL.Image.new('RGBA', (256, 256))
        
        img.paste(img_base, (0, 0), img_base)
        img.paste(img_outlines, None, img_outlinesmask)
        img.paste(img_streets, (0, 0), img_streets)
        
        return img
    
        pass

    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax):
        pass
