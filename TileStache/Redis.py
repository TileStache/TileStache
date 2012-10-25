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

from time import time, sleep

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
        key = tile_key(layer, coord, format) + '-lock'
        expires = time() + layer.stale_lock_timeout + 1
        timeout = time() + (layer.stale_lock_timeout * 2)

        while time() < timeout:
            if self.mem.setnx(key, expires):
                # lock acquired
                return

            current_value = self.mem.get(key)

            if current_value and float(current_value) < time() and \
                self.mem.getset(key, expires) == current_value:
                    # We found an expired lock and nobody raced us to replacing it
                    return

            time.sleep(.2)

        raise Exception('Unable to acquire lock!')

    def unlock(self, layer, coord, format):
        key = tile_key(layer, coord, format) + 'lock'
        self.mem.delete(key)

    def remove(self, layer, coord, format):
        key = tile_key(layer, coord, format)
        self.mem.delete(key)

    def read(self, layer, coord, format):
        key = tile_key(layer, coord, format)
        value = self.mem.get(key)
        return value

    def save(self, body, layer, coord, format):
        key = tile_key(layer, coord, format)
        if layer.cache_lifespan:
            self.mem.setex(key, layer.cache_lifespan, body)
        else:
            self.mem.set(key, body)
