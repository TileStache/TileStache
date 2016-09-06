#!/usr/bin/env python
"""server.py will serve your cache.

This script is intended to be run directly from the command line from its current location.

It is intended for direct use only during development or for debugging TileStache.

For the proper way to configure TileStach for serving tiles see the docs at:

http://tilestache.org/doc/#serving-tiles

To use this built-in server, install werkzeug and then run tilestache-server.py:

    server.py

By default the script serves tiles on http://127.0.0.1:8080/.

You can then open your browser and view a url like:

    http://localhost:8080/geotiff/0/0/0.png

Check server.py --help to change these defaults.
"""

import json


if __name__ == '__main__':
    from datetime import datetime
    from optparse import OptionParser, OptionValueError
    import os, sys

    parser = OptionParser()

    config = {
        "cache": {
            "name": "Test",
            "path": "/tmp/stache",
            "umask": "0000"
        },
        "layers": {
            "geotiff": {
                "provider": {"name": "mapnik", "mapfile": "mapnik.xml"},
                "projection": "spherical mercator"
            }
        }
    }

    parser.add_option("-c", "--config", dest="file", default="tilestache.cfg",
        help="the path to the tilestache config")
    parser.add_option("-i", "--ip", dest="ip", default="127.0.0.1",
        help="the IP address to listen on")
    parser.add_option("-p", "--port", dest="port", type="int", default=8080,
        help="the port number to listen on")
    parser.add_option('--include-path', dest='include',
        help="Add the following colon-separated list of paths to Python's include path (aka sys.path)")
    (options, args) = parser.parse_args()

    if options.include:
        for p in options.include.split(':'):
            sys.path.insert(0, p)

    from werkzeug.serving import run_simple
    import TileStache

    app = TileStache.WSGITileServer(config=config, autoreload=True)
    run_simple(options.ip, options.port, app)
