""" Caches tiles to Redis

Requires redis-py
  https://pypi.python.org/pypi/redis/

Example configuration:

  "cache": {
    "name": "Redis",
    "server": "localhost:6379:0",
    "key prefix": "unique-id"
  }

Redis cache parameters:

  server
    "host:port:db" 
    Defaults to "localhost:6379:0" if omitted.

  key prefix
    Optional string to prepend to generated key.
    Useful when running multiple instances of TileStache
    that share the same Redis database to avoid key
    collisions (though the prefered solution is to use a different
    db number). The key prefix will be prepended to the
    key name. Defaults to "".
    

"""
from time import time as _time, sleep as _sleep

try:
    import redis
except ImportError:
    # at least we can build the documentation
    pass

def tile_key(layer, coord, format, key_prefix):
    """ Return a tile key string.
    """
    name = layer.name()
    tile = '%(zoom)d/%(column)d/%(row)d' % coord.__dict__
    key = str('%(key_prefix)s/%(name)s/%(tile)s.%(format)s' % locals())
    return key

class Cache:
    """
    """
    def __init__(self, server='127.0.0.1:6379:0', key_prefix=''):
        self.host, self.port, self.db = server.split(":")
        self.conn = redis.Redis(host=self.host, port=int(self.port), db=int(self.db))
        self.key_prefix = key_prefix

    def lock(self, layer, coord, format):
        """ Acquire a cache lock for this tile.
            Returns nothing, but blocks until the lock has been acquired.
            NOT IMPLEMENTED YET
        """
        return
        
    def unlock(self, layer, coord, format):
        """ Release a cache lock for this tile.
            NOT IMPLEMENTED YET
        """
        return
        key = tile_key(layer, coord, format, self.key_prefix)
        self.conn.delete(key+'-lock')
        
    def remove(self, layer, coord, format):
        """ Remove a cached tile.
        """
        key = tile_key(layer, coord, format, self.key_prefix)
        self.conn.delete(key)
        
    def read(self, layer, coord, format):
        """ Read a cached tile.
        """
        key = tile_key(layer, coord, format, self.key_prefix)
        value = self.conn.get(key)
        return value
        
    def save(self, body, layer, coord, format):
        """ Save a cached tile.
        """
        key = tile_key(layer, coord, format, self.key_prefix)
        self.conn.set(key, body)  #, layer.cache_lifespan or 0)
