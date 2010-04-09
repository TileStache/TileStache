""" A stylish alternative for caching your tiles.


"""

import re

from os import environ
from sys import stdout
from cgi import parse_qs
from StringIO import StringIO
from os.path import dirname

try:
    from json import load as json_load
except ImportError:
    from simplejson import load as json_load

from ModestMaps.Core import Coordinate

import Config

# regular expression for PATH_INFO
_pathinfo_pat = re.compile(r'^/?(?P<l>\w.+)/(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)\.(?P<e>\w+)$')

def handleRequest(layer, coord, extension):
    """ Get a type string and tile binary for a given request layer tile.
    
        Arguments:
        - layer: instance of Core.Layer to render.
        - coord: one ModestMaps.Core.Coordinate corresponding to a single tile.
        - extension: filename extension to choose response type, e.g. "png" or "jpg".
    
        This is the main entry point, after site configuration has been loaded
        and individual tiles need to be rendered.
    """
    mimetype, format = Config.getTypeByExtension(extension)
    cache = layer.config.cache
    
    # Start by checking for a tile in the cache.
    body = cache.read(layer, coord, format)
    
    # If no tile was found, dig deeper
    if body is None:
        try:
            # this is the coordinate that actually gets locked.
            lockCoord = layer.metatile.firstCoord(coord)
            
            # We may need to write a new tile, so acquire a lock.
            cache.lock(layer, lockCoord, format)
            
            # There's a chance that some other process has
            # written the tile while the lock was being acquired.
            body = cache.read(layer, coord, format)
    
            # If no one else wrote the tile, do it here.
            if body is None:
                buff = StringIO()
                tile = layer.render(coord, format)
                tile.save(buff, format)
                body = buff.getvalue()
                
                cache.save(body, layer, coord, format)

        finally:
            # Always clean up a lock when it's no longer being used.
            cache.unlock(layer, lockCoord, format)

    return mimetype, body

def parseConfigfile(configpath):
    """ Parse a configuration file and return a Configuration object.
    
        Configuration file is formatted as JSON, and has two sections:
        
          {
            "cache": { ... },
            "layers": {
              "layer-1": { ... },
              "layer-2": { ... },
              ...
            }
          }
        
        The full filesystem path to the file is significant, used
        to resolve any relative paths found in the configuration.
        
        See the Caches module for more information on the "caches" section,
        and the Core and Providers modules for more information on the
        "layers" section.
    """
    config_dict = json_load(open(configpath, 'r'))
    dirpath = dirname(configpath)

    return Config.buildConfiguration(config_dict, dirpath)

def _splitPathInfo(pathinfo):
    """ Converts a PATH_INFO string to layer name, coordinate, and extension parts.
        
        Example: "/layer/0/0/0.png", leading "/" optional.
    """
    path = _pathinfo_pat.match(pathinfo)
    layer, row, column, zoom, extension = [path.group(p) for p in 'lyxze']
    coord = Coordinate(int(row), int(column), int(zoom))

    return layer, coord, extension

def cgiHandler(debug=False):
    """ Load up configuration and talk to stdout by CGI.
    """
    if debug:
        import cgitb
        cgitb.enable()
    
    config = parseConfigfile('tilestache.cfg')
    layername, coord, extension = _splitPathInfo(environ['PATH_INFO'])
    
    query = parse_qs(environ['QUERY_STRING'])
    layer = config.layers[layername]
    
    mimetype, content = handleRequest(layer, coord, extension)
    
    print >> stdout, 'Content-Length: %d' % len(content)
    print >> stdout, 'Content-Type: %s\n' % mimetype
    print >> stdout, content
