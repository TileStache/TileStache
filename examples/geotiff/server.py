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
import gdal, osr
import os

from xml.etree.ElementTree import Element, tostring, fromstring
from xmljson import badgerfish as bf

if __name__ == '__main__':
    from datetime import datetime
    from optparse import OptionParser, OptionValueError
    import os, sys

    parser = OptionParser()
    filename = "cea.tif"
    filepath = gdal.Open(os.path.join(os.path.dirname(os.path.realpath(__file__)), filename))
    srs = osr.SpatialReference()
    srs.ImportFromWkt(raster.GetProjectionRef())
    layer_srs = srs.ExportToProj4()
    map_srs = "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0.0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs +over"

    mapnik_config_json = {
       "Map":{
          "@srs":map_srs,
          "@font-directory":"./fonts",
          "Style":{
             "@name":"raster-style",
             "Rule":{
                "RasterSymbolizer":{

                }
             }
          },
          "Layer":{
             "@status":"on",
             "@srs":layer_srs,
             "@name":"raster-layer",
             "StyleName":{
                "$":"raster-style"
             },
             "Datasource":{
                "Parameter":[
                   {
                      "@name":"type",
                      "$":"gdal"
                   },
                   {
                      "@name":"file",
                      "$":filepath
                   },
                   {
                      "@name":"format",
                      "$":"tiff"
                   }
                ]
             }
          }
       }
    }


    mapnik_config = tostring(bf.etree(mapnik_config_json)[0])
    print mapnik_config

    config = {
        "cache": {
            "name": "Test",
            "path": "/tmp/stache",
            "umask": "0000"
        },
        "layers": {
            "geotiff": {
                "provider": {"name": "mapnik", "mapconfig": mapnik_config},
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
