""" The input/output bits of TileStache.
"""

import re

from os import environ
from cgi import parse_qs
from sys import stderr, stdout
from StringIO import StringIO
from os.path import realpath, dirname, join as pathjoin

try:
    from json import load as loadjson
    from json import dumps as dumpjsons
except ImportError:
    from simplejson import load as loadjson
    from simplejson import dumps as dumpjsons

from ModestMaps.Core import Coordinate

import Core
import Caches
import Providers

# regular expression for PATH_INFO
_pathinfo_pat = re.compile(r'^/(?P<l>.+)/(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)\.(?P<e>\w+)$')

def handleRequest(layer, coord, extension):
    """ Get a type string and image binary for a given request layer, coordinate, and file extension.
    
        This is the main entry point, after site configuration have been loaded
        and individual tiles need to be rendered.
    """
    mimetype, format = getTypeByExtension(extension)
    
    body = layer.config.cache.read(layer, coord, format)
    
    if body is None:
        out = StringIO()
        img = layer.render(coord)
        img.save(out, format)
        body = out.getvalue()
        
        layer.config.cache.save(body, layer, coord, format)

    return mimetype, body

def cgiHandler(debug=False):
    """ Load up configuration and talk to stdout by CGI.
    """
    if debug:
        import cgitb
        cgitb.enable()
    
    path = _pathinfo_pat.match(environ['PATH_INFO'])
    layer, row, column, zoom, extension = [path.group(p) for p in 'lyxze']
    config = parseConfigfile('tilestache.cfg')
    
    coord = Coordinate(int(row), int(column), int(zoom))
    query = parse_qs(environ['QUERY_STRING'])
    layer = config.layers[layer]
    
    mimetype, content = handleRequest(layer, coord, extension)
    
    print >> stdout, 'Content-Length: %d' % len(content)
    print >> stdout, 'Content-Type: %s\n' % mimetype
    print >> stdout, content

def parseConfigfile(configpath):
    """ Parse a configuration file path and return a Configuration object.
    """
    raw = loadjson(open(configpath, 'r'))
    
    rawcache = raw.get('cache', {})
    cache = _parseConfigfileCache(rawcache, configpath)
    
    config = Core.Configuration(cache)
    
    for (name, rawlayer) in raw.get('layers', {}).items():
        config.layers[name] = _parseConfigfileLayer(rawlayer, config, configpath)

    return config

def _parseConfigfileCache(rawcache, configpath):
    """ Used by parseConfigfile() to parse just the cache parts of a config.
    """
    if rawcache['type'].lower() == 'test':
        cache = Caches.Test(lambda msg: stderr.write(msg + '\n'))

    elif rawcache['type'].lower() == 'disk':
        cachepath = realpath(pathjoin(dirname(configpath), rawcache['path']))
        kwargs = {}
        
        if rawcache.has_key('umask'):
            kwargs['umask'] = int(rawcache['umask'], 8)

        cache = Caches.Disk(cachepath, **kwargs)
    else:
        raise Exception('Unknown cache type: %s' % rawcache['type'])

    return cache

def _parseConfigfileLayer(rawlayer, config, configpath):
    """ Used by parseConfigfile() to parse just the layer parts of a config.
    """
    projection = rawlayer.get('projection', '')
    rawprovider = rawlayer['provider']

    if rawprovider.has_key('name'):
        _class = Providers.getProviderByName(rawprovider['name'])
        kwargs = {}
        
        if _class is Providers.Mapnik:
            mapfile = rawprovider['mapfile']
            kwargs['mapfile'] = realpath(pathjoin(dirname(configpath), mapfile))
        
    elif rawprovider.has_key('class'):
        _class = Providers.loadProviderByClass(rawprovider['class'])
        kwargs = rawprovider.get('kwargs', {})
        kwargs = dict( [(str(k), v) for (k, v) in kwargs.items()] )

    else:
        raise Exception('Missing required provider name or class: %s' % dumpjsons(rawprovider))
    
    layer = Core.Layer(config, projection)
    layer.provider = _class(layer, **kwargs)
    
    return layer

def getTypeByExtension(extension):
    """ Get mime-type and PIL format by file extension.
    """
    if extension.lower() == 'png':
        return 'image/png', 'PNG'

    elif extension.lower() == 'jpg':
        return 'image/jpeg', 'JPEG'

    else:
        raise Exception('Unknown extension: "%s"' % extension)
