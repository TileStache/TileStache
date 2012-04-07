""" A stylish alternative for caching your map tiles.

TileStache is a Python-based server application that can serve up map tiles
based on rendered geographic data. You might be familiar with TileCache
(http://tilecache.org), the venerable open source WMS server from MetaCarta.
TileStache is similar, but we hope simpler and better-suited to the needs of
designers and cartographers.

Documentation available at http://tilestache.org/doc/
"""
__version__ = 'N.N.N'

import re

from sys import stdout
try:
    from urlparse import parse_qs
except ImportError:
    from cgi import parse_qs
from StringIO import StringIO
from os.path import dirname, join as pathjoin, realpath
from datetime import datetime, timedelta
from urlparse import urljoin, urlparse
from urllib import urlopen
from os import getcwd
from time import time
import logging

try:
    from json import load as json_load
except ImportError:
    from simplejson import load as json_load

from ModestMaps.Core import Coordinate

# dictionary of configuration objects for requestLayer().
_previous_configs = {}

import Core
import Config

# regular expression for PATH_INFO
_pathinfo_pat = re.compile(r'^/?(?P<l>\w.+)/(?P<z>\d+)/(?P<x>-?\d+)/(?P<y>-?\d+)\.(?P<e>\w+)$')
_preview_pat = re.compile(r'^/?(?P<l>\w.+)/(preview\.html)?$')

def getTile(layer, coord, extension, ignore_cached=False):
    """ Get a type string and tile binary for a given request layer tile.
    
        Arguments:
        - layer: instance of Core.Layer to render.
        - coord: one ModestMaps.Core.Coordinate corresponding to a single tile.
        - extension: filename extension to choose response type, e.g. "png" or "jpg".
        - ignore_cached: always re-render the tile, whether it's in the cache or not.
    
        This is the main entry point, after site configuration has been loaded
        and individual tiles need to be rendered.
    """
    start_time = time()
    
    mimetype, format = layer.getTypeByExtension(extension)
    cache = layer.config.cache

    if not ignore_cached:
        # Start by checking for a tile in the cache.
        body = cache.read(layer, coord, format)
        tile_from = 'cache'

    else:
        # Then look in the bag of recent tiles.
        body = Core._getRecentTile(layer, coord, format)
        tile_from = 'recent tiles'
    
    # If no tile was found, dig deeper
    if body is None:
        try:
            lockCoord = None

            if layer.write_cache:
                # this is the coordinate that actually gets locked.
                lockCoord = layer.metatile.firstCoord(coord)
                
                # We may need to write a new tile, so acquire a lock.
                cache.lock(layer, lockCoord, format)
            
            if not ignore_cached:
                # There's a chance that some other process has
                # written the tile while the lock was being acquired.
                body = cache.read(layer, coord, format)
                tile_from = 'cache after all'
    
            if body is None:
                # No one else wrote the tile, do it here.
                buff = StringIO()

                try:
                    tile = layer.render(coord, format)
                    save = True
                except Core.NoTileLeftBehind, e:
                    tile = e.tile
                    save = False

                if not layer.write_cache:
                    save = False
                
                if format.lower() == 'jpeg':
                    save_kwargs = layer.jpeg_options
                elif format.lower() == 'png':
                    save_kwargs = layer.png_options
                else:
                    save_kwargs = {}
                
                tile.save(buff, format, **save_kwargs)
                body = buff.getvalue()
                
                if save:
                    cache.save(body, layer, coord, format)

                tile_from = 'layer.render()'

        finally:
            if lockCoord:
                # Always clean up a lock when it's no longer being used.
                cache.unlock(layer, lockCoord, format)
    
    Core._addRecentTile(layer, coord, format, body)
    logging.info('TileStache.getTile() %s/%d/%d/%d.%s via %s in %.3f', layer.name(), coord.zoom, coord.column, coord.row, extension, tile_from, time() - start_time)
    
    return mimetype, body

def getPreview(layer):
    """ Get a type string and dynamic map viewer HTML for a given layer.
    """
    return 'text/html', Core._preview(layer)

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
    if pathinfo == '/':
        return None, None, None
    
    if _pathinfo_pat.match(pathinfo or ''):
        path = _pathinfo_pat.match(pathinfo)
        layer, row, column, zoom, extension = [path.group(p) for p in 'lyxze']
        coord = Coordinate(int(row), int(column), int(zoom))

    elif _preview_pat.match(pathinfo or ''):
        path = _preview_pat.match(pathinfo)
        layer, extension = path.group('l'), 'html'
        coord = None

    else:
        raise Core.KnownUnknown('Bad path: "%s". I was expecting something more like "/example/0/0/0.png"' % pathinfo)

    return layer, coord, extension

def mergePathInfo(layer, coord, extension):
    """ Converts layer name, coordinate and extension back to a PATH_INFO string.
    
        See also splitPathInfo().
    """
    z = coord.zoom
    x = coord.column
    y = coord.row
    
    return '/%(layer)s/%(z)d/%(x)d/%(y)d.%(extension)s' % locals()

def requestLayer(config, path_info):
    """ Return a Layer.
    
        Requires a configuration and PATH_INFO (e.g. "/example/0/0/0.png").
        
        Config parameter can be a file path string for a JSON configuration file
        or a configuration object with 'cache', 'layers', and 'dirpath' properties.
    """
    if type(config) in (str, unicode):
        #
        # Should be a path to a configuration file we can load;
        # build a tuple key into previously-seen config objects.
        #
        key = hasattr(config, '__hash__') and (config, getcwd())
        
        if key in _previous_configs:
            config = _previous_configs[key]
        
        else:
            config = parseConfigfile(config)
            
            if key:
                _previous_configs[key] = config
    
    else:
        assert hasattr(config, 'cache'), 'Configuration object must have a cache.'
        assert hasattr(config, 'layers'), 'Configuration object must have layers.'
        assert hasattr(config, 'dirpath'), 'Configuration object must have a dirpath.'
    
    # ensure that path_info is at least a single "/"
    path_info = '/' + (path_info or '').lstrip('/')
    
    if path_info == '/':
        return Core.Layer(config, None, None)

    layername = splitPathInfo(path_info)[0]
    
    if layername not in config.layers:
        raise Core.KnownUnknown('"%s" is not a layer I know about. Here are some that I do know about: %s.' % (layername, ', '.join(sorted(config.layers.keys()))))
    
    return config.layers[layername]

def requestHandler(config_hint, path_info, query_string):
    """ Generate a mime-type and response body for a given request.
    
        Requires a configuration and PATH_INFO (e.g. "/example/0/0/0.png").
        
        Config_hint parameter can be a path string for a JSON configuration file
        or a configuration object with 'cache', 'layers', and 'dirpath' properties.
        
        Query string is optional, currently used for JSON callbacks.
        
        Calls getTile() to render actual tiles, and getPreview() to render preview.html.
    """
    try:
        # ensure that path_info is at least a single "/"
        path_info = '/' + (path_info or '').lstrip('/')
        
        layer = requestLayer(config_hint, path_info)
        query = parse_qs(query_string or '')
        try:
            callback = query['callback'][0]
        except KeyError:
            callback = None
        
        #
        # Special case for index page.
        #
        if path_info == '/':
            return getattr(layer.config, 'index', ('text/plain', 'TileStache says hello.'))

        coord, extension = splitPathInfo(path_info)[1:]
        
        if path_info == '/':
            raise Exception(path_info)
        
        elif extension == 'html' and coord is None:
            mimetype, content = getPreview(layer)

        elif extension.lower() in layer.redirects:
            other_extension = layer.redirects[extension.lower()]
            other_path_info = mergePathInfo(layer.name(), coord, other_extension)
            raise Core.TheTileIsInAnotherCastle(other_path_info)
        
        else:
            mimetype, content = getTile(layer, coord, extension)
    
        if callback and 'json' in mimetype:
            mimetype, content = 'application/javascript', '%s(%s)' % (callback, content)

    except Core.KnownUnknown, e:
        out = StringIO()
        
        print >> out, 'Known unknown!'
        print >> out, e
        print >> out, ''
        print >> out, '\n'.join(Core._rummy())
        
        mimetype, content = 'text/plain', out.getvalue()

    return mimetype, content

def cgiHandler(environ, config='./tilestache.cfg', debug=False):
    """ Read environment PATH_INFO, load up configuration, talk to stdout by CGI.
    
        Calls requestHandler().
        
        Config parameter can be a file path string for a JSON configuration file
        or a configuration object with 'cache', 'layers', and 'dirpath' properties.
    """
    if debug:
        import cgitb
        cgitb.enable()
    
    path_info = environ.get('PATH_INFO', None)
    query_string = environ.get('QUERY_STRING', None)
    
    try:
        mimetype, content = requestHandler(config, path_info, query_string)
    
    except Core.TheTileIsInAnotherCastle, e:
        other_uri = environ['SCRIPT_NAME'] + e.path_info
        
        if query_string:
            other_uri += '?' + query_string

        print >> stdout, 'Status: 302 Found'
        print >> stdout, 'Location:', other_uri
        print >> stdout, 'Content-Type: text/plain\n'
        print >> stdout, 'You are being redirected to', other_uri
        return
    
    layer = requestLayer(config, path_info)
    
    if layer.allowed_origin:
        print >> stdout, 'Access-Control-Allow-Origin:', layer.allowed_origin
    
    if layer.max_cache_age is not None:
        expires = datetime.utcnow() + timedelta(seconds=layer.max_cache_age)
        print >> stdout, 'Expires:', expires.strftime('%a %d %b %Y %H:%M:%S GMT')
        print >> stdout, 'Cache-Control: public, max-age=%d' % layer.max_cache_age
    
    print >> stdout, 'Content-Length: %d' % len(content)
    print >> stdout, 'Content-Type: %s\n' % mimetype
    print >> stdout, content

class WSGITileServer:
    """ Create a WSGI application that can handle requests from any server that talks WSGI.

        The WSGI application is an instance of this class. Example:

          app = WSGITileServer('/path/to/tilestache.cfg')
          werkzeug.serving.run_simple('localhost', 8080, app)
    """

    def __init__(self, config, autoreload=False):
        """ Initialize a callable WSGI instance.

            Config parameter can be a file path string for a JSON configuration
            file or a configuration object with 'cache', 'layers', and
            'dirpath' properties.
            
            Optional autoreload boolean parameter causes config to be re-read
            on each request, applicable only when config is a JSON file.
        """

        if type(config) in (str, unicode):
            self.autoreload = autoreload
            self.config_path = config
    
            try:
                self.config = parseConfigfile(config)
            except Exception, e:
                raise Core.KnownUnknown("Error loading Tilestache config file:\n%s" % str(e))

        else:
            assert hasattr(config, 'cache'), 'Configuration object must have a cache.'
            assert hasattr(config, 'layers'), 'Configuration object must have layers.'
            assert hasattr(config, 'dirpath'), 'Configuration object must have a dirpath.'
            
            self.autoreload = False
            self.config_path = None
            self.config = config

    def __call__(self, environ, start_response):
        """
        """
        if self.autoreload: # re-parse the config file on every request
            try:
                self.config = parseConfigfile(self.config_path)
            except Exception, e:
                raise Core.KnownUnknown("Error loading Tilestache config file:\n%s" % str(e))

        try:
            layer, coord, ext = splitPathInfo(environ['PATH_INFO'])
        except Core.KnownUnknown, e:
            return self._response(start_response, '400 Bad Request', str(e))

        if layer and layer not in self.config.layers:
            return self._response(start_response, '404 Not Found')

        try:
            mimetype, content = requestHandler(self.config, environ['PATH_INFO'], environ['QUERY_STRING'])
        
        except Core.TheTileIsInAnotherCastle, e:
            other_uri = environ['SCRIPT_NAME'] + e.path_info
            
            if environ['QUERY_STRING']:
                other_uri += '?' + environ['QUERY_STRING']
    
            start_response('302 Found', [('Location', other_uri), ('Content-Type', 'text/plain')])
            return ['You are being redirected to %s\n' % other_uri]
        
        request_layer = requestLayer(self.config, environ['PATH_INFO'])
        allowed_origin = request_layer.allowed_origin
        max_cache_age = request_layer.max_cache_age
        return self._response(start_response, '200 OK', str(content), mimetype, allowed_origin, max_cache_age)

    def _response(self, start_response, code, content='', mimetype='text/plain', allowed_origin='', max_cache_age=None):
        """
        """
        headers = [('Content-Type', mimetype), ('Content-Length', str(len(content)))]
        
        if allowed_origin:
            headers.append(('Access-Control-Allow-Origin', allowed_origin))
        
        if max_cache_age is not None:
            expires = datetime.utcnow() + timedelta(seconds=max_cache_age)
            headers.append(('Expires', expires.strftime('%a %d %b %Y %H:%M:%S GMT')))
            headers.append(('Cache-Control', 'public, max-age=%d' % max_cache_age))
        
        start_response(code, headers)
        return [content]

def modpythonHandler(request):
    """ Handle a mod_python request.
    
        Calls requestHandler().
    
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
    
    config_path = request.get_options().get('config', 'tilestache.cfg')
    config_path = realpath(pathjoin(dirname(request.filename), config_path))
    
    path_info = request.path_info
    query_string = request.args
    
    mimetype, content = requestHandler(config_path, path_info, query_string)

    request.status = apache.HTTP_OK
    request.content_type = mimetype
    request.set_content_length(len(content))
    request.send_http_header()

    request.write(content)

    return apache.OK
