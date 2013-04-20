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

def getPreview(layer):
    """ Get a type string and dynamic map viewer HTML for a given layer.
    """
    return 200, makeHeaders('text/html'), Core._preview(layer)

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

def makeHeaders(mimetype):
    """ Create a headers dict (containing only a content-type for now).
    """
    headers = dict()

    headers['Content-Type'] = mimetype

    return headers

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
    """ Generate a set of headers and response body for a given request.
    
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
        
        if extension == 'html' and coord is None:
            status_code, headers, content = getPreview(layer)

        elif extension.lower() in layer.redirects:
            other_extension = layer.redirects[extension.lower()]
            other_path_info = mergePathInfo(layer.name(), coord, other_extension)
            raise Core.TheTileIsInAnotherCastle(other_path_info)
        
        else:
            status_code, headers, content = layer.getTile(coord, extension)
    
        if callback and 'json' in headers['Content-Type']:
            headers, content = makeHeaders('application/javascript; charset=utf-8'), '%s(%s)' % (callback, content)

    except Core.KnownUnknown, e:
        out = StringIO()
        
        print >> out, 'Known unknown!'
        print >> out, e
        print >> out, ''
        print >> out, '\n'.join(Core._rummy())
        
        status_code, headers, content = 500, makeHeaders('text/plain'), out.getvalue()

    return status_code, headers, content

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
        status_code, headers, content = requestHandler(config, path_info, query_string)
    
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
        headers['Access-Control-Allow-Origin'] = layer.allowed_origin
    
    if layer.max_cache_age is not None:
        expires = datetime.utcnow() + timedelta(seconds=layer.max_cache_age)
        headers['Expires'] = expires.strftime('%a %d %b %Y %H:%M:%S GMT')
        headers['Cache-Control'] = 'public, max-age=%d' % layer.max_cache_age
    
    headers['Content-Length'] = len(content)

    # output the status code as a header
    print >> stdout, 'Status: %s', status_code

    # output gathered headers
    for k, v in headers:
        print >> stdout, '%s: %s\n' % (k, v)

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
            except:
                print "Error loading Tilestache config:"
                raise

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
            status_code, headers, content = requestHandler(self.config, environ['PATH_INFO'], environ['QUERY_STRING'])
        
        except Core.TheTileIsInAnotherCastle, e:
            other_uri = environ['SCRIPT_NAME'] + e.path_info
            
            if environ['QUERY_STRING']:
                other_uri += '?' + environ['QUERY_STRING']
    
            start_response('302 Found', [('Location', other_uri), ('Content-Type', 'text/plain')])
            return ['You are being redirected to %s\n' % other_uri]
        
        request_layer = requestLayer(self.config, environ['PATH_INFO'])
        allowed_origin = request_layer.allowed_origin
        max_cache_age = request_layer.max_cache_age
        
        if request_layer.allowed_origin:
            headers.append(('Access-Control-Allow-Origin', allowed_origin))
        
        if request_layer.max_cache_age is not None:
            expires = datetime.utcnow() + timedelta(seconds=max_cache_age)
            headers.append(('Expires', expires.strftime('%a %d %b %Y %H:%M:%S GMT')))
            headers.append(('Cache-Control', 'public, max-age=%d' % max_cache_age))

        return self._response(start_response, status_code, str(content), headers)

    def _response(self, start_response, code, content='', headers=dict()):
        """
        """
        # TODO headers should be internally represented as a list of tuples
        # rather than a dict, otherwise multiple values for the same header
        # won't work properly
        if not headers.has_key('Content-Type'):
            headers['Content-Type'] = 'text/plain'

        if not headers.has_key('Content-Length'):
            headers['Content-Length'] = str(len(content))
        
        # TODO this needs a lookup for the string part of the response
        start_response(str(code) + " blarg", headers.items())
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
    
    status_code, headers, content = requestHandler(config_path, path_info, query_string)

    request.status = status_code

    for k, v in headers:
        request.headers_out.add(k, v)

    request.set_content_length(len(content))
    request.send_http_header()

    request.write(content)

    return status_code
