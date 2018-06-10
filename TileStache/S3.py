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
    Optional access key ID for your S3 account.

  secret
    Optional secret access key for your S3 account.

  policy
    Optional S3 ACL policy for uploaded tiles. Default is 'public-read'.

  use_locks
    Optional boolean flag for whether to use the locking feature on S3.
    True by default. A good reason to set this to false would be the
    additional price and time required for each lock set in S3.

  path
    Optional path under bucket to use as the cache dir. ex. 'cache' will
    put tiles under <bucket>/cache/

  reduced_redundancy
    If set to true, use S3's Reduced Redundancy Storage feature. Storage is
    cheaper but has lower redundancy on Amazon's servers. Defaults to false.

Access and secret keys are under "Security Credentials" at your AWS account page:
  http://aws.amazon.com/account/

When access or secret are not provided, the environment variables
AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY will be used
    http://docs.pythonboto.org/en/latest/s3_tut.html#creating-a-connection
"""
from time import time as _time, sleep as _sleep
from mimetypes import guess_type
from time import strptime, time
from calendar import timegm
from .py3_compat import reduce

try:
    from boto.s3.bucket import Bucket as S3Bucket
    from boto.s3.connection import S3Connection
except ImportError:
    # at least we can build the documentation
    pass

def tile_key(layer, coord, format, path = ''):
    """ Return a tile key string.
    """
    path = path.strip('/')
    name = layer.name()
    tile = '%(zoom)d/%(column)d/%(row)d' % coord.__dict__
    ext = format.lower()

    return str('%(path)s/%(name)s/%(tile)s.%(ext)s' % locals())

class Cache:
    """
    """
    def __init__(self, bucket, access=None, secret=None, use_locks=True, path='', reduced_redundancy=False, policy='public-read'):
        self.bucket = S3Bucket(S3Connection(access, secret), bucket)
        self.use_locks = bool(use_locks)
        self.path = path
        self.reduced_redundancy = reduced_redundancy
        self.policy = policy

    def lock(self, layer, coord, format):
        """ Acquire a cache lock for this tile.

            Returns nothing, but blocks until the lock has been acquired.
            Does nothing and returns immediately if `use_locks` is false.
        """
        if not self.use_locks:
            return

        key_name = tile_key(layer, coord, format, self.path)
        due = _time() + layer.stale_lock_timeout

        while _time() < due:
            if not self.bucket.get_key(key_name+'-lock'):
                break

            _sleep(.2)

        key = self.bucket.new_key(key_name+'-lock')
        key.set_contents_from_string('locked.', {'Content-Type': 'text/plain'}, reduced_redundancy=self.reduced_redundancy)

    def unlock(self, layer, coord, format):
        """ Release a cache lock for this tile.
        """
        if not self.use_locks:
            return

        key_name = tile_key(layer, coord, format, self.path)
        self.bucket.delete_key(key_name+'-lock')

    def remove(self, layer, coord, format):
        """ Remove a cached tile.
        """
        key_name = tile_key(layer, coord, format, self.path)
        self.bucket.delete_key(key_name)

    def read(self, layer, coord, format):
        """ Read a cached tile.
        """
        key_name = tile_key(layer, coord, format, self.path)
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
        key_name = tile_key(layer, coord, format, self.path)
        key = self.bucket.new_key(key_name)

        content_type, encoding = guess_type('example.'+format)
        headers = content_type and {'Content-Type': content_type} or {}

        key.set_contents_from_string(body, headers, policy=self.policy, reduced_redundancy=self.reduced_redundancy)
