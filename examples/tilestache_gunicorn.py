"""
Usage: gunicorn --options tilestache_gunicorn:app

tilestache_gunicorn is a wsgi wrapper, using gunicorn, for TileStache that proxies
and caches tile from OpenStreetMaps. For example:

	http://localhost:8000/osm/14/2620/6333.png

For a complete list of options, please consult: gunicorn --help

See also: http://github.com/benoitc/gunicorn
"""

import TileStache

config = {
    "cache": {"name": "Disk", "path" : "/tmp/tilestache"},
    "layers": {
        "osm": {
            "provider": {"name": "proxy", "provider": "OPENSTREETMAP"},
            "projection": "spherical mercator"
            }
        }
    }

config = TileStache.Config.buildConfiguration(config)

def app(environ, start_response):

    layer, coord, ext = TileStache._splitPathInfo(environ['PATH_INFO'])

    if not config.layers.get(layer, False):
        status = '404 NOT FOUND'
        data = ''

    else:

        try:
            content_type, data = TileStache.handleRequest(config.layers[layer], coord, ext)
            status = '200 OK'

        except Exception, e:
            status = '500 SERVER ERROR'
            data = str(e)

    response_headers = [
        ('Content-type', type),
        ('Content-Length', str(len(data)))
    ]

    start_response(status, response_headers)
    return iter([data])
