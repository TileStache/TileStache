import os

import tornado.ioloop
import tornado.web

import TileStache


class TornadoRequestHandler(tornado.web.RequestHandler):
    def initialize(self, config, autoreload=False):
        self.config = config
        self.autoreload = autoreload

    def get(self, path_info):
        status_code, headers, content = TileStache.requestHandler2(
                                            self.config, path_info)

        # Get the header
        header = headers.items()[0]

        # Tornado syntax for passing headers
        self.set_header(header[0], header[1])
        self.write(content)

class TornadoTileServer(tornado.web.Application):
    def __init__(self, **kwargs):
        config = kwargs.get("config") or None
        autoreload = kwargs.get("autoreload") or None

        if type(config) in (str, unicode, dict):
            self.config_args = config

            try:
                config = TileStache.parseConfig(config)
            except:
                print "Error loading Tilestache config:"
                raise

            hargs = dict(config=config, autoreload=autoreload)
            kwargs['handlers'] = [(r"/(.*)", TornadoRequestHandler, hargs),
                                  (r'/(favicon.ico)',
                                   tornado.web.StaticFileHandler,
                                   {'path': 'www/mustaches.jpg'})]
            super(TornadoTileServer, self).__init__(**kwargs)

        else:
            assert hasattr(config, 'cache'), 'Configuration object must have a cache.'
            assert hasattr(config, 'layers'), 'Configuration object must have layers.'
            assert hasattr(config, 'dirpath'), 'Configuration object must have a dirpath.'

            self.config_args = None

