#!/usr/bin/python

if __name__ == '__main__':
    from datetime import datetime
    from optparse import OptionParser, OptionValueError
    from werkzeug.serving import run_simple
    import os, sys, TileStache

    parser = OptionParser()
    parser.add_option("-c", "--config", dest="file", default="tilestache.cfg",
        help="the path to the tilestache config")
    parser.add_option("-i", "--ip", dest="ip", default="127.0.0.1",
        help="the IP address to listen on")
    parser.add_option("-p", "--port", dest="port", type="int", default=8080,
        help="the port number to listen on")
    (options, args) = parser.parse_args()

    if not os.path.exists(options.file):
        print >> sys.stderr, "Config file not found. Use -c to pick a tilestache config file."
        sys.exit(1)

    app = TileStache.WSGITileServer(config=options.file, autoreload=True)
    run_simple(options.ip, options.port, app)

