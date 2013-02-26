#!/usr/bin/env python
""" Caches tiles to Google Cloud Storage.

Requires boto (2.0+):
  http://pypi.python.org/pypi/boto

Example configuration:

  "cache": {
    "name": "TileStache.Goodies.Caches.GoogleCloud:Cache",
    "kwargs": {
      "bucket": "<bucket name>",
      "access": "<access key>",
      "secret": "<secret key>"
    }
  }

cache parameters:

  bucket
    Required bucket name for GS. If it doesn't exist, it will be created.

  access
    Required access key ID for your GS account.

  secret
    Required secret access key for your GS account.

"""
from time import time
from mimetypes import guess_type


# URI scheme for Google Cloud Storage.
GOOGLE_STORAGE = 'gs'
# URI scheme for accessing local files.
LOCAL_FILE = 'file'

try:
    import boto
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
    def __init__(self, bucket, access, secret):
        config = boto.config
        config.add_section('Credentials')
        config.set('Credentials', 'gs_access_key_id', access)
        config.set('Credentials', 'gs_secret_access_key', secret)

        uri = boto.storage_uri('', GOOGLE_STORAGE)
        for b in uri.get_all_buckets():
          if b.name == bucket:
            self.bucket = b
        #TODO: create bucket if not found

    def lock(self, layer, coord, format):
        """ Acquire a cache lock for this tile.
        
            Returns nothing, but blocks until the lock has been acquired.
        """
        key_name = tile_key(layer, coord, format)
        due = time() + layer.stale_lock_timeout
        
        while time() < due:
            if not self.bucket.get_key(key_name+'-lock'):
                break
            
            _sleep(.2)
        
        key = self.bucket.new_key(key_name+'-lock')
        key.set_contents_from_string('locked.', {'Content-Type': 'text/plain'})
        
    def unlock(self, layer, coord, format):
        """ Release a cache lock for this tile.
        """
        key_name = tile_key(layer, coord, format)
        try:
          self.bucket.delete_key(key_name+'-lock')
        except:
          pass
        
    def remove(self, layer, coord, format):
        """ Remove a cached tile.
        """
        key_name = tile_key(layer, coord, format)
        self.bucket.delete_key(key_name)
        
    def read(self, layer, coord, format):
        """ Read a cached tile.
        """
        key_name = tile_key(layer, coord, format)
        key = self.bucket.get_key(key_name)
        
        if key is None:
            return None
        
        if layer.cache_lifespan:
            t = timegm(strptime(key.last_modified, '%a, %d %b %Y %H:%M:%S %Z'))

            if (time() - t) > layer.cache_lifespan:
                return None
        
        return key.get_contents_as_string()
        
    def save(self, body, layer, coord, format):
        """ Save a cached tile.
        """
        key_name = tile_key(layer, coord, format)
        key = self.bucket.new_key(key_name)
        
        content_type, encoding = guess_type('example.'+format)
        headers = content_type and {'Content-Type': content_type} or {}
        
        key.set_contents_from_string(body, headers, policy='public-read')
