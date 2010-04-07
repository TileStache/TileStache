""" The input/output bits of TileStache.
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

class Configuration:
    """ A complete site configuration, with a collection of Layer objects.
    """
    def __init__(self, cache):
        self.cache = cache
        self.layers = {}

def buildConfiguration(config_dict, dirpath='.'):
    """ Build a configuration dictionary into a Configuration object.
    """
    cache_dict = config_dict.get('cache', {})
    cache = _parseConfigfileCache(cache_dict, dirpath)
    
    config = Configuration(cache)
    
    for (name, layer_dict) in config_dict.get('layers', {}).items():
        config.layers[name] = _parseConfigfileLayer(layer_dict, config, dirpath)

    return config

def _parseConfigfileCache(cache_dict, dirpath):
    """ Used by parseConfigfile() to parse just the cache parts of a config.
    """
    if cache_dict['name'].lower() == 'test':
        cache = Caches.Test(lambda msg: stderr.write(msg + '\n'))

    elif cache_dict['name'].lower() == 'disk':
        cachepath = realpath(pathjoin(dirpath, cache_dict['path']))
        kwargs = {}
        
        if cache_dict.has_key('umask'):
            kwargs['umask'] = int(cache_dict['umask'], 8)

        cache = Caches.Disk(cachepath, **kwargs)

    else:
        raise Exception('Unknown cache: %s' % cache_dict['name'])

    return cache

def _parseConfigfileLayer(layer_dict, config, dirpath):
    """ Used by parseConfigfile() to parse just the layer parts of a config.
    """
    projection = layer_dict.get('projection', '')
    
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
            kwargs['url'] = provider_dict['url']
        
    elif provider_dict.has_key('class'):
        _class = Providers.loadProviderByClass(provider_dict['class'])
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
