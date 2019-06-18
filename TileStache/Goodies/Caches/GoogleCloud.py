#!/usr/bin/env python
""" Caches tiles to Google Cloud Storage.

Requires google-cloud-storage==1.3.1

Example configuration:

  "cache": {
    "class": "TileStache.Goodies.Caches.GoogleCloud:Cache",
    "kwargs": {
      "bucket": "<bucket name>",
    }
  }

cache parameters:

  bucket
    Required bucket name for GS. If it doesn't exist, it will be created.

"""

from time import time, sleep as _sleep
from mimetypes import guess_type


# URI scheme for Google Cloud Storage.
GOOGLE_STORAGE = 'gs'
# URI scheme for accessing local files.
LOCAL_FILE = 'file'

try:
    import google.cloud.storage
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
    def __init__(self, bucket):
        self.storage_client = google.cloud.storage.Client()
        self.bucket = bucket

    def get_blob(self, path):
        return self.storage_client.bucket(self.bucket).blob(path)

    def lock(self, layer, coord, format):
        """ Acquire a cache lock for this tile.

            Returns nothing, but blocks until the lock has been acquired.
        """
        key_name = tile_key(layer, coord, format)
        due = time() + layer.stale_lock_timeout

        while time() < due:
            if not self.get_blob(key_name+'-lock').exists():
                break

            _sleep(.2)

        blob = self.get_blob(key_name + '-lock')
        blob.upload_from_string('locked.', content_type='text/plain')

    def unlock(self, layer, coord, format):
        """ Release a cache lock for this tile.
        """
        key_name = tile_key(layer, coord, format)
        try:
          self.get_blob(key_name+'-lock').delete()
        except:
          pass

    def remove(self, layer, coord, format):
        """ Remove a cached tile.
        """
        key_name = tile_key(layer, coord, format)
        self.get_blob(key_name).delete()

    def read(self, layer, coord, format):
        """ Read a cached tile.
        """
        key_name = tile_key(layer, coord, format)
        blob = self.get_blob(key_name)

        if blob.exists() is False:
            return None

        if layer.cache_lifespan:
            t = timegm(strptime(key.last_modified, '%a, %d %b %Y %H:%M:%S %Z'))

            if (time() - t) > layer.cache_lifespan:
                return None

        return blob.download_as_string()

    def save(self, body, layer, coord, format):
        """ Save a cached tile.
        """
        key_name = tile_key(layer, coord, format)
        blob = self.get_blob(key_name)

        content_type, encoding = guess_type('example.' + format)
        blob.upload_from_string(body, content_type=content_type)
        blob.make_public()
