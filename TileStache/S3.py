from time import time as _time, sleep as _sleep
from mimetypes import guess_type

try:
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
        self.bucket = S3Connection(access, secret).create_bucket(bucket)

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
        
        return key.get_contents_as_string()
        
    def save(self, body, layer, coord, format):
        """ Save a cached tile.
        """
        key_name = tile_key(layer, coord, format)
        key = self.bucket.new_key(key_name)
        
        content_type, encoding = guess_type('example.'+format)
        headers = content_type and {'Content-Type': content_type} or {}
        
        key.set_contents_from_string(body, headers, policy='public-read')
