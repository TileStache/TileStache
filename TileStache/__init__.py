""" A stylish alternative for caching your tiles.


"""

import re
import Geography
from os import environ
from cgi import parse_qs
from sys import stderr, stdout
from ModestMaps.Core import Coordinate
from StringIO import StringIO

try:
    from json import load as loadjson
except ImportError:
    from simplejson import load as loadjson

class Configuration:
    """ A complete site configuration, with a collection of Layer objects.
    """
    def __init__(self):
        self.layers = {}

class Layer:
    """ A Layer, with its own provider and projection.
    """
    def __init__(self, config, provider, projection):
        self.config = config
        self.provider = provider
        self.projection = Geography.getProjectionByName(projection)

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

def parseConfigfile(path):
    """ Parse a configuration file path and return a Configuration object.
    """
    config = Configuration()
    raw = loadjson(open(path, 'r'))
    
    for (name, data) in raw.get('layers', {}).items():
        projection = data.get('projection', '')
        
        try:
            path = data['provider']['class'].split('.')
        except KeyError:
            raise

        module = __import__('.'.join(path[:-1]))
        _class = getattr(module, path[-1])
        kwargs = data['provider'].get('kwargs', {})
        provider = _class(**kwargs)
    
        config.layers[name] = Layer(config, provider, projection)

    return config

def handleRequest(layer, coord, extension, query):
    """ Get a type string and image binary for a given request layer, coordinate, file extension, and query string.
    """
    out = StringIO()
    img = layer.render(coord)
    
    img.save(out, 'PNG')
    
    return 'image/png', out.getvalue()

# regular expression for PATH_INFO
pathinfo_pat = re.compile(r'^/(?P<l>.+)/(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)\.(?P<e>\w+)$')

def cgiHandler(debug=False):
    """ 
    """
    if debug:
        import cgitb
        cgitb.enable()
    
    path = pathinfo_pat.match(environ['PATH_INFO'])
    layer, row, column, zoom, extension = [path.group(p) for p in 'lyxze']
    
    coord = Coordinate(int(row), int(column), int(zoom))
    query = parse_qs(environ['QUERY_STRING'])
    layer = parseConfigfile('tilestache.cfg').layers[layer]
    
    mimetype, content = handleRequest(layer, coord, extension, query)
    
    print >> stdout, 'Content-Type: %(mimetype)s\n' % locals()
    print >> stdout, content
