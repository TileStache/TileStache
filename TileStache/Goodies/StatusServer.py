from os import getpid
from time import time
from hashlib import md5

from redis import StrictRedis

import TileStache

_keep = 20

def update_status(msg):
    """
    """
    pid = getpid()
    red = StrictRedis()
    key = 'pid-%d-statuses' % pid
    msg = '%.3f %s' % (time(), msg)
    
    red.lpush(key, msg)
    red.expire(key, 60 * 60)
    red.ltrim(key, 0, _keep)

def get_recent():
    """
    """
    pid = getpid()
    red = StrictRedis()
    
    messages = []

    for key in red.keys('pid-*-statuses'):
        try:
            now = time()
            pid = int(key.split('-')[1])
            msgs = [msg.split(' ', 1) for msg in red.lrange(key, 0, _keep)]
            msgs = [(now - float(t), pid, msg) for (t, msg) in msgs]
        except:
            continue
        else:
            messages += msgs
    
    messages.sort() # youngest-first
    return messages[:100]

def nice_time(time):
    if time < 15:
        return 'moments'
    if time < 90:
        return '%d seconds' % time
    if time < 60 * 60 * 1.5:
        return '%d minutes' % (time / 60.)
    if time < 24 * 60 * 60 * 1.5:
        return '%d hours' % (time / 3600.)
    if time < 7 * 24 * 60 * 60 * 1.5:
        return '%d days' % (time / 86400.)
    if time < 30 * 24 * 60 * 60 * 1.5:
        return '%d weeks' % (time / 604800.)

    return '%d months' % (time / 2592000.)

def pid_indent(pid):
    hash = md5(str(pid))
    number = int(hash.hexdigest(), 16)
    indent = number % 64
    return indent

def status_response():
    """
    """
    lines = ['%d' % time(), '----------']
    
    for (elapsed, pid, message) in get_recent():
        line = [' ' * pid_indent(pid)]
        line += [str(pid), message + ',']
        line += [nice_time(elapsed), 'ago']
        lines.append(' '.join(line))
    
    return '\n'.join(lines)

class WSGIServer (TileStache.WSGITileServer):
    """ 
        
        Inherits the constructor from TileStache WSGI, which just loads
        a TileStache configuration file into self.config.
    """
    def __init__(self, config, autoreload=False):
        """
        """
        TileStache.WSGITileServer.__init__(self, config, autoreload)
        self.config.cache = CacheWrap(self.config.cache)

        update_status('Created')
        
    def __call__(self, environ, start_response):
        """
        """
        start = time()

        if environ['PATH_INFO'] == '/status':
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return status_response()

        if environ['PATH_INFO'] == '/favicon.ico':
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return ''

        update_status('Started %s' % environ['PATH_INFO'])
        response = TileStache.WSGITileServer.__call__(self, environ, start_response)

        update_status('Finished %s in %.3f seconds' % (environ['PATH_INFO'], time() - start))
        return response
        
    def __del__(self):
        """
        """
        update_status('Destroyed')

class CacheWrap:

    def __init__(self, cache):
        self.cache = cache
    
    def lock(self, layer, coord, format):
        start = time()
        update_status('Attempted cache lock')

        self.cache.lock(layer, coord, format)
        update_status('Got cache lock in %.3f seconds' % (time() - start))
    
    def unlock(self, layer, coord, format):
        return self.cache.unlock(layer, coord, format)
    
    def remove(self, layer, coord, format):
        return self.cache.remove(layer, coord, format)
    
    def read(self, layer, coord, format):
        return self.cache.read(layer, coord, format)
      
    def save(self, body, layer, coord, format):
        return self.cache.save(body, layer, coord, format)
