""" AreaServer supplies a tiny image server for use with TileStache providers
    that implement renderArea() (http://tilestache.org/doc/#custom-providers).
    The built-in Mapnik provider (http://tilestache.org/doc/#mapnik-provider)
    is one example.

    There are no tiles here, just a quick & dirty way of getting variously-sized
    images out of a codebase that's ordinarily oriented toward tile generation.

    Example usage, with gunicorn (http://gunicorn.org):

      gunicorn --bind localhost:8888 "TileStache.Goodies.AreaServer:WSGIServer('tilestache.cfg')"

    AreaServer URLs are compatible with the built-in URL Template provider
    (http://tilestache.org/doc/#url-template-provider) and implement a generic
    kind of WMS (http://en.wikipedia.org/wiki/Web_Map_Service).

    All six URL parameters shown in this example are required; any other
    URL parameter is ignored:

      http://localhost:8888/layer-name?width=600&height=600&xmin=-100&ymin=-100&xmax=100&ymax=100
"""

from datetime import timedelta
from datetime import datetime
from io import BytesIO

from TileStache.py3_compat import parse_qsl

from TileStache import WSGITileServer
from TileStache.Core import KnownUnknown

class WSGIServer (WSGITileServer):
    """ WSGI Application that can handle WMS-style requests for static images.

        Inherits the constructor from TileStache WSGI, which just loads
        a TileStache configuration file into self.config.

        WSGITileServer autoreload argument is ignored, though. For now.
    """
    def __call__(self, environ, start_response):
        """ Handle a request, using PATH_INFO and QUERY_STRING from environ.

            There are six required query string parameters: width, height,
            xmin, ymin, xmax and ymax. Layer name must be supplied in PATH_INFO.
        """
        try:
            for var in 'QUERY_STRING PATH_INFO'.split():
                if var not in environ:
                    raise KnownUnknown('Missing "%s" environment variable' % var)

            query = dict(parse_qsl(environ['QUERY_STRING']))

            for param in 'width height xmin ymin xmax ymax'.split():
                if param not in query:
                    raise KnownUnknown('Missing "%s" parameter' % param)

            layer = environ['PATH_INFO'].strip('/')
            layer = self.config.layers[layer]
            provider = layer.provider

            if not hasattr(provider, 'renderArea'):
                raise KnownUnknown('Layer "%s" provider %s has no renderArea() method' % (layer.name(), provider.__class__))

            width, height = [int(query[p]) for p in 'width height'.split()]
            xmin, ymin, xmax, ymax = [float(query[p]) for p in 'xmin ymin xmax ymax'.split()]

            #
            # Don't supply srs or zoom parameters, which may cause problems for
            # some providers. TODO: add optional support for these two parameters.
            #

            output = BytesIO()
            image = provider.renderArea(width, height, None, xmin, ymin, xmax, ymax, None)
            image.save(output, format='PNG')

            headers = [('Content-Type', 'image/png')]

            if layer.allowed_origin:
                headers.append(('Access-Control-Allow-Origin', layer.allowed_origin))

            if layer.max_cache_age is not None:
                expires = datetime.utcnow() + timedelta(seconds=layer.max_cache_age)
                headers.append(('Expires', expires.strftime('%a %d %b %Y %H:%M:%S GMT')))
                headers.append(('Cache-Control', 'public, max-age=%d' % layer.max_cache_age))

            start_response('200 OK', headers)
            return output.getvalue()

        except KnownUnknown, e:
            start_response('400 Bad Request', [('Content-Type', 'text/plain')])
            return str(e)
