Usage
=====

TileStache is a Python-based server application that can serve up map
tiles based on rendered geographic data. You might be familiar with
`TileCache <http://tilecache.org>`__ the venerable open source WMS
server from MetaCarta. TileStache is similar, but we hope simpler and
better-suited to the needs of designers and cartographers.

**This document covers TileStache version N.N.N**.

See also `detailed module and class
reference <TileStache.html>`__.

-  `Requesting Tiles <#requesting-tiles>`__

   -  `Over HTTP <#over-http>`__
   -  `In Code <#in-code>`__

-  `Serving Tiles <#serving-tiles>`__

   -  `WSGI <#wsgi>`__
   -  `CGI <#cgi>`__
   -  `mod\_python <#mod-python>`__

-  `Configuring TileStache <#configuring-tilestache>`__

   -  `Caches <#caches>`__
   -  `Layers <#layers>`__
   -  `Providers <#providers>`__
   -  `Projections <#projections>`__
   -  `Metatiles <#metatiles>`__
   -  `Preview <#preview>`__
   -  `Index Page <#index-page>`__
   -  `Logging <#logging>`__

-  `Extending TileStache <#extending-tilestache>`__

   -  `Custom Providers <#custom-providers>`__
   -  `Custom Caches <#custom-caches>`__
   -  `Configuration <#custom-configuration>`__

`Requesting Tiles <#requesting-tiles>`__
------------------------------------------

`Over HTTP <#over-http>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~

TileStache URLs are based on a Google Maps-like scheme:

::

    /{layer name}/{zoom}/{column}/{row}.{extension}

An example tile URL might look like this:

::

    http://example.org/path/tile.cgi/streets/12/656/1582.png

For JSON responses such as those from the `Vector
provider <#vector>`__, URLs can include an optional callback
for `JSONP <http://en.wikipedia.org/wiki/JSONP>`__ support:

::

    http://example.org/path/tile.cgi/streets/12/656/1582.json?callback=funcname

Interactive, slippy-map previews of tiles are also available:

::

    /{layer name}/preview.html

`In Code <#in-code>`__
~~~~~~~~~~~~~~~~~~~~~~

`TileStache.getTile <#tilestache-gettile>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Get a type string and tile binary for a given request layer tile.

Arguments to ``getTile``:

layer
    Instance of ``Core.Layer`` to render.
coord
    One ``ModestMaps.Core.Coordinate`` corresponding to a single tile.
extension
    Filename extension to choose response type, e.g. "png" or "jpg".
ignore\_cached
    Optional boolean: always re-render the tile, whether it's in the
    cache or not. Default False.

Return value of ``getTile`` is a tuple containing a mime-type string
such as "image/png" and a complete byte string representing the rendered
tile.

See
`TileStache.getTile <TileStache.html#TileStache.getTile>`__
documentation for more information.

`TileStache.requestHandler <#tilestache-requesthandler>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Generate a mime-type and response body for a given request. This is the
function to use when creating new HTTP interfaces to TileStache.

Arguments to ``requestHandler``:

config
    Required file path string for a JSON configuration file or a
    configuration object with cache, layers, and dirpath properties,
    such as
    `TileStache.Config.Configuration <TileStache.Config.html#TileStache.Config.Configuration>`__.
path\_info
    Required end portion of a request URL including the layer name and
    tile coordinate, e.g. "/roads/12/656/1582.png".
query\_string
    Optional query string. Currently used only for JSONP callbacks.
script\_name
    Optional script name corresponds to CGI environment variable
    SCRIPT\_NAME, used to calculate correct 302 redirects.

Return value of ``requestHandler`` is a tuple containing a mime-type
string such as "image/png" and a complete byte string representing the
rendered tile.

See
`TileStache.requestHandler <TileStache.html#TileStache.requestHandler>`__
documentation for more information.

`Serving Tiles <#serving-tiles>`__
------------------------------------

We currently provide three scripts for serving tiles: one for a
WSGI-based webserver, one for a CGI-based webserver, and one for Apache
``mod_python``.

`WSGI <#wsgi>`__
~~~~~~~~~~~~~~~~

TileStache comes with a WSGI application and a
`Werkzeug <http://werkzeug.pocoo.org/>`__ web server. To use the
built-in server, run ``tilestache-server.py``, which (by default) looks
for a config file named ``tilestache.cfg`` in the current directory and
then serves tiles on ``http://127.0.0.1:8080/``. Check
``tilestache-server.py --help`` to change these defaults.

Alternatively, any WSGI server can be pointed at an instance of
``TileStache.WSGITileServer``. Here’s how to use it with
`gunicorn <http://gunicorn.org/>`__:

::

    $ gunicorn "TileStache:WSGITileServer('/path/to/tilestache.cfg')"

The same configuration can be served with
`uWSGI <http://projects.unbit.it/uwsgi/>`__ like so. Note the usage of
the ``--eval`` option over ``--module`` as this latter option does not
support argument passing:

::

    $ uwsgi --http :8080 --eval 'import TileStache; \
    application = TileStache.WSGITileServer("/path/to/tilestache.cfg")'

See
`TileStache.WSGITileServer <TileStache.html#TileStache.WSGITileServer>`__
documentation for more information.

`CGI <#cgi>`__
^^^^^^^^^^^^^^

Using TileStache through CGI supports basic tile serving, and is useful
for simple testing and low-to-medium traffic websites. This is a
complete, working CGI script that looks for configuration in a local
file called ``tilestache.cfg``:

::

    #!/usr/bin/python
    import os, TileStache
    TileStache.cgiHandler(os.environ, 'tilestache.cfg', debug=True)

See
`TileStache.cgiHandler <TileStache.html#TileStache.cgiHandler>`__
documentation for more information.

`mod\_python <#mod-python>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Using TileStache through ``mod_python`` improves performance by caching
imported modules, but must be configured via the Apache webserver
config. This is a complete example configuration for a webserver
publishing tiles configured by a file in ``/etc``:

::

    <Directory /var/www/tiles>
      AddHandler mod_python .py
      PythonHandler TileStache::modpythonHandler
      PythonOption config /etc/tilestache.cfg
    </Directory>

See
`TileStache.modpythonHandler <TileStache.html#TileStache.modpythonHandler>`__
documentation for more information.

`Configuring TileStache <#configuring-tilestache>`__
------------------------------------------------------

TileStache configuration is stored in JSON files, and is composed of two
main top-level sections: "cache" and "layers". There are examples of
both in this minimal sample configuration:

::

    {
      "cache": {"name": "Test"},
      "layers": {
        "ex": {
            "provider": {"name": "mapnik", "mapfile": "style.xml"},
            "projection": "spherical mercator"
        }
      }
    }

`Caches <#caches>`__
~~~~~~~~~~~~~~~~~~~~

A Cache is the part of TileStache that stores static files to speed up
future requests. A few default caches are shown here, with additional
cache classes defined in
`TileStache.Goodies.Caches <TileStache.Goodies.Caches.html>`__.

Jump to `Test <#test-cache>`__, `Disk <#disk-cache>`__,
`Multi <#multi-cache>`__, `Memcache <#memcache-cache>`__,
`Redis <#redis-cache>`__, or `S3 <#s3-cache>`__ cache.

`Test <#test-cache>`__
^^^^^^^^^^^^^^^^^^^^^^

Simple cache that doesn’t actually cache anything.

Activity is optionally logged, though.

Example configuration:

::

    {
      "cache": {
        "name": "Test",
        "verbose": true
      },
      "layers": { … }
    }

Test cache parameters:

verbose
    Optional boolean flag to write cache activities to a logging
    function, defaults to False if omitted.

See
`TileStache.Caches.Test <TileStache.Caches.html#TileStache.Caches.Test>`__
documentation for more information.

`Disk <#disk-cache>`__
^^^^^^^^^^^^^^^^^^^^^^

Caches files to disk.

Example configuration:

::

    {
      "cache": {
        "name": "Disk",
        "path": "/tmp/stache",
        "umask": "0000",
        "dirs": "portable",
        "gzip": ["xml", "json"]
      },
      "layers": { … }
    }

Disk cache parameters:

path
    Required local directory path where files should be stored.
umask
    Optional string representation of octal permission mask for stored
    files. Defaults to "0022".
dirs
    Optional string saying whether to create cache directories that are
    safe or portable. For an example tile 12/656/1582.png, "portable"
    creates matching directory trees while "safe" guarantees directories
    with fewer files, e.g. 12/000/656/001/582.png. Defaults to "safe".
gzip
    Optional list of file formats that should be stored in a compressed
    form. Defaults to ["txt", "text", "json", "xml"]. Provide an empty
    list in the configuration for no compression.

If your configuration file is loaded from a remote location, e.g.
http://example.com/tilestache.cfg, the path **must** be an unambiguous
filesystem path, e.g. "file:///tmp/cache".

See
`TileStache.Caches.Disk <TileStache.Caches.html#TileStache.Cache.Disk>`__
documentation for more information.

`Multi <#multi-cache>`__
^^^^^^^^^^^^^^^^^^^^^^^^

Caches tiles to multiple, ordered caches.

Multi cache is well-suited for a speed-to-capacity gradient, for example
a combination of `Memcache <#memcache-cache>`__ and `S3 <#s3-cache>`__
to take advantage of the high speed of memcache and the high capacity of
S3. Each tier of caching is checked sequentially when reading from the
cache, while all tiers are used together for writing. Locks are only
used with the first cache.

Example configuration:

::

    {
      "cache": {
        "name": "Multi",
        "tiers": [
            {
               "name": "Memcache",
               "servers": ["127.0.0.1:11211"]
            },
            {
               "name": "Disk",
               "path": "/tmp/stache"
            }
        ]
      },
      "layers": { … }
    }

Multi cache parameters:

tiers
    Required list of cache configurations. The fastest, most local cache
    should be at the beginning of the list while the slowest or most
    remote cache should be at the end. Memcache and S3 together make a
    great pair.

See
`TileStache.Caches.Multi <TileStache.Caches.html#TileStache.Caches.Multi>`__
documentation for more information.

`Memcache <#memcache-cache>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Caches tiles to `Memcache <http://memcached.org/>`__, requires
`python-memcached <http://www.tummy.com/Community/software/python-memcached/>`__.

Example configuration:

::

    {
      "cache": {
        "name": "Memcache",
        "servers": ["127.0.0.1:11211"],
        "revision": 0,
        "key prefix": "unique-id"
      },
      "layers": { … }
    }

Memcache cache parameters:

servers
    Optional array of servers, list of "{host}:{port}" pairs. Defaults
    to ["127.0.0.1:11211"] if omitted.
revision
    Optional revision number for mass-expiry of cached tiles regardless
    of lifespan. Defaults to 0.
key prefix
    Optional string to prepend to Memcache generated key. Useful when
    running multiple instances of TileStache that share the same
    Memcache instance to avoid key collisions. The key prefix will be
    prepended to the key name. Defaults to "".

See
`TileStache.Memcache.Cache <TileStache.Memcache.html#TileStache.Memcache.Cache>`__
documentation for more information.

`Redis <#redis-cache>`__
^^^^^^^^^^^^^^^^^^^^^^^^

Caches tiles to `Redis <http://redis.io/>`__, requires
`redis-py <https://pypi.python.org/pypi/redis/>`__ and `redis
server <http://redis.io/>`__.

Example configuration:

::


    {
      "cache": {
        "name": "Redis",
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "key prefix": "unique-id"
      },
      "layers": { … }
    }

Redis cache parameters:

host
    Defaults to "localhost" if omitted.
port
    Integer; Defaults to 6379 if omitted.
db
    Integer; Redis database number, defaults to 0 if omitted.
key prefix
    Optional string to prepend to generated key. Useful when running
    multiple instances of TileStache that share the same Redis database
    to avoid key collisions (though the prefered solution is to use a
    different db number). The key prefix will be prepended to the key
    name. Defaults to "".

See
`TileStache.Redis.Cache <TileStache.Redis.html#TileStache.Redis.Cache>`__
documentation for more information.

`S3 <#s3-cache>`__
^^^^^^^^^^^^^^^^^^

Caches tiles to `Amazon S3 <https://s3.amazonaws.com/>`__, requires
`boto <http://pypi.python.org/pypi/boto>`__ (2.0+).

Example configuration:

::

    {
      "cache": {
        "name": "S3",
        "bucket": "<bucket name>",
        "access": "<access key>",
        "secret": "<secret key>"
        "reduced_redundancy": False
      },
      "layers": { … }
    }

S3 cache parameters:

bucket
    Required bucket name for S3. If it doesn’t exist, it will be
    created.
access
    Optional access key ID for your S3 account. You can find this under
    “Security Credentials” at your `AWS account
    page <http://aws.amazon.com/account/>`__.
secret
    Optional secret access key for your S3 account. You can find this
    under “Security Credentials” at your `AWS account
    page <http://aws.amazon.com/account/>`__.
use\_locks
    Optional boolean flag for whether to use the locking feature on S3.
    True by default. A good reason to set this to false would be the
    additional price and time required for each lock set in S3.
path
    Optional path under bucket to use as the cache directory. ex.
    'path': 'cache' will put tiles under {bucket}/cache/
reduced\_redundancy
    Optional boolean specifying whether to use Reduced Redundancy
    Storage mode in S3. Files stored with RRS incur less cost but have
    reduced redundancy in Amazon's storage system.

When access or secret are not provided, the environment variables
AWS\_ACCESS\_KEY\_ID and AWS\_SECRET\_ACCESS\_KEY will be used. See
`Boto
documentation <http://docs.pythonboto.org/en/latest/s3_tut.html#creating-a-connection>`__
for more information.

See
`TileStache.S3.Cache <TileStache.S3.html#TileStache.S3.Cache>`__
documentation for more information.

`Additional Caches <#additional-caches>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

New caches with functionality that’s not strictly core to TileStache
first appear in
`TileStache.Goodies.Caches <TileStache.Goodies.Caches.html>`__.

LimitedDisk
'''''''''''

Cache that stores a limited amount of data. This is an example cache
that uses a SQLite database to track sizes and last-read times for
cached tiles, and removes least-recently-used tiles whenever the total
size of the cache exceeds a set limit. See
`TileStache.Goodies.Caches.LimitedDisk <TileStache.Goodies.Caches.LimitedDisk.html>`__
for more information.

`Layers <#layers>`__
~~~~~~~~~~~~~~~~~~~~

A Layer represents a set of tiles in TileStache. It keeps references to
providers, projections, a Configuration instance, and other details
required for to the storage and rendering of a tile set.

Example layer configuration:

::

    {
      "cache": …,
      "layers":
      {
        "example-name":
        {
          "provider": { … },
          "metatile": { … },
          "preview": { … },
          "stale lock timeout": …,
          "cache lifespan": …,
          "projection": …,
          "write cache": …,
          "bounds": { … },
          "allowed origin": …,
          "maximum cache age": …,
          "redirects": …,
          "tile height": …,
          "jpeg options": …,
          "png options": …,
          "pixel effect": { … }
        }
      }
    }

The public-facing URL of a single tile for this layer might look like
this:

::

    http://example.com/tilestache.cgi/example-name/0/0/0.png

Shared layer parameters:

provider
    Refers to a Provider, explained in detail under
    `Providers <#providers>`__.
metatile
    Optionally makes it possible for multiple individual tiles to be
    rendered at one time, for greater speed and efficiency. This is
    commonly used for bitmap providers such as Mapnik. See
    `Metatiles <#metatiles>`__ for more information.
preview
    Optionally overrides the starting point for the built-in per-layer
    slippy map preview, useful for image-based layers where appropriate.
    See `Preview <#preview>`__ for more information.
projection
    Names a geographic projection, explained in
    `Projections <#projections>`__. If omitted, defaults to "spherical
    mercator".
stale lock timeout
    An optional number of seconds to wait before forcing a lock that
    might be stuck. This is defined on a per-layer basis, rather than
    for an entire cache at one time, because you may have different
    expectations for the rendering speeds of different layer
    configurations. Defaults to 15.
cache lifespan
    An optional number of seconds that cached tiles should be stored.
    This is defined on a per-layer basis. Defaults to forever if None, 0
    or omitted.
write cache
    An optional boolean value to allow skipping cache write altogether.
    This is defined on a per-layer basis. Defaults to true if omitted.
bounds
    An optional dictionary of six tile boundaries to limit the rendered
    area: low (lowest zoom level), high (highest zoom level), north,
    west, south, and east (all in degrees). When any of these are
    omitted, default values are north=89, west=-180, south=-89,
    east=180, low=0, and high=31. A list of dictionaries will also be
    accepted, indicating a set of possible bounding boxes any one of
    which includes possible tiles.
allowed origin
    An optional string that shows up in the response HTTP header
    `Access-Control-Allow-Origin <http://www.w3.org/TR/cors/#access-control-allow-origin-response-hea>`__,
    useful for when you need to provide javascript direct access to
    response data such as GeoJSON or pixel values. The header is part of
    a `W3C working draft <http://www.w3.org/TR/cors/>`__. Pro-tip: if
    you want to allow maximum permissions and minimal security headache,
    use a value of "\*" for this.
maximum cache age
    An optional number of seconds used to control behavior of downstream
    caches. Causes TileStache responses to include
    `Cache-Control <http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.9>`__
    and
    `Expires <http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.21>`__
    HTTP response headers. Useful when TileStache is itself hosted
    behind an HTTP cache such as Squid, Cloudfront, or Akamai.
redirects
    An optional dictionary of per-extension HTTP redirects, treated as
    lowercase. Useful in cases where your tile provider can support many
    formats but you want to enforce limits to save on cache usage. If a
    request is made for a tile with an extension in the dictionary keys,
    a response can be generated that redirects the client to the same
    tile with another extension. For example, use the setting {"jpg":
    "png"} to force all requests for JPEG tiles to be redirected to PNG
    tiles.
tile height
    An optional integer gives the height of the image tile in pixels.
    You almost always want to leave this at the default value of 256,
    but you can use a value of 512 to create double-size,
    double-resolution tiles for high-density phone screens.
jpeg options
    An optional dictionary of JPEG creation options, passed through `to
    PIL <http://effbot.org/imagingbook/format-jpeg.htm>`__. Valid
    options include quality (integer), progressive (boolean), and
    optimize (boolean).
png options
    An optional dictionary of PNG creation options, passed through `to
    PIL <http://effbot.org/imagingbook/format-png.htm>`__. Valid options
    include palette (URL or filename), palette256 (boolean) and optimize
    (boolean).
pixel effect
    An optional dictionary that defines an effect to be applied for all
    tiles of this layer. Pixel effect can be any of these: blackwhite,
    greyscale, desaturate, pixelate, halftone, or blur.

`Providers <#providers>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~

A Provider is the part of TileStache that stores static files to speed
up future requests. A few default providers are shown here, with
additional provider classes defined in
`TileStache.Goodies.Providers <TileStache.Goodies.Providers.html>`__

Jump to `Mapnik (image) <#mapnik-provider>`__,
`Proxy <#proxy-provider>`__, `Vector <#vector>`__, `URL
Template <#url-template-provider>`__, `MBTiles <#mbtiles-provider>`__,
`Mapnik (grid) <#mapnik-grid-provider>`__, or `Pixel
Sandwich <#sandwich-provider>`__ provider.

`Mapnik <#mapnik-provider>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Built-in Mapnik provider, renders map images from Mapnik XML files.

Example Mapnik provider configuration:

::

    {
      "cache": { … }.
      "layers":
      {
        "roads":
        {
          "provider":
          {
            "name": "mapnik",
            "mapfile": "style.xml"
          }
        }
      }
    }

Mapnik provider parameters:

mapfile
    Required local file path to Mapnik XML file.
fonts
    Optional relative directory path to *\*.ttf* font files

See
`TileStache.Mapnik.ImageProvider <TileStache.Mapnik.html#TileStache.Mapnik.ImageProvider>`__
for more information.

`Proxy <#proxy-provider>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Proxy provider, to pass through and cache tiles from other places.

Example Proxy provider configuration:

::

    {
      "cache": { … }.
      "layers":
      {
        "roads":
        {
          "provider":
          {
            "name": "proxy",
            "url": "http://tile.openstreetmap.org/{Z}/{X}/{Y}.png"
          }
        }
      }
    }

Proxy provider parameters:

url

Optional URL template for remote tiles, for example:
"http://tile.openstreetmap.org/{Z}/{X}/{Y}.png"

provider

Optional provider name string from Modest Maps built-ins. See
``ModestMaps.builtinProviders.keys()`` for a list. Example:
"OPENSTREETMAP".

timeout

Defines a timeout in seconds for the request. If not defined, the global
default timeout setting will be used.

See
`TileStache.Providers.Proxy <TileStache.Providers.html#TileStache.Providers.Proxy>`__
for more information.

`Vector <#vector>`__
^^^^^^^^^^^^^^^^^^^^

Provider that returns vector representation of features in a data
source.

Currently two serializations and three encodings are supported for a
total of six possible kinds of output with these tile name extensions:

GeoJSON (.geojson)
    Conforms to the `GeoJSON
    specification <http://geojson.org/geojson-spec.html>`__.
Arc GeoServices JSON (.arcjson)
    Conforms to ESRI’s `GeoServices REST
    specification <http://www.esri.com/library/whitepapers/pdfs/geoservices-rest-spec.pdf>`__.
GeoBSON (.geobson) and Arc GeoServices BSON (.arcbson)
    `BSON-encoded <http://bsonspec.org/#/specification>`__ GeoJSON and
    Arc JSON.
GeoAMF (.geoamf) and Arc GeoServices AMF (.arcamf)
    `AMF0-encoded <http://opensource.adobe.com/wiki/download/attachments/1114283/amf0_spec_121207.pdf>`__
    GeoJSON and Arc JSON.

Example Vector provider configurations:

::

    {
      "cache": { … }.
      "layers":
      {
        "vector-postgis-points":
        {
          "provider": {"name": "vector", "driver": "PostgreSQL",
                       "parameters": {"dbname": "geodata", "user": "geodata",
                                      "table": "planet_osm_point"}}
        },
        "vector-shapefile-lines":
        {
          "provider": {"name": "vector", "driver": "shapefile",
                       "parameters": {"file": "oakland-uptown-line.latlon.shp"},
                       "properties": {"NAME": "name", "HIGHWAY": "highway"}}
        },
        "vector-sf-streets":
        {
          "provider": {"name": "vector", "driver": "GeoJSON",
                       "parameters": {"file": "stclines.json"},
                       "properties": ["STREETNAME"]}
        },
        {
          "provider": {"name": "vector", "driver": "MySQL",
                       "parameters": {"dbname": "geodata", "port": "3306",
                                       "user": "geotest", "table": "test"},
                       "properties": ["name"], "id_property": "oid"}
        },
        {
          "provider": {"name": "vector", "driver": "Oracle",
                       "parameters": {"dbname": "ORCL", "port": "3306",
                                      "user": "scott", "password": "tiger",
                                      "table": "test"}}
        },
        {
          "provider": {"name": "vector", "driver": "Spatialite",
                       "parameters": {"file": "test.sqlite", "layer": "test"}}
        }
      }
    }

Vector provider parameters:

driver
    String used to identify an OGR driver. Currently, only "ESRI
    Shapefile", "PostgreSQL", and "GeoJSON" are supported as data source
    drivers, with "postgis" and "shapefile" accepted as synonyms. Not
    case-sensitive.
parameters
    Dictionary of parameters for each driver.

    PostgreSQL, MySQL and Oracle
        "dbname" parameter is required, with name of database. "host",
        "user", and "password" are optional connection parameters. One
        of "table" or "query" is required, with a table name in the
        first case and a complete SQL query in the second.
    Shapefile and GeoJSON
        "file" parameter is required, with filesystem path to data file.
    Spatialite
        "file" parameter is required, with filesystem path to data file.
        "layer" parameter is required, and is the name of the SQLite
        table.

properties
    Optional list or dictionary of case-sensitive output property names.
     If omitted, all fields from the data source will be included in
    response. If a list, treated as a whitelist of field names to
    include in response. If a dictionary, treated as a whitelist and
    re-mapping of field names.
clipped
    Default is true.
     Boolean flag for optionally clipping the output geometries to the
    bounds of the enclosing tile, or the string value "padded" for
    clipping to the bounds of the tile plus 5%. This results in
    incomplete geometries, dramatically smaller file sizes, and improves
    performance and compatibility with
    `Polymaps <http://polymaps.org>`__.
projected
    Default is false.
     Boolean flag for optionally returning geometries in projected
    rather than geographic coordinates. Typically this means EPSG:900913
    a.k.a. spherical mercator projection. Stylistically a poor fit for
    GeoJSON, but useful when returning Arc GeoServices responses.
precision
    Default is 6.
     Optional number of decimal places to use for floating point values.
spacing
    Optional number of tile pixels for spacing geometries in responses.
    Used to cut down on the number of returned features by ensuring that
    only those features at least this many pixels apart are returned.
    Order of features in the data source matters: early features beat
    out later features.
verbose
    Default is false.
     Boolean flag for optionally expanding output with additional
    whitespace for readability. Results in larger but more readable
    GeoJSON responses.
skip\_empty\_fields
    Default is False.
     Boolean flag for optionally skipping empty fields when assembling
    the GEOJSON feature's properties dictionary.

See
`TileStache.Vector <TileStache.Vector.html>`__
for more information.

`URL Template <#url-template-provider>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Templated URL provider, to pass through and cache tiles from WMS
servers.

Example UrlTemplate provider configuration:

::

    {
      "cache": { … }.
      "layers":
      {
        "roads":
        {
          "provider":
          {
            "name": "url template",
            "template": "http://example.com/?bbox=$xmin,$ymin,$xmax,$ymax"
          }
        }
      }
    }

UrlTemplate provider parameters:

template

String with substitutions suitable for use in
`string.Template <http://docs.python.org/library/string.html#string.Template>`__.
The variables available for substitution are width, height (in pixels),
srs (in `PROJ.4 format <http://trac.osgeo.org/proj/wiki/GenParms>`__),
xmin, ymin, xmax, ymax (in projected map units), and zoom. Example:
"http://example.com/?bbox=$xmin,$ymin,$xmax,$ymax&bboxSR=102113&size=$width,$height&imageSR=102113&format=jpg&f=image".

referer

Optional string with HTTP Referer URL to send to WMS server. Some WMS
servers use the Referer request header to authenticate requests; this
parameter provides one.

source projection

Names a geographic projection, explained in
`Projections <#projections>`__, that coordinates should be transformed
to for requests.

timeout

Defines a timeout in seconds for the request. If not defined, the global
default timeout setting will be used.

See
`TileStache.Providers.UrlTemplate <TileStache.Providers.html#TileStache.Providers.UrlTemplate>`__
for more information.

`MBTiles <#mbtiles-provider>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Provider that reads stored images from `MBTiles
tilesets <http://mbtiles.org/>`__.

Example MBTiles provider configuration:

::

    {
      "cache": { … }.
      "layers":
      {
        "roads":
        {
          "provider":
          {
            "name": "mbtiles",
            "tileset": "collection.mbtiles"
          }
        }
      }
    }

MBTiles provider parameters:

tileset
    Required local file path to MBTiles tileset file, a SQLite 3
    database file.

See
`TileStache.MBTiles.Provider <TileStache.MBTiles.html#TileStache.MBTiles.Provider>`__
for more information.

`Mapnik Grid <#mapnik-grid-provider>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Built-in Mapnik `UTF
Grid <https://github.com/mapbox/utfgrid-spec/blob/master/1.2/utfgrid.md>`__
provider, renders JSON raster objects from Mapnik 2.0+.

Example Mapnik Grid provider configurations:

::

    {
      "cache": { … }.
      "layers":
      {
        "one-grid":
        {
          "provider":
          {
            "name": "mapnik grid",
            "mapfile": "style.xml",
            "layer_index": 1
          },
        }
        "two-grids":
        {
          "provider":
          {
            "name": "mapnik grid",
            "mapfile": "style.xml",
            "layers":
            [
              [2, ["population"]],
              [0, ["name", "population"]]
            ]
          }
        }
      }
    }

Mapnik Grid provider parameters:

mapfile
    Required local file path to Mapnik XML file.
fields
    Optional array of field names to return in the response, defaults to
    all. An empty list will return no field names, while a value of null
    is equivalent to all.
layer\_index
    Optional layer from the mapfile to render, defaults to 0 (first
    layer).
layers
    Optional ordered list of (layer\_index, fields) to combine; if
    provided layers overrides both layer\_index and fields arguments.
scale
    Optional scale factor of output raster, defaults to 4 (64×64).
layer\_id\_key
    Optional. If set, each item in the "data" property will have its
    source mapnik layer name added, keyed by this value. Useful for
    distingushing between data items.

See
`TileStache.Mapnik.GridProvider <TileStache.Mapnik.html#GTileStache.Mapnik.GridProvider>`__
for more information.

`Pixel Sandwich <#sandwich-provider>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Sandwich Provider supplies a Photoshop-like rendering pipeline,
making it possible to use the output of other configured tile layers as
layers or masks to create a combined output. Sandwich is modeled on Lars
Ahlzen’s `TopOSM <http://www.toposm.com/>`__.

Sandwich require the external `Blit
library <http://github.com/migurski/Blit>`__ to function.

Example Sandwich provider configurations:

::

    {
      "cache": { … }.
      "layers":
      {
        "sandwiches":
        {
          "provider":
          {
            "name": "Sandwich",
            "stack":
            [
              {"src": "base"},
              {"src": "outlines", "mask": "halos"},
              {"src": "streets"}
            ]
          }
        },
        "base":
        {
          "provider": {"name": "mapnik", "mapfile": "mapnik-base.xml"}
        },
        "halos":
        {
          "provider": {"name": "mapnik", "mapfile": "mapnik-halos.xml"},
          "metatile": {"buffer": 128}
        },
        "outlines":
        {
          "provider": {"name": "mapnik", "mapfile": "mapnik-outlines.xml"},
          "metatile": {"buffer": 16}
        },
        "streets":
        {
          "provider": {"name": "mapnik", "mapfile": "mapnik-streets.xml"},
          "metatile": {"buffer": 128}
        }
      }
    }

Sandwich provider parameters:

stack
    Required layer or stack of layers that can be combined to create
    output. The stack is a list, with solid color or raster layers from
    elsewhere in the configuration, and is described in detail in the
    dedicated `Sandwich
    documentation <TileStache.Sandwich.html>`__.

See
`TileStache.Sandwich <TileStache.Sandwich.html>`__
for more information.

`Additional Providers <#additional-providers>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

New providers with functionality that’s not strictly core to TileStache
first appear in
`TileStache.Goodies.Providers <TileStache.Goodies.Providers.html>`__.

Grid
''''

Grid rendering for TileStache. UTM provider draws gridlines in tiles, in
transparent images suitable for use as map overlays. See
`TileStache.Goodies.Providers.Grid <TileStache.Goodies.Providers.Grid.html>`__
for more information.

PostGeoJSON
'''''''''''

Provider that returns GeoJSON data responses from PostGIS queries. This
is an example of a provider that does not return an image, but rather
queries a database for raw data and replies with a string of GeoJSON.
For example, it’s possible to retrieve data for locations of
OpenStreetMap points of interest based on a query with a bounding box
intersection. See
`TileStache.Goodies.Providers.PostGeoJSON <TileStache.Goodies.Providers.PostGeoJSON.html>`__
for more information.

SolrGeoJSON
'''''''''''

Provider that returns GeoJSON data responses from Solr spatial queries.
This is an example of a provider that does not return an image, but
rather queries a Solr instance for raw data and replies with a string of
GeoJSON. See
`TileStache.Goodies.Providers.SolrGeoJSON <TileStache.Goodies.Providers.SolrGeoJSON.html>`__
for more information.

Composite
'''''''''

Layered, composite rendering for TileStache. See
`TileStache.Goodies.Providers.Composite <TileStache.Goodies.Providers.Composite.html>`__
for more information.

MirrorOSM
'''''''''

Requests for tiles have the side effect of running
`osm2pgsql <http://wiki.openstreetmap.org/wiki/Osm2pgsql>`__ to populate
a PostGIS database of OpenStreetMap data from a remote API source. It
would be normal to use this provider outside the regular confines of a
web server, perhaps with a call to ``tilestache-seed.py`` governed by a
cron job or some other out-of-band process. See
`TileStache.Goodies.Providers.MirrorOSM <TileStache.Goodies.Providers.MirrorOSM.html>`__
for more information.

`Projections <#projections>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A Projection defines the relationship between the rendered tiles and the
underlying geographic data. Generally, just one popular projection is
used for most web maps, "spherical mercator".

Provided projections:

spherical mercator
    Projection for most commonly-used web map tile scheme, equivalent to
    ``EPSG:900913``. The simplified projection used here is described in
    greater detail at
    `openlayers.org <http://trac.openlayers.org/wiki/SphericalMercator>`__.
WGS84
    Unprojected projection for the other commonly-used web map tile
    scheme, equivalent to ``EPSG:4326``.

You can define your own projection, with a module and object name as
arguments:

::

    "layer-name": {
        ...
        "projection": "Module:Object",
    }

The object must include methods that convert between coordinates,
points, and locations. See the included mercator and WGS84
implementations for example. You can also instantiate a projection class
using this syntax:

::

    "layer-name": {
        ...
        "projection": "Module:Object()"
    }

See
`TileStache.Geography <TileStache.Geography.html>`__
for more information.

`Metatiles <#metatiles>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^

Metatiles are larger areas to be rendered at one time, often used
because it’s more efficient to render a large number of contiguous tiles
at once than each one separately.

Example metatile configuration:

::

    {
      "cache": …,
      "layers":
      {
        "example-name":
        {
          "provider": { … },
          "metatile":
          {
            "rows": 4,
            "columns": 4,
            "buffer": 64
          }
        }
      }
    }

This example metatile is four rows tall and four columns wide with a
buffer of 64 pixels, for a total bitmap size of 4 × 256 + 64 × 2 =
**1152**.

Metatile parameters:

rows
    Height of the metatile measured in tiles.
columns
    Width of the metatile measured in tiles.
buffer
    Buffer area around the metatile, measured in pixels. This is useful
    for providers with labels or icons, where it’s necessary to draw a
    bit extra around the edges to ensure that text is not cut off.

`Preview <#preview>`__
^^^^^^^^^^^^^^^^^^^^^^

TileStache includes a built-in slippy map preview, that can be viewed in
a browser using the URL /{layer name}/preview.html, e.g.
http://example.org/example-name/preview.html. The settings for this
preview are completely optional, but can be set on a per-layer basis for
control over starting location and file extension.

Example preview configuration:

::

    {
      "cache": …,
      "layers":
      {
        "example-name":
        {
          "provider": { … },
          "preview":
          {
            "lat": 37.80439,
            "lon": -122.27127,
            "zoom": 15,
            "ext": "jpg"
          }
        }
      }
    }

This example preview displays JPG tiles, and is centered on `37.80439,
-122.27127 at zoom 15 <http://osm.org/go/TZNQsg5C-->`__.

Preview parameters:

lat
    Starting latitude in degrees.
lon
    Starting longitude in degrees.
zoom
    Starting zoom level.
ext
    Filename extension, e.g. "png".

`Index Page <#index-page>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

TileStache supports configurable index pages for the front page of an
instance. A custom index can be specified as a filename relative to the
configuration location. Typically an HTML document would be given here,
but other kinds of files such as images can be used, with MIME
content-type headers determined by
`mimetypes.guess\_type <http://docs.python.org/library/mimetypes.html#mimetypes.guess_type>`__.
A simple text greeting is displayed if no index is provided.

Example index page configuration:

::

    {
      "cache": …,
      "layers": …,
      "index": "filename.html"
      }
    }

Example index page configuration using a remote image:

::

    {
      "cache": …,
      "layers": …,
      "index": "http://tilestache.org/mustaches.jpg"
      }
    }

`Logging <#logging>`__
^^^^^^^^^^^^^^^^^^^^^^

TileStache includes basic support for Python’s built-in `logging
system <http://docs.python.org/library/logging.html>`__, with a logging
level settable in the main configuration file. Possible logging levels
include "debug", "info", "warning", "error" and "critical", described in
the `basic logging
tutorial <http://docs.python.org/howto/logging.html>`__.

Example logging configuration:

::

    {
      "cache": …,
      "layers": …,
      "logging": "debug"
      }
    }

`Extending TileStache <#extending-tilestache>`__
------------------------------------------------

TileStache relies on `duck
typing <http://en.wikipedia.org/wiki/Duck_typing>`__ rather than
inheritance for extensibility, so all guidelines for customization below
explain what methods and properties must be defined on objects for them
to be valid as providers, caches, and configurations.

`Custom Providers <#custom-providers>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Example external provider configuration:

::

    {
      "cache": …,
      "layers":
      {
        "example-name":
        {
          "provider":
          {
            "class": "Module:Classname",
            "kwargs": {"frob": "yes"}
          }
        }
      }
    }

The class value is split up into module and classname, and dynamically
included. If this doesn’t work for some reason, TileStache will fail
loudly to let you know. The kwargs value is fed to the class constructor
as a dictionary of keyword args. If your defined class doesn’t accept
any of these keyword arguments, TileStache will throw an exception.

A provider must offer at least one of two methods for rendering map
areas: ``renderTile`` or ``renderArea``. A provider must also accept an
instance of ``Layer`` as the first argument to its constructor.

Return value of both ``renderTile`` and ``renderArea`` is an object with
a ``save`` method that can accept a file-like object and a format name,
typically an instance of the ``PIL.Image`` object but allowing for
creation of providers that save text, raw data or other non-image
response.

A minimal provider stub class:

::

    class ProviderStub:

      def __init__(self, layer):
        # create a new provider for a layer
        raise NotImplementedError

      def renderTile(self, width, height, srs, coord):
        # return an object with a PIL-like save() method for a tile
        raise NotImplementedError

      def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom):
        # return an object with a PIL-like save() method for an area
        raise NotImplementedError

In cases where a provider generates a response that should not be
cached, ``renderTile`` and ``renderArea`` may raise the
`Core.NoTileLeftBehind <TileStache.Core.html#NoTileLeftBehind>`__
exception in lieu of a normal response. The exception is constructed
using the intended response object, but nothing will be written to
cache. This feature might useful in cases where a full tileset is being
rendered for static hosting, and you don’t want millions of identical
ocean tiles.

See
`TileStache.Providers <TileStache.Providers.html>`__
for more information on custom providers and
`TileStache.Goodies.Providers <TileStache.Goodies.Providers.html>`__
for examples of custom providers.

`provider.renderTile <#provider-rendertile>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Draws a single tile at a time.

Arguments to ``renderTile``:

width
    Pixel width of tile, typically 256.
height
    Pixel height of tile, typically 256.
srs
    Projection as Proj4 string. "+proj=longlat +ellps=WGS84
    +datum=WGS84" is an example, see
    `TileStache.Geography <TileStache.Geography.html>`__
    for actual values.
coord
    Coordinate object representing a single tile.

Return value of ``renderTile`` is a
`PIL.Image <http://effbot.org/imagingbook/image.htm#Image.save>`__
or other saveable object, used like this:

::

    provider.renderTile(…).save(file, "XML")

`provider.renderArea <#provider-renderarea>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Draws a variably-sized area, and is used when drawing metatiles.

Non-image providers and metatiles do not mix. If your provider returns
JSON, plaintext, XML, or some other non-PIL format, implement only the
``renderTile`` method.

Arguments to ``renderArea``:

width
    Pixel width of tile, typically 256.
height
    Pixel height of tile, typically 256.
srs
    Projection as Proj4 string. "+proj=longlat +ellps=WGS84
    +datum=WGS84" is an example, see
    `TileStache.Geography <TileStache.Geography.html>`__
    for actual values.
xmin
    Minimum x boundary of rendered area in projected coordinates.
ymin
    Minimum y boundary of rendered area in projected coordinates.
xmax
    Maximum x boundary of rendered area in projected coordinates.
ymax
    Maximum y boundary of rendered area in projected coordinates.
zoom
    Zoom level of final map. Technically this can be derived from the
    other arguments, but that’s a hassle so we’ll pass it in explicitly.

Return value of ``renderArea`` is a
`PIL.Image <http://effbot.org/imagingbook/image.htm#Image.save>`__
or other saveable object, used like this:

::

    provider.renderArea(…).save(file, "PNG")

`provider.getTypeByExtension <#provider-gettypebyextension>`__
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A provider may offer a method for custom response types,
``getTypeByExtension``. This method returns a tuple with two strings: a
mime-type and a format.

Arguments to ``getTypeByExtension``:

extension
    Filename extension string, e.g. "png", "json", etc.

`Custom Caches <#custom-caches>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Example external provider configuration:

::

    {
      "cache":
      {
        "class": "Module:Classname",
        "kwargs": {"frob": "yes"}
      },
      "layers": { … }
    }

The class value is split up into module and classname, and dynamically
included. If this doesn’t work for some reason, TileStache will fail
loudly to let you know. The kwargs value is fed to the class constructor
as a dictionary of keyword args. If your defined class doesn’t accept
any of these keyword arguments, TileStache will throw an exception.

A cache must provide all of these five methods: ``lock``, ``unlock``,
``remove``, ``read``, and ``save``.

Each method requires three arguments:

layer
    Instance of a layer.
coord
    Single Coordinate that represents a tile.
format
    String like "png" or "jpg" that is used as a filename extension.

The ``save`` method accepts an additional argument *before the others*:

body
    Raw content to save to the cache.

A minimal cache stub class:

::

    class CacheStub:

      def lock(self, layer, coord, format):
        # lock a tile
        raise NotImplementedError

      def unlock(self, layer, coord, format):
        # unlock a tile
        raise NotImplementedError

      def remove(self, layer, coord, format):
        # remove a tile
        raise NotImplementedError

      def read(self, layer, coord, format):
        # return raw tile content from cache
        raise NotImplementedError

      def save(self, body, layer, coord, format):
        # save raw tile content to cache
        raise NotImplementedError

See
`TileStache.Caches <TileStache.Caches.html>`__
for more information on custom caches and
`TileStache.Goodies.Caches <TileStache.Goodies.Caches.html>`__
for examples of custom caches.

`Custom Configuration <#custom-configuration>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A complete configuration object includes cache, layers, and dirpath
properties and optional index property:

cache
    Cache instance, e.g. ``TileStache.Caches.Disk`` etc. See
    `TileStache.Caches <TileStache.Caches.html>`__
    for details on what makes a usable cache.
layers
    Dictionary of layers keyed by name.
dirpath
    Local filesystem path for this configuration, useful for expanding
    relative paths.
index
    Two-element tuple with mime-type and content for installation index
    page.

When creating a custom layers dictionary, e.g. for dynamic layer
collections backed by some external configuration, these `dictionary
methods <http://docs.python.org/library/stdtypes.html#mapping-types-dict>`__
must be provided for a complete collection of layers:

keys
    Return list of layer name strings.
items
    Return list of (name, layer) pairs.
\_\_contains\_\_
    Return boolean true if given key is an existing layer.
\_\_getitem\_\_
    Return existing layer object for given key or raise ``KeyError``.

A minimal layers dictionary stub class:

::

    class LayersStub:

      def keys(self):
        # return a list of key strings
        raise NotImplementedError

      def items(self):
        # return a list of (key, layer) tuples
        raise NotImplementedError

      def __contains__(self, key):
        # return True if the key is here
        raise NotImplementedError

      def __getitem__(self, key):
        # return the layer named by the key
        raise NotImplementedError

