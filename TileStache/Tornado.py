import os

import tornado.ioloop
import tornado.web

import TileStache


class TornadoRequestHandler(tornado.web.RequestHandler):
    """ Create a Tornado HTTP get and post handler.

        This class is documented as part of Tornado public RequestHandler API:
            http://www.tornadoweb.org/en/stable/guide/structure.html
    """
    def initialize(self, config=None, autoreload=False):
        self.config = config
        self.autoreload = autoreload

        try:
                self.tsconfig = TileStache.parseConfig(self.config)
        except:
            print "Error loading Tilestache config:"
            raise

    def get(self, *args, **kwargs):
        if self.autoreload: # re-parse the config file on every request
            try:
                self.tsconfig = parseConfig(self.config)
            except Exception, e:
                raise Core.KnownUnknown("Error loading Tilestache configuration:\n%s" % str(e))

        status_code, headers, content = TileStache.requestHandler2(
                                            self.tsconfig, args[0])

        # Get the header
        header = headers.items()[0]

        # Tornado syntax for passing headers
        self.set_header(header[0], header[1])
        self.write(content)


class TornadoTileApplication(tornado.web.Application):
    """ Create a Tornado application that can handle HTTP requests.

        This class is documented as part of TileStache's public API:
            http://tilestache.org/doc/#wsgi

        The Tornado application is an instance of this class. Example:

            app = TornadoTileApplication(config='/path/to/tilestache.cfg')
            app.listen(8080)
            tornado.ioloop.IOLoop.current().start()
    """
    def __init__(self, **kwargs):
        config = kwargs.get("config") or None
        autoreload = kwargs.get("autoreload") or None

        if type(config) in (str, unicode, dict):
            hargs = dict(config=config, autoreload=autoreload)
            kwargs['handlers'] = [(r"/(.*)", TornadoRequestHandler, hargs),
                                  (r'/(favicon.ico)',
                                   tornado.web.StaticFileHandler,
                                   {'path': 'www/mustaches.jpg'})]
            super(TornadoTileApplication, self).__init__(**kwargs)

        else:
            assert hasattr(config, 'cache'), 'Configuration object must have a cache.'
            assert hasattr(config, 'layers'), 'Configuration object must have layers.'
            assert hasattr(config, 'dirpath'), 'Configuration object must have a dirpath.'
