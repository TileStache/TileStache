""" Caches tiles to Redis.

Requires redis-py:
  https://github.com/andymccurdy/redis-py

Example configuration:

  "cache": {
    "name": "redis",
    "kwargs": {
      "url": "redis://localhost"
    }
  }
"""

try:
    import redis
except ImportError:
    # at least we can build the documentation
    pass

def tile_key(layer, coord, format, rev=0):
    name = layer.name()
    tile = '%(zoom)d/%(column)d/%(row)d' % coord.__dict__
    return str('%(rev)s/%(name)s/%(tile)s.%(format)s' % locals())

class Cache:
    def __init__(self, url='redis://localhost'):
        self.url = url

    @property
    def mem(self):
        if getattr(self, 'r', None) is None:
            self.r = redis.from_url(self.url)
        return self.r

    def lock(self, layer, coord, format):
        key = tile_key(layer, coord, format)
        due = _time() + layer.stale_lock_timeout

        while _time() < due:
            if self.mem.get(key + '-lock', layer.stale_lock_timeout):
                return
            _sleep(.2)

        self.mem.setex(key + '-lock', layer.stale_lock_timeout, 'locked.')
        return

    def unlock(self, layer, coord, format):
        key = tile_key(layer, coord, format)
        self.mem.del(key + '-lock')

    def remove(self, layer, coord, format):
        key = tile_key(layer, coord, format)
        self.mem.del(key)

    def read(self, layer, coord, format):
        key = tile_key(layer, coord, format)
        value = self.mem.get(key)
        return value

    def save(self, body, layer, coord, format):
        key = tile_key(layer, coord, format)
        self.mem.setex(key, layer.cache_lifespan or 0, body)
