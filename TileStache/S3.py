try:
    from boto.s3.connection import S3Connection
    from boto.s3.bucket import Bucket
    from boto.s3.key import Key
except ImportError:
    # at least we can build the documentation
    pass

class Cache:
    """
    """
    def __init__(self, bucket, access, secret):
        self.bucket = bucket
        self.access = access
        self.secret = secret

    def lock(self, layer, coord, format):
        """ Acquire a cache lock for this tile.
        
            Returns nothing, but blocks until the lock has been acquired.
        """
        raise NotImplementedError
        
    def unlock(self, layer, coord, format):
        """ Release a cache lock for this tile.
        """
        raise NotImplementedError
        
    def read(self, layer, coord, format):
        """ Read a cached tile.
        """
        raise NotImplementedError
        
    def save(self, body, layer, coord, format):
        """ Save a cached tile.
        """
        raise NotImplementedError
