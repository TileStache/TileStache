""" The input/output bits of TileStache.
"""

from os.path import realpath, dirname, join as pathjoin

try:
    from json import load as loadjson
    from json import dumps as dumpjsons
except ImportError:
    from simplejson import load as loadjson
    from simplejson import dumps as dumpjsons

import Core
import Caches
import Providers

def parseConfigfile(configpath):
    """ Parse a configuration file path and return a Configuration object.
    """
    raw = loadjson(open(configpath, 'r'))
    return buildConfiguration(raw, dirname(configpath))

def buildConfiguration(raw, dirpath):
    """
    """
    rawcache = raw.get('cache', {})
    cache = _parseConfigfileCache(rawcache, dirpath)
    
    config = Core.Configuration(cache)
    
    for (name, rawlayer) in raw.get('layers', {}).items():
        config.layers[name] = _parseConfigfileLayer(rawlayer, config, dirpath)

    return config

def _parseConfigfileCache(rawcache, dirpath):
    """ Used by parseConfigfile() to parse just the cache parts of a config.
    """
    if rawcache['name'].lower() == 'test':
        cache = Caches.Test(lambda msg: stderr.write(msg + '\n'))

    elif rawcache['name'].lower() == 'disk':
        cachepath = realpath(pathjoin(dirpath, rawcache['path']))
        kwargs = {}
        
        if rawcache.has_key('umask'):
            kwargs['umask'] = int(rawcache['umask'], 8)

        cache = Caches.Disk(cachepath, **kwargs)
    else:
        raise Exception('Unknown cache: %s' % rawcache['name'])

    return cache

def _parseConfigfileLayer(rawlayer, config, dirpath):
    """ Used by parseConfigfile() to parse just the layer parts of a config.
    """
    projection = rawlayer.get('projection', '')
    rawprovider = rawlayer['provider']

    if rawprovider.has_key('name'):
        _class = Providers.getProviderByName(rawprovider['name'])
        kwargs = {}
        
        if _class is Providers.Mapnik:
            mapfile = rawprovider['mapfile']
            kwargs['mapfile'] = realpath(pathjoin(dirpath, mapfile))
        
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
