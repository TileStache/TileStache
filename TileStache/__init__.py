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

    def coordinateProj(self, coord):
        """ Convert from Coordinate object to a Point object in EPSG:900913
        """
        # the zoom at which we're dealing with meters on the ground
        diameter = 2 * pi * 6378137
        zoom = log(diameter) / log(2)
        coord = coord.zoomTo(zoom)
        
        # global offsets
        coord.column -= diameter/2
        coord.row = diameter/2 - coord.row

        return ModestMaps.Core.Point(coord.column, coord.row)

    def locationProj(self, location):
        """ Convert from Location object to a Point object in EPSG:900913
        """
        return self.coordinateProj(self.locationCoordinate(location))

class Configuration:
    """
    """
    def __init__(self):
        self.layers = {}

class Layer:
    """
    """
    def __init__(self, config, name, projection):
        self.config = config
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
        config.layers[name] = Layer(config, name, projection)

    return config

def handleRequest(layer, coord, query):
    """
    """
    print layer
    print coord
    
    print layer.projection.coordinateLocation(coord)
    print layer.projection.coordinateProj(coord)
    
    print layer.projection.coordinateProj(ModestMaps.Core.Coordinate(0, 0, 0))
    print layer.projection.coordinateProj(ModestMaps.Core.Coordinate(1, 1, 0))
    
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
    layer = parseConfigfile('tilestache.cfg').layers[layer]
    
    print 'Content-Type: text/plain\n'
    return handleRequest(layer, coord, query)
