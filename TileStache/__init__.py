""" A stylish alternative for caching your map tiles.

TileStache is a Python-based server application that can serve up map tiles
based on rendered geographic data. You might be familiar with TileCache
(http://tilecache.org), the venerable open source WMS server from MetaCarta.
TileStache is similar, but we hope simpler and better-suited to the needs of
designers and cartographers.

Documentation available at http://tilestache.org/doc/
"""
from __future__ import print_function
import os.path

__version__ = open(os.path.join(os.path.dirname(__file__), 'VERSION')).read().strip()

import re

from sys import stdout
from io import StringIO
from os.path import dirname, join as pathjoin, realpath
from datetime import datetime, timedelta

from .py3_compat import urljoin, urlparse, urlopen, parse_qs, httplib, is_string_type, reduce

from wsgiref.headers import Headers
from os import getcwd
from time import time

import logging

try:
    from json import load as json_load
    from json import loads as json_loads
except ImportError:
    from simplejson import load as json_load
    from simplejson import loads as json_loads

from ModestMaps.Core import Coordinate

# dictionary of configuration objects for requestLayer().
_previous_configs = {}

from . import Core
from . import Config

# regular expression for PATH_INFO
_pathinfo_pat = re.compile(r'^/?(?P<l>\w.+)/(?P<z>\d+)/(?P<x>-?\d+)/(?P<y>-?\d+)\.(?P<e>\w+)$')
_preview_pat = re.compile(r'^/?(?P<l>\w.+)/(preview\.html)?$')

def getTile(layer, coord, extension, ignore_cached=False):
    ''' Get a type string and tile binary for a given request layer tile.

        This function is documented as part of TileStache's public API:
            http://tilestache.org/doc/#tilestache-gettile

        Arguments:
        - layer: instance of Core.Layer to render.
        - coord: one ModestMaps.Core.Coordinate corresponding to a single tile.
        - extension: filename extension to choose response type, e.g. "png" or "jpg".
        - ignore_cached: always re-render the tile, whether it's in the cache or not.

        This is the main entry point, after site configuration has been loaded
        and individual tiles need to be rendered.
    '''
    status_code, headers, body = layer.getTileResponse(coord, extension, ignore_cached)
    mime = headers.get('Content-Type')

    return mime, body

def getPreview(layer):
    """ Get a type string and dynamic map viewer HTML for a given layer.
    """
    return 200, Headers([('Content-Type', 'text/html')]), Core._preview(layer)


def parseConfig(configHandle):
    """ Parse a configuration file and return a Configuration object.

        Configuration could be a Python dictionary or a file formatted as JSON. In both cases
        it needs to be formatted with two sections, "cache" and "layers":

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
    if isinstance(configHandle, dict):
        config_dict = configHandle
        dirpath = '.'
    else:
        scheme, host, path, p, q, f = urlparse(configHandle)

        if scheme == '':
            scheme = 'file'
            path = realpath(path)

        if scheme == 'file':
            with open(path) as file:
                config_dict = json_load(file)
        else:
            config_dict = json_load(urlopen(configHandle))

        dirpath = '%s://%s%s' % (scheme, host, dirname(path).rstrip('/') + '/')

    return Config.buildConfiguration(config_dict, dirpath)

parseConfigfile = parseConfig  # Deprecated function


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
        raise Core.KnownUnknown('Bad path: "{}". I was expecting something more like "/example/0/0/0.png"'.format(pathinfo))

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
    if is_string_type(config):
        #
        # Should be a path to a configuration file we can load;
        # build a tuple key into previously-seen config objects.
        #
        key = hasattr(config, '__hash__') and (config, getcwd())

        if key in _previous_configs:
            config = _previous_configs[key]

        else:
            config = parseConfig(config)

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
        raise Core.KnownUnknown('"{}" is not a layer I know about. Here are some that I do know about: {}.'.format(layername, ', '.join(sorted(config.layers.keys()))))

    return config.layers[layername]

def requestHandler(config_hint, path_info, query_string=None):
    """ Generate a mime-type and response body for a given request.

        This function is documented as part of TileStache's public API:
            http://tilestache.org/doc/#tilestache-requesthandler

        TODO: replace this with requestHandler2() in TileStache 2.0.0.

        Calls requestHandler2().
    """
    status_code, headers, content = requestHandler2(config_hint, path_info, query_string)
    mimetype = headers.get('Content-Type')

    return mimetype, content

def requestHandler2(config_hint, path_info, query_string=None, script_name=''):
    """ Generate a set of headers and response body for a given request.

        TODO: Replace requestHandler() with this function in TileStache 2.0.0.

        Requires a configuration and PATH_INFO (e.g. "/example/0/0/0.png").

        Config_hint parameter can be a path string for a JSON configuration file
        or a configuration object with 'cache', 'layers', and 'dirpath' properties.

        Query string is optional, currently used for JSON callbacks.

        Calls Layer.getTileResponse() to render actual tiles, and getPreview() to render preview.html.
    """
    headers = Headers([])

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
            mimetype, content = getattr(layer.config, 'index', ('text/plain', 'TileStache says hello.'))
            return 200, Headers([('Content-Type', mimetype)]), content

        coord, extension = splitPathInfo(path_info)[1:]

        if extension == 'html' and coord is None:
            status_code, headers, content = getPreview(layer)

        elif extension.lower() in layer.redirects:
            other_extension = layer.redirects[extension.lower()]

            redirect_uri = script_name
            redirect_uri += mergePathInfo(layer.name(), coord, other_extension)

            if query_string:
                redirect_uri += '?' + query_string

            headers['Location'] = redirect_uri
            headers['Content-Type'] = 'text/plain'

            return 302, headers, 'You are being redirected to %s\n' % redirect_uri

        else:
            status_code, headers, content = layer.getTileResponse(coord, extension)

        if layer.allowed_origin:
            headers.setdefault('Access-Control-Allow-Origin', layer.allowed_origin)

        if callback and 'json' in headers['Content-Type']:
            headers['Content-Type'] = 'application/javascript; charset=utf-8'
            content = '%s(%s)' % (callback, content)

        if layer.max_cache_age is not None:
            expires = datetime.utcnow() + timedelta(seconds=layer.max_cache_age)
            headers.setdefault('Expires', expires.strftime('%a, %d %b %Y %H:%M:%S GMT'))
            headers.setdefault('Cache-Control', 'public, max-age=%d' % layer.max_cache_age)

    except Core.KnownUnknown as e:
        out = StringIO()

        print('Known unknown!', file=out)
        print(e, file=out)
        print('', file=out)
        print('\n'.join(Core._rummy()), file=out)

        headers['Content-Type'] = 'text/plain'
        status_code, content = 500, out.getvalue().encode('ascii')

    return status_code, headers, content

def cgiHandler(environ, config='./tilestache.cfg', debug=False):
    """ Read environment PATH_INFO, load up configuration, talk to stdout by CGI.

        This function is documented as part of TileStache's public API:
            http://tilestache.org/doc/#cgi

        Calls requestHandler().

        Config parameter can be a file path string for a JSON configuration file
        or a configuration object with 'cache', 'layers', and 'dirpath' properties.
    """
    if debug:
        import cgitb
        cgitb.enable()

    path_info = environ.get('PATH_INFO', None)
    query_string = environ.get('QUERY_STRING', None)
    script_name = environ.get('SCRIPT_NAME', None)

    status_code, headers, content = requestHandler2(config, path_info, query_string, script_name)

    headers.setdefault('Content-Length', str(len(content)))

    # output the status code as a header
    stdout.write('Status: %d\n' % status_code)

    # output gathered headers
    for k, v in headers.items():
        stdout.write('%s: %s\n' % (k, v))

    stdout.write('\n')
    stdout.write(content)

class WSGITileServer:
    """ Create a WSGI application that can handle requests from any server that talks WSGI.

        This class is documented as part of TileStache's public API:
            http://tilestache.org/doc/#wsgi

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

        if is_string_type(config):
            self.autoreload = autoreload
            self.config_path = config

            try:
                self.config = parseConfig(config)
            except:
                print("Error loading Tilestache config:")
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
                self.config = parseConfig(self.config_path)
            except Exception as e:
                raise Core.KnownUnknown("Error loading Tilestache config file:\n%s" % str(e))

        try:
            layer, coord, ext = splitPathInfo(environ['PATH_INFO'])
        except Core.KnownUnknown as e:
            return self._response(start_response, 400, str(e))

        #
        # WSGI behavior is different from CGI behavior, because we may not want
        # to return a chatty rummy for likely-deployed WSGI vs. testing CGI.
        #
        if layer and layer not in self.config.layers:
            return self._response(start_response, 404)

        path_info = environ.get('PATH_INFO', None)
        query_string = environ.get('QUERY_STRING', None)
        script_name = environ.get('SCRIPT_NAME', None)

        status_code, headers, content = requestHandler2(self.config, path_info, query_string, script_name)

        return self._response(start_response, status_code, bytes(content), headers)

    def _response(self, start_response, code, content='', headers=None):
        """
        """
        headers = headers or Headers([])

        if content:
            headers.setdefault('Content-Length', str(len(content)))

        start_response('%d %s' % (code, httplib.responses[code]), headers.items())
        return [content]

def modpythonHandler(request):
    """ Handle a mod_python request.

        TODO: Upgrade to new requestHandler() so this can return non-200 HTTP.

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
