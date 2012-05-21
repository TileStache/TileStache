""" StatusServer is a replacement for WSGITileServer that saves per-process
    events to Redis and displays them in a chronological stream at /status.
    
    The internal behaviors of a running WSGI server can be hard to inspect,
    and StatusServer is designed to output data relevant to tile serving out
    to Redis where it can be gathered and inspected.
    
    Example usage, with gunicorn (http://gunicorn.org):
    
      gunicorn --bind localhost:8888 "TileStache.Goodies.StatusServer:WSGIServer('tilestache.cfg')"

    Example output, showing vertical alignment based on process ID:

      13235 Attempted cache lock, 2 minutes ago
      13235 Got cache lock in 0.001 seconds, 2 minutes ago
      13235 Started /osm/15/5255/12664.png, 2 minutes ago
      13235 Finished /osm/15/5255/12663.png in 0.724 seconds, 2 minutes ago
                         13233 Got cache lock in 0.001 seconds, 2 minutes ago
                         13233 Attempted cache lock, 2 minutes ago
                         13233 Started /osm/15/5249/12664.png, 2 minutes ago
                         13233 Finished /osm/15/5255/12661.png in 0.776 seconds, 2 minutes ago
                                     13234 Got cache lock in 0.001 seconds, 2 minutes ago
                                     13234 Attempted cache lock, 2 minutes ago
                                     13234 Started /osm/15/5254/12664.png, 2 minutes ago
                                     13234 Finished /osm/15/5249/12663.png in 0.466 seconds, 2 minutes ago
      13235 Attempted cache lock, 2 minutes ago
      13235 Got cache lock in 0.001 seconds, 2 minutes ago
      13235 Started /osm/15/5255/12663.png, 2 minutes ago
      13235 Finished /osm/15/5250/12664.png in 0.502 seconds, 2 minutes ago
                         13233 Got cache lock in 0.001 seconds, 2 minutes ago
                         13233 Attempted cache lock, 2 minutes ago
                         13233 Started /osm/15/5255/12661.png, 2 minutes ago
"""
from os import getpid
from time import time
from hashlib import md5

try:
    from redis import StrictRedis

except ImportError:
    #
    # Changes to the Redis API have led to incompatibilities between clients
    # and servers. Older versions of redis-py might be needed to communicate
    # with older server versions, such as the 1.2.0 that ships on Ubuntu Lucid.
    #
    # Ensure your Redis client and server match, potentially using pip
    # to specify a version number of the Python package to use, e.g.:
    #
    #   pip install -I "redis<=1.2.0"
    #
    from redis import Redis
    
    class StrictRedis (Redis):
        """ Compatibility class for older versions of Redis.
        """
        def lpush(self, name, value):
            # old Redis uses a boolean argument to name the list head.
            self.push(name, value, True)

        def expire(self, name, seconds):
            # old Redis expire can't be repeatedly updated.
            pass

import TileStache

_keep = 20

def update_status(msg, **redis_kwargs):
    """ Updated Redis with a message, prefix it with the current timestamp.
    
        Keyword args are passed directly to redis.StrictRedis().
    """
    pid = getpid()
    red = StrictRedis(**redis_kwargs)
    key = 'pid-%d-statuses' % pid
    msg = '%.6f %s' % (time(), msg)
    
    red.lpush(key, msg)
    red.expire(key, 60 * 60)
    red.ltrim(key, 0, _keep)

def delete_statuses(pid, **redis_kwargs):
    """
    """
    red = StrictRedis(**redis_kwargs)
    key = 'pid-%d-statuses' % pid
    red.delete(key)

def get_recent(**redis_kwargs):
    """ Retrieve recent messages from Redis, in reverse chronological order.
        
        Two lists are returned: one a single most-recent status message from
        each process, the other a list of numerous messages from each process.
        
        Each message is a tuple with floating point seconds elapsed, integer
        process ID that created it, and an associated text message such as
        "Got cache lock in 0.001 seconds" or "Started /osm/12/656/1582.png".
    
        Keyword args are passed directly to redis.StrictRedis().
    """
    pid = getpid()
    red = StrictRedis(**redis_kwargs)
    
    processes = []
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
            processes += msgs[:1]
    
    messages.sort() # youngest-first
    processes.sort() # youngest-first

    return processes, messages

def nice_time(time):
    """ Format a time in seconds to a string like "5 minutes".
    """
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
    """ Get an MD5-based indentation for a process ID.
    """
    hash = md5(str(pid))
    number = int(hash.hexdigest(), 16)
    indent = number % 32
    return indent

def status_response(**redis_kwargs):
    """ Retrieve recent messages from Redis and 
    """
    processes, messages = get_recent(**redis_kwargs)
    
    lines = ['%d' % time(), '----------']
    
    for (index, (elapsed, pid, message)) in enumerate(processes):
        if elapsed > 6 * 60 * 60:
            # destroy the process if it hasn't been heard from in 6+ hours
            delete_statuses(pid, **redis_kwargs)
            continue
    
        if elapsed > 10 * 60:
            # don't show the process if it hasn't been heard from in ten+ minutes
            continue
    
        line = '%03s. %05s %s, %s ago' % (str(index + 1), pid, message, nice_time(elapsed))
        lines.append(line)
    
    lines.append('----------')
    
    for (elapsed, pid, message) in messages[:250]:
        line = [' ' * pid_indent(pid)]
        line += [str(pid), message + ',']
        line += [nice_time(elapsed), 'ago']
        lines.append(' '.join(line))
    
    return str('\n'.join(lines))

class WSGIServer (TileStache.WSGITileServer):
    """ Create a WSGI application that can handle requests from any server that talks WSGI.
    
        Notable moments in the tile-making process such as time elapsed
        or cache lock events are sent as messages to Redis. Inherits the
        constructor from TileStache WSGI, which just loads a TileStache
        configuration file into self.config.
    """
    def __init__(self, config, redis_host='localhost', redis_port=6379):
        """
        """
        TileStache.WSGITileServer.__init__(self, config)

        self.redis_kwargs = dict(host=redis_host, port=redis_port)
        self.config.cache = CacheWrap(self.config.cache, self.redis_kwargs)

        update_status('Created', **self.redis_kwargs)
        
    def __call__(self, environ, start_response):
        """
        """
        start = time()

        if environ['PATH_INFO'] == '/status':
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return status_response(**self.redis_kwargs)

        if environ['PATH_INFO'] == '/favicon.ico':
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return ''

        try:
            update_status('Started %s' % environ['PATH_INFO'], **self.redis_kwargs)
            response = TileStache.WSGITileServer.__call__(self, environ, start_response)
    
            update_status('Finished %s in %.3f seconds' % (environ['PATH_INFO'], time() - start), **self.redis_kwargs)
            return response
        
        except Exception, e:
            update_status('Error: %s after %.3f seconds' % (str(e), time() - start), **self.redis_kwargs)
            raise
        
    def __del__(self):
        """
        """
        update_status('Destroyed', **self.redis_kwargs)

class CacheWrap:
    """ Wraps up a TileStache cache object and reports events to Redis.
    
        Implements a cache provider: http://tilestache.org/doc/#custom-caches.
    """
    def __init__(self, cache, redis_kwargs):
        self.cache = cache
        self.redis_kwargs = redis_kwargs
    
    def lock(self, layer, coord, format):
        start = time()
        update_status('Attempted cache lock', **self.redis_kwargs)

        self.cache.lock(layer, coord, format)
        update_status('Got cache lock in %.3f seconds' % (time() - start), **self.redis_kwargs)
    
    def unlock(self, layer, coord, format):
        return self.cache.unlock(layer, coord, format)
    
    def remove(self, layer, coord, format):
        return self.cache.remove(layer, coord, format)
    
    def read(self, layer, coord, format):
        return self.cache.read(layer, coord, format)
      
    def save(self, body, layer, coord, format):
        return self.cache.save(body, layer, coord, format)
