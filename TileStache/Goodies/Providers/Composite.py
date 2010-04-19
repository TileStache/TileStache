"""

<stack> 
	<layer src="road-names" /> 
	<layer src="road-inlines" /> 
	<layer src="road-outlines"> 
		<mask src="road-name-halos" /> 
	</layer> 
	<layer color="#ccc"/> 
</stack>
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

    def render(self):
        pass

class Stack:

    def __init__(self, layers):
        self.layers = layers

    def render(self):
        pass

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
                kwargs['maskname'] = element.getAttribute('src')

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

        self.stack = stack

    def renderTile(self, width, height, srs, coord):
    
        makeStack(self.stack)
    
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
