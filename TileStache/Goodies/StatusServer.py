from os import getpid
from time import time

from redis import StrictRedis

from TileStache import WSGITileServer

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

class WSGIServer (WSGITileServer):
    """ WSGI Application that can handle WMS-style requests for static images.
        
        Inherits the constructor from TileStache WSGI, which just loads
        a TileStache configuration file into self.config.
        
        WSGITileServer autoreload argument is ignored, though. For now.
    """
    def __call__(self, environ, start_response):
        """
        """
        if environ['PATH_INFO'] == '/status':
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return str(get_recent())

        if environ['PATH_INFO'] == '/favicon.ico':
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return ''

        update_status('Started %(PATH_INFO)s' % environ)
        response = WSGITileServer.__call__(self, environ, start_response)
        update_status('Finished %(PATH_INFO)s' % environ)
        return response
