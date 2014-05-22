#TileStache

_a stylish alternative for caching your map tiles_

[![Build Status](https://travis-ci.org/TileStache/TileStache.png)](https://travis-ci.org/TileStache/TileStache)

**TileStache** is a Python-based server application that can serve up map tiles
based on rendered geographic data. You might be familiar with [TileCache](http://tilecache.org), 
the venerable open source WMS server from MetaCarta. TileStache is similar, but we hope 
simpler and better-suited to the needs of designers and cartographers.

##Synopsis

    import TileStache
    import ModestMaps
    
    config = {
      "cache": {"name": "Test"},
      "layers": {
        "example": {
            "provider": {"name": "mapnik", "mapfile": "examples/style.xml"},
            "projection": "spherical mercator"
        } 
      }
    }
    
    # like http://tile.openstreetmap.org/1/0/0.png
    coord = ModestMaps.Core.Coordinate(0, 0, 1)
    config = TileStache.Config.buildConfiguration(config)
    type, bytes = TileStache.getTile(config.layers['example'], coord, 'png')
    
    open('tile.png', 'w').write(bytes)



##Dependencies

###Required:

- ModestMaps: http://modestmaps.com, http://github.com/migurski/modestmaps-py
- Python Imaging Library (PIL): http://www.pythonware.com/products/pil

###Optional:

- Simplejson: https://github.com/simplejson/simplejson (optional if using >= python 2.6)
- mapnik: http://mapnik.org (optional)
- werkzeug: http://werkzeug.pocoo.org/ (optional)

Install the pure python modules with pip:

    sudo pip install -U PIL modestmaps simplejson werkzeug

Install pip (http://www.pip-installer.org/) like:

    curl -O -L https://raw.github.com/pypa/pip/master/contrib/get-pip.py
    sudo python get-pip.py

Install Mapnik via instructions at:

    http://mapnik.org/download


##Installation

TileStache can be run from the download directory as is. For example the scripts:

    tilestache-render.py tilestache-seed.py tilestache-server.py

Can all be run locally like:

    ./scripts/tilestache-server.py

To install globally do:

    python setup.py install
    
  * Note: you may need to prefix that command with 'sudo' to have permissions
to fully install TileStache.


##Quickstart

To make sure TileStache is working start the development server:

    ./scripts/tilestache-server.py

Then open a modern web browser and you should be able to preview tiles at:

    http://localhost:8080/osm/preview.html

This is a previewer that uses ModestMaps and OpenStreetMap tiles from
http://tile.osm.org as defined in the default config file 'tilestache.cfg'


##Documentation

The next step is to learn how build custom layers and serve them.

See the [docs](http://tilestache.org/doc/) for details.


##Features

Rendering providers:
* Mapnik
* Proxy
* Vector
* Templated URLs

Caching backends:
* Local disk
* Test
* Memcache
* S3


##Design Goals

The design of TileStache focuses on approachability at the expense of
cleverness or completeness. Our hope is to make it easy for anyone to design
a new map of their city, publish a fresh view of their world, or even build
the next 8-Bit NYC (http://8bitnyc.com).

* Small

The core of TileStache is intended to have a small code footprint.
It should be quick and easy to to understand what the library is doing and
why, based on common entry points like included CGI scripts. Where possible,
dynamic programming "magic" is to be avoided, in favor of basic, procedural
and copiously-documented Python.

* Pluggable

We want to accept plug-ins and extensions from outside TileStache, and offer
TileStache itself as an extension for other systems. It must be possible to
write and use additional caches or renderers without having to modify the
core package itself, extend classes from inside the package, or navigate
chains of class dependencies. Duck typing and stable interfaces win.

* Sensible Defaults

The default action of a configured TileStache instance should permit the most
common form of interaction: a worldwide, spherical-mercator upper-left oriented
tile layout compatible with those used by OpenStreetMap, Google, Bing Maps,
Yahoo! and others. It should be possible to make TileStache do whatever is
necessary to support any external system, but we eschew complex, impenetrable
standards in favor of pragmatic, fast utility with basic web clients.


##License

BSD, see LICENSE file.
