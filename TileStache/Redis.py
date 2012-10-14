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
import logging

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
        self.r = redis.from_url(url)

    def lock(self, layer, coord, format):
        # IMPLEMENT LOCKING!!!

        # key = tile_key(layer, coord, format)
        # due = _time() + layer.stale_lock_timeout

        # while _time() < due:
        #     if self.mem.setnx(key + '-lock', layer.stale_lock_timeout):
        #         return
        #     _sleep(.2)

        # self.mem.setex(key + '-lock', layer.stale_lock_timeout, 'locked.')
        logging.debug('lock: ')
        return

    def unlock(self, layer, coord, format):
        key = tile_key(layer, coord, format)
        logging.debug('unlock: ' + key)
        self.r.delete(key + '-lock')

    def remove(self, layer, coord, format):
        key = tile_key(layer, coord, format)
        logging.debug('remove: ' + key)
        self.r.delete(key)

    def read(self, layer, coord, format):
        key = tile_key(layer, coord, format)
        logging.debug('read: ' + key)
        value = self.r.get(key)
        logging.debug('value: ' + value)
        return value

    def save(self, body, layer, coord, format):
        key = tile_key(layer, coord, format)
        logging.debug('save: ' + key)
        self.r.setex(key, layer.cache_lifespan or 0, body)
