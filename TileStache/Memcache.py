""" Caches tiles to Memcache.

Requires pylibmc:
  http://pypi.python.org/pypi/pylibmc

Example configuration (with SASL authentication):

  "cache": {
    "name": "Memcache",
    "servers": ["127.0.0.1:11211"],
    "username": "user",
    "password": "pass",
    "revision": 0
  }

Memcache cache parameters:

  servers
    Optional array of servers, list of "{host}:{port}" pairs.
    Defaults to ["127.0.0.1:11211"] if omitted.

  revision
    Optional revision number for mass-expiry of cached tiles
    regardless of lifespan. Defaults to 0.

  username
    Optional username string used for SASL authentication

  password
    Optional password string used for SASL authentication
"""
from time import time as _time, sleep as _sleep

try:
    from pylibmc import Client
except ImportError:
    # at least we can build the documentation
    pass

def tile_key(layer, coord, format, rev):
    """ Return a tile key string.
    """
    name = layer.name()
    tile = '%(zoom)d/%(column)d/%(row)d' % coord.__dict__
    return str('%(rev)s/%(name)s/%(tile)s.%(format)s' % locals())

class Cache:
    """
    """
    def __init__(self, servers=['127.0.0.1:11211'], revision=0, username=None, password=None):
        self.servers = servers
        self.revision = revision
        self.username = username
        self.password = password

    @property
    def mem(self):
        if getattr(self, 'client', None) is None:
            if self.username and self.password:
                self.client = Client(
                    servers=self.servers,
                    username=self.username,
                    password=self.password,
                    binary=True
                )
            else:
                self.client = Client(self.servers)
        return self.client

    def lock(self, layer, coord, format):
        """ Acquire a cache lock for this tile.

            Returns nothing, but blocks until the lock has been acquired.
        """
        key = tile_key(layer, coord, format, self.revision)
        due = _time() + layer.stale_lock_timeout

        while _time() < due:
            if self.mem.add(key + '-lock', 'locked.',
                    layer.stale_lock_timeout):
                return

            _sleep(.2)

        self.mem.set(key + '-lock', 'locked.', layer.stale_lock_timeout)
        return

    def unlock(self, layer, coord, format):
        """ Release a cache lock for this tile.
        """
        key = tile_key(layer, coord, format, self.revision)

        self.mem.delete(key + '-lock')

    def remove(self, layer, coord, format):
        """ Remove a cached tile.
        """
        key = tile_key(layer, coord, format, self.revision)

        self.mem.delete(key)

    def read(self, layer, coord, format):
        """ Read a cached tile.
        """
        key = tile_key(layer, coord, format, self.revision)

        value = self.mem.get(key)

        return value

    def save(self, body, layer, coord, format):
        """ Save a cached tile.
        """
        key = tile_key(layer, coord, format, self.revision)

        self.mem.set(key, body, layer.cache_lifespan or 0)
