""" Caches tiles to Redis

Requires redis-py and redis-server
  https://pypi.python.org/pypi/redis/
  http://redis.io/

  sudo apt-get install redis-server
  pip install redis


Example configuration:

  "cache": {
    "name": "Redis",
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "key prefix": "unique-id"
  }

Redis cache parameters:

  host
    Defaults to "localhost" if omitted.

  port
    Integer; Defaults to 6379 if omitted.

  db
    Integer; Redis database number, defaults to 0 if omitted.

  key prefix
    Optional string to prepend to generated key.
    Useful when running multiple instances of TileStache
    that share the same Redis database to avoid key
    collisions (though the prefered solution is to use a different
    db number). The key prefix will be prepended to the
    key name. Defaults to "".
    

"""
from __future__ import absolute_import
from time import time as _time, sleep as _sleep

# We enabled absolute_import because case insensitive filesystems
# cause this file to be loaded twice (the name of this file
# conflicts with the name of the module we want to import).
# Forcing absolute imports fixes the issue.

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
    def __init__(self, host="localhost", port=6379, db=0, key_prefix=''):
        self.host = host
        self.port = port
        self.db = db
        self.conn = redis.Redis(host=self.host, port=self.port, db=self.db)
        self.key_prefix = key_prefix


    def lock(self, layer, coord, format):
        """ Acquire a cache lock for this tile.
            Returns nothing, but blocks until the lock has been acquired.
        """
        key = tile_key(layer, coord, format, self.key_prefix) + "-lock" 
        due = _time() + layer.stale_lock_timeout

        while _time() < due:
            if self.conn.setnx(key, 'locked.'):
                return

            _sleep(.2)

        self.conn.set(key, 'locked.')
        return
        
    def unlock(self, layer, coord, format):
        """ Release a cache lock for this tile.
        """
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

        # note: setting ex=0 will raise an error
        cache_lifespan = layer.cache_lifespan
        if cache_lifespan == 0:
            cache_lifespan = None

        self.conn.set(key, body, ex=cache_lifespan)
