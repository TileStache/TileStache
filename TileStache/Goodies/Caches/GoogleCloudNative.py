#!/usr/bin/env python
""" Caches tiles to Google Cloud Storage using Google's python client.

Requires the google-cloud-storage library (1.6.0+):
  https://pypi.python.org/pypi/google-cloud-storage

...as well as the pytz module, because timezones.

Example configuration:

  "cache": {
    "class": "TileStache.Goodies.Caches.GoogleCloudNative:Cache",
    "kwargs": {
      "bucket": "<bucket name>"
    }
  }

Cache parameters:

  bucket
    Required bucket name. The bucket must exist.

  use_locks
    Optional flag for whether to use the locking feature.
    True by default. A good reason to set this to false would be the
    additional price and time required for each lock set.

Authentication is taken from your environment according to these docs:
  https://googlecloudplatform.github.io/google-cloud-python/latest/core/auth.html
"""
import pytz
from time import time, sleep
from datetime import datetime
from mimetypes import guess_type


try:
    from google.cloud import storage
    from google.cloud.exceptions import NotFound
except ImportError:
    # at least we can build the documentation
    pass


def tile_key(layer, coord, format):
    """ Return a tile key string.
    """
    name = layer.name()
    tile = '%(zoom)d/%(column)d/%(row)d' % coord.__dict__
    ext = format.lower()

    return str('%(name)s/%(tile)s.%(ext)s' % locals())


class Cache:
    """
    """
    def __init__(self, bucket, use_locks=True):
        client = storage.Client()
        self.bucket = client.get_bucket(bucket)
        self.use_locks = bool(use_locks)

    def lock(self, layer, coord, format):
        """ Acquire a cache lock for this tile.

            Returns nothing, but blocks until the lock has been acquired.
        """
        if not self.use_locks:
            return

        lock_name = tile_key(layer, coord, format) + '-lock'
        due = time() + layer.stale_lock_timeout

        while time() < due:
            if not self.bucket.get_blob(lock_name):
                break

            sleep(.2)

        key = self.bucket.blob(lock_name)
        key.upload_from_string('locked.')

    def unlock(self, layer, coord, format):
        """ Release a cache lock for this tile.
        """
        lock_name = tile_key(layer, coord, format) + '-lock'
        try:
            self.bucket.delete_blob(lock_name)
        except NotFound:
            pass

    def remove(self, layer, coord, format):
        """ Remove a cached tile.
        """
        if not self.use_locks:
            return

        key_name = tile_key(layer, coord, format)
        self.bucket.delete_blob(key_name)

    def read(self, layer, coord, format):
        """ Read a cached tile.
        """
        key_name = tile_key(layer, coord, format)
        key = self.bucket.get_blob(key_name)

        if key is None:
            return None

        if layer.cache_lifespan:
            if (datetime.now(pytz.utc) - key.updated).total_seconds() > layer.cache_lifespan:
                return None

        return key.download_as_string()

    def save(self, body, layer, coord, format):
        """ Save a cached tile.
        """
        key_name = tile_key(layer, coord, format)
        key = self.bucket.blob(key_name)

        content_type, _ = guess_type('example.' + format)
        if content_type is None:
            content_type = 'text/plain'

        key.upload_from_string(body, content_type)
