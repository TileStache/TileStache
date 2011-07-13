""" Caches tiles to Amazon S3.

Requires boto (2.0+):
  http://pypi.python.org/pypi/boto

Example configuration:

  "cache": {
    "name": "S3",
    "bucket": "<bucket name>",
    "access": "<access key>",
    "secret": "<secret key>"
  }

S3 cache parameters:

  bucket
    Required bucket name for S3. If it doesn't exist, it will be created.

  access
    Required access key ID for your S3 account.

  secret
    Required secret access key for your S3 account.

Access and secret keys are under "Security Credentials" at your AWS account page:
  http://aws.amazon.com/account/
"""
from time import time as _time, sleep as _sleep
from mimetypes import guess_type
from time import strptime, time
from calendar import timegm

try:
    from boto.s3.bucket import Bucket as S3Bucket
    from boto.s3.connection import S3Connection
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
        self.bucket = S3Bucket(S3Connection(access, secret), bucket)

    def lock(self, layer, coord, format):
        """ Acquire a cache lock for this tile.
        
            Returns nothing, but blocks until the lock has been acquired.
        """
        key_name = tile_key(layer, coord, format)
        due = _time() + layer.stale_lock_timeout
        
        while _time() < due:
            if not self.bucket.get_key(key_name+'-lock'):
                break
            
            _sleep(.2)
        
        key = self.bucket.new_key(key_name+'-lock')
        key.set_contents_from_string('locked.', {'Content-Type': 'text/plain'})
        
    def unlock(self, layer, coord, format):
        """ Release a cache lock for this tile.
        """
        key_name = tile_key(layer, coord, format)
        self.bucket.delete_key(key_name+'-lock')
        
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
