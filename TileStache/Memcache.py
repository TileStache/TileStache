from time import time, sleep

try:
    from memcache import Client
except ImportError:
    # at least we can build the documentation
    pass

def tile_key(layer, coord, format, rev):
    """
    """
    name = layer.name()
    tile = '%(zoom)d/%(column)d/%(row)d' % coord.__dict__
    return str('%(rev)s/%(name)s/%(tile)s.%(format)s' % locals())

class Cache:

    def __init__(self, servers=['127.0.0.1:11211'], lifespan=0, revision=0):
        self.servers = servers
        self.lifespan = lifespan
        self.revision = revision

    def lock(self, layer, coord, format):
        mem = Client(self.servers)
        key = tile_key(layer, coord, format, self.revision)
        due = time() + layer.stale_lock_timeout
        
        try:
            while time() < due:
                if mem.add(key+'-lock', 'locked.', layer.stale_lock_timeout):
                    return
                
                sleep(.2)
            
            mem.set(key+'-lock', 'locked.', layer.stale_lock_timeout)
            return

        finally:
            mem.disconnect_all()
        
    def unlock(self, layer, coord, format):
        mem = Client(self.servers)
        key = tile_key(layer, coord, format, self.revision)
        
        mem.delete(key+'-lock')
        mem.disconnect_all()
        
    def read(self, layer, coord, format):
        mem = Client(self.servers)
        key = tile_key(layer, coord, format, self.revision)
        
        value = mem.get(key)
        mem.disconnect_all()
        
        return value
        
    def save(self, body, layer, coord, format):
        mem = Client(self.servers)
        key = tile_key(layer, coord, format, self.revision)
        
        mem.set(key, body, 120)
