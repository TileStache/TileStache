#!/usr/bin/env python
"""tilestache-server.py will serve your cache.

This script is intended to be run directly from the command line.

It is intended for direct use only during development or for debugging TileStache.

For the proper way to configure TileStach for serving tiles see the docs at:

http://tilestache.org/doc/#serving-tiles

To use this built-in server, install werkzeug and then run tilestache-server.py:

    tilestache-server.py

By default the script looks for a config file named tilestache.cfg in the current directory and then serves tiles on http://127.0.0.1:8080/. 

You can then open your browser and view a url like:

    http://localhost:8080/osm/0/0/0.png

The above layer of 'osm' (defined in the tilestache.cfg) will display an OpenStreetMap
tile proxied from http://tile.osm.org/0/0/0.png
   
Check tilestache-server.py --help to change these defaults.
"""
from __future__ import print_function

if __name__ == '__main__':
    from datetime import datetime
    from optparse import OptionParser, OptionValueError
    import os, sys

    parser = OptionParser()
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

    if not os.path.exists(options.file):
        print("Config file not found. Use -c to pick a tilestache config file.", file=sys.stderr)
        sys.exit(1)

    app = TileStache.WSGITileServer(config=options.file, autoreload=True)
    run_simple(options.ip, options.port, app)

