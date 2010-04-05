import re
import ModestMaps
from os import environ
from cgi import parse_qs
from math import log, pi

try:
    from json import load as loadjson
except ImportError:
    from simplejson import load as loadjson

class SphericalMercator(ModestMaps.Geo.MercatorProjection):
    """
    """
    def __init__(self):
        # these numbers are slightly magic.
        t = ModestMaps.Geo.Transformation(1.068070779e7, 0, 3.355443185e7,
		                                  0, -1.068070890e7, 3.355443057e7)

        ModestMaps.Geo.MercatorProjection.__init__(self, 26, t)

class Configuration:
    """
    """
    def __init__(self):
        self.layers = {}

class Layer:
    """
    """
    def __init__(self, name, projection):
        self.name = name
        self.projection = getProjectionByName(projection)

def getProjectionByName(name):
    """
    """
    if name == 'spherical mercator':
        return SphericalMercator()
    
        # print 'fuck'
        # 
        # radius = 6378137
        # diameter = 2 * pi radius
        # 
        # point1 = -pi, pi, -diameter, diameter
        # print ModestMaps.Geo.deriveTransformation(a1x, a1y, a2x, a2y, b1x, b1y, b2x, b2y, c1x, c1y, c2x, c2y)
        
    else:
        raise Exception('Unknown projection: "%s"' % name)

def parseConfigfile(path):
    """
    """
    config = Configuration()
    raw = loadjson(open(path, 'r'))
    
    for (name, data) in raw.get('layers', {}).items():
        projection = data.get('projection', '')
        config.layers[name] = Layer(name, projection)

    return config

def handleRequest(config, layer, coord, query):
    """
    """
    
    pass

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
    
    coord = ModestMaps.Core.Coordinate(int(row), int(column), int(zoom))
    query = parse_qs(environ['QUERY_STRING'])
    
    print 'Content-Type: text/plain\n'
    config = parseConfigfile('tilestache.cfg')
    return handleRequest(config, config.layers[layer], coord, query)
