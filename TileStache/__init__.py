""" A stylish alternative for caching your map tiles.


"""

import re

from sys import stdout
from cgi import parse_qs
from StringIO import StringIO
from os.path import dirname, join as pathjoin, realpath
from urlparse import urljoin, urlparse
from urllib import urlopen

try:
    from json import load as json_load
except ImportError:
    from simplejson import load as json_load

from ModestMaps.Core import Coordinate

import Core
import Config

# regular expression for PATH_INFO
_pathinfo_pat = re.compile(r'^/?(?P<l>\w.+)/(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)\.(?P<e>\w+)$')
_preview_pat = re.compile(r'^/?(?P<l>\w.+)/preview\.html$')

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

def handlePreview(layer):
    """ Get a type string and dynamic map viewer HTML for a given layer.
    """
    return 'text/html', Core._preview(layer.name())

def parseConfigfile(configpath):
    """ Parse a configuration file and return a Configuration object.
    
        Configuration file is formatted as JSON with two sections, "cache" and "layers":
        
          {
            "cache": { ... },
            "layers": {
              "layer-1": { ... },
              "layer-2": { ... },
              ...
            }
          }
        
        The full path to the file is significant, used to
        resolve any relative paths found in the configuration.
        
        See the Caches module for more information on the "caches" section,
        and the Core and Providers modules for more information on the
        "layers" section.
    """
    config_dict = json_load(urlopen(configpath))
    
    scheme, host, path, p, q, f = urlparse(configpath)
    
    if scheme == '':
        scheme = 'file'
        path = realpath(path)
    
    dirpath = '%s://%s%s' % (scheme, host, dirname(path).rstrip('/') + '/')

    return Config.buildConfiguration(config_dict, dirpath)

def splitPathInfo(pathinfo):
    """ Converts a PATH_INFO string to layer name, coordinate, and extension parts.
        
        Example: "/layer/0/0/0.png", leading "/" optional.
    """
    if _pathinfo_pat.match(pathinfo):
        path = _pathinfo_pat.match(pathinfo)
        layer, row, column, zoom, extension = [path.group(p) for p in 'lyxze']
        coord = Coordinate(int(row), int(column), int(zoom))

    elif _preview_pat.match(pathinfo):
        path = _preview_pat.match(pathinfo)
        layer, extension = path.group('l'), 'html'
        coord = None

    else:
        raise Core.KnownUnknown('Bad path: "%s". I was expecting something more like "/example/0/0/0.png"' % pathinfo)

    return layer, coord, extension

def cgiHandler(environ, config='./tilestache.cfg', debug=False):
    """ Read environment PATH_INFO, load up configuration, talk to stdout by CGI.
    """
    if debug:
        import cgitb
        cgitb.enable()
    
    try:
        if not environ.has_key('PATH_INFO'):
            raise Core.KnownUnknown('Missing PATH_INFO in TileStache.cgiHandler().')

        config = parseConfigfile(config)
        layername, coord, extension = splitPathInfo(environ['PATH_INFO'])
        
        if layername not in config.layers:
            raise Core.KnownUnknown('"%s" is not a layer I know about. Here are some that I do know about: %s.' % (layername, ', '.join(config.layers.keys())))
        
        query = parse_qs(environ['QUERY_STRING'])
        layer = config.layers[layername]
        
        if extension == 'html' and coord is None:
            mimetype, content = handlePreview(layer)

        else:
            mimetype, content = handleRequest(layer, coord, extension)

    except Core.KnownUnknown, e:
        out = StringIO()
        
        print >> out, 'Known unknown!'
        print >> out, e
        print >> out, ''
        print >> out, '\n'.join(Core._rummy())
        
        mimetype, content = 'text/plain', out.getvalue()

    print >> stdout, 'Content-Length: %d' % len(content)
    print >> stdout, 'Content-Type: %s\n' % mimetype
    print >> stdout, content

def modpythonHandler(request):
    """ Handle a mod_python request.
    
        Example Apache configuration for TileStache:

        <Directory /home/migurski/public_html/TileStache>
            AddHandler mod_python .py
            PythonHandler TileStache::modpythonHandler
            PythonOption config /etc/tilestache.cfg
        </Directory>
        
        Configuration options, using PythonOption directive:
        - config: path to configuration file, defaults to "tilestache.cfg",
            using request.filename as the current working directory.
    """
    from mod_python import apache
    
    try:
        config = request.get_options().get('config', 'tilestache.cfg')
        config = realpath(pathjoin(dirname(request.filename), config))
        config = parseConfigfile(config)
    
        layername, coord, extension = splitPathInfo(request.path_info)
        
        if layername not in config.layers:
            raise Core.KnownUnknown('"%s" is not a layer I know about. Here are some that I do know about: %s.' % (layername, ', '.join(config.layers.keys())))
        
        query = request.args
        layer = config.layers[layername]
        
        mimetype, content = handleRequest(layer, coord, extension)

    except Core.KnownUnknown, e:
        out = StringIO()
        
        print >> out, 'Known unknown!'
        print >> out, e
        print >> out, ''
        print >> out, '\n'.join(Core._rummy())
        
        mimetype, content = 'text/plain', out.getvalue()

    request.status = apache.HTTP_OK
    request.content_type = mimetype
    request.set_content_length(len(content))
    request.send_http_header()

    request.write(content)

    return apache.OK
