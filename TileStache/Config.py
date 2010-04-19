""" The configuration bits of TileStache.
"""

from sys import stderr
from os.path import realpath, join as pathjoin

try:
    from json import dumps as json_dumps
except ImportError:
    from simplejson import dumps as json_dumps

import Core
import Caches
import Providers
import Geography

class Configuration:
    """ A complete site configuration, with a collection of Layer objects.
    """
    def __init__(self, cache, path):
        self.cache = cache
        self.path = path
        self.layers = {}

def buildConfiguration(config_dict, dirpath='.'):
    """ Build a configuration dictionary into a Configuration object.
    """
    cache_dict = config_dict.get('cache', {})
    cache = _parseConfigfileCache(cache_dict, dirpath)
    
    config = Configuration(cache, realpath(dirpath))
    
    for (name, layer_dict) in config_dict.get('layers', {}).items():
        config.layers[name] = _parseConfigfileLayer(layer_dict, config, dirpath)

    return config

def _parseConfigfileCache(cache_dict, dirpath):
    """ Used by parseConfigfile() to parse just the cache parts of a config.
    """
    if cache_dict.has_key('name'):
        _class = Caches.getCacheByName(cache_dict['name'])
        kwargs = {}
        
        if _class is Caches.Test:
            kwargs['logfunc'] = lambda msg: stderr.write(msg + '\n')
    
        elif _class is Caches.Disk:
            kwargs['path'] = realpath(pathjoin(dirpath, cache_dict['path']))
            
            if cache_dict.has_key('umask'):
                kwargs['umask'] = int(cache_dict['umask'], 8)
    
        else:
            raise Exception('Unknown cache: %s' % cache_dict['name'])
        
    elif cache_dict.has_key('class'):
        _class = loadClassPath(cache_dict['class'])
        kwargs = cache_dict.get('kwargs', {})
        kwargs = dict( [(str(k), v) for (k, v) in kwargs.items()] )

    else:
        raise Exception('Missing required cache name or class: %s' % json_dumps(cache_dict))

    cache = _class(**kwargs)

    return cache

def _parseConfigfileLayer(layer_dict, config, dirpath):
    """ Used by parseConfigfile() to parse just the layer parts of a config.
    """
    projection = layer_dict.get('projection', 'spherical mercator')
    projection = Geography.getProjectionByName(projection)
    
    #
    # Do the metatile
    #

    meta_dict = layer_dict.get('metatile', {})
    kwargs = {}
    
    for k in ('buffer', 'rows', 'columns'):
        if meta_dict.has_key(k):
            kwargs[k] = int(meta_dict[k])
    
    metatile = Core.Metatile(**kwargs)
    
    #
    # Do the provider
    #

    provider_dict = layer_dict['provider']

    if provider_dict.has_key('name'):
        _class = Providers.getProviderByName(provider_dict['name'])
        kwargs = {}
        
        if _class is Providers.Mapnik:
            mapfile = provider_dict['mapfile']
            kwargs['mapfile'] = realpath(pathjoin(dirpath, mapfile))
        
        elif _class is Providers.Proxy:
            if provider_dict.has_key('url'):
                kwargs['url'] = provider_dict['url']
            if provider_dict.has_key('provider'):
                kwargs['provider_name'] = provider_dict['provider']
        
    elif provider_dict.has_key('class'):
        _class = loadClassPath(provider_dict['class'])
        kwargs = provider_dict.get('kwargs', {})
        kwargs = dict( [(str(k), v) for (k, v) in kwargs.items()] )

    else:
        raise Exception('Missing required provider name or class: %s' % json_dumps(provider_dict))
    
    #
    # Finish him!
    #

    layer = Core.Layer(config, projection, metatile)
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

def loadClassPath(classpath):
    """ Load external class based on a path.
    
        Example classpath: "Module.Submodule.Classname",
    """
    classpath = classpath.split('.')
    module = __import__('.'.join(classpath[:-1]), fromlist=classpath[-1])
    _class = getattr(module, classpath[-1])
    
    return _class
