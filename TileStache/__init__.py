import re
import ModestMaps
from sys import stderr, stdout
from os import environ
from cgi import parse_qs
from math import log, pi
from StringIO import StringIO

try:
    from json import load as loadjson
except ImportError:
    from simplejson import load as loadjson

class SphericalMercator(ModestMaps.Geo.MercatorProjection):
    """
    """
    srs = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0' \
        + ' +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +no_defs'
    
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
        self.projection = getProjectionByName(projection)

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

def getProjectionByName(name):
    """ Retrieve a projection object by name.
    
        Raise an exception if the name doesn't work out.
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

def handleRequest(layer, coord, query):
    """ Get a type string and image binary for a given request layer, coordinate and query string.
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
    
    coord = ModestMaps.Core.Coordinate(int(row), int(column), int(zoom))
    query = parse_qs(environ['QUERY_STRING'])
    layer = parseConfigfile('tilestache.cfg').layers[layer]
    
    mimetype, content = handleRequest(layer, coord, query)
    
    print >> stdout, 'Content-Type: %(mimetype)s\n' % locals()
    print >> stdout, content
