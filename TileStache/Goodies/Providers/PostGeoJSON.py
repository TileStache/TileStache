""" Provider that returns GeoJSON data responses from PostGIS queries.

Note:

The built-in TileStache Vector provider (new in version 1.9.0) offers a more
complete method of generating vector tiles, and supports many kinds of data
sources not avilable in PostGeoJSON such as shapefiles. PostGeoJSON will
continue to be provided and supported in TileStache, but future development
of vector support will be contentrated on the mainline Vector provider, not
this one.

More information:
  http://tilestache.org/doc/TileStache.Vector.html

Anyway.

This is an example of a provider that does not return an image, but rather
queries a database for raw data and replies with a string of GeoJSON. For
example, it's possible to retrieve data for locations of OpenStreetMap points
of interest based on a query with a bounding box intersection.

Read more about the GeoJSON spec at: http://geojson.org/geojson-spec.html

Many Polymaps (http://polymaps.org) examples use GeoJSON vector data tiles,
which can be effectively created using this provider.

Keyword arguments:

  dsn:
    Database connection string suitable for use in psycopg2.connect().
    See http://initd.org/psycopg/docs/module.html#psycopg2.connect for more.
  
  query:
    PostGIS query with a "!bbox!" placeholder for the tile bounding box.
    Note that the table *must* use the web spherical mercaotr projection
    900913. Query should return an id column, a geometry column, and other
    columns to be placed in the GeoJSON "properties" dictionary.
    See below for more on 900913.
  
  clipping:
    Boolean flag for optionally clipping the output geometries to the bounds
    of the enclosing tile. Defaults to fales. This results in incomplete
    geometries, dramatically smaller file sizes, and improves performance
    and compatibility with Polymaps (http://polymaps.org).
  
  id_column:
    Name of id column in output, detaults to "id". This determines which query
    result column is placed in the GeoJSON "id" field.
  
  geometry_column:
    Name of geometry column in output, defaults to "geometry". This determines
    which query result column is reprojected to lat/lon and output as a list
    of geographic coordinates.
  
  indent:
    Number of spaces to indent output GeoJSON response. Defaults to 2.
    Skip all indenting with a value of zero.
  
  precision:
    Number of decimal places of precision for output geometry. Defaults to 6.
    Default should be appropriate for almost all street-mapping situations.
    A smaller value can help cut down on output file size for lower-zoom maps.

Example TileStache provider configuration:

  "points-of-interest":
  {
    "provider":
    {
      "class": "TileStache.Goodies.Providers.PostGeoJSON.Provider",
      "kwargs":
      {
        "dsn": "dbname=geodata user=postgres",
        "query": "SELECT osm_id, name, way FROM planet_osm_point WHERE way && !bbox! AND name IS NOT NULL",
        "id_column": "osm_id", "geometry_column": "way",
        "indent": 2
      }
    }
  }

Caveats:

Currently only databases in the 900913 (google) projection are usable,
though this is the default setting for OpenStreetMap imports from osm2pgsql.
The "!bbox!" query placeholder (see example below) must be lowercase, and
expands to:
    
    ST_SetSRID(ST_MakeBox2D(ST_MakePoint(ulx, uly), ST_MakePoint(lrx, lry)), 900913)
    
You must support the "900913" SRID in your PostGIS database for now.
For populating the internal PostGIS spatial_ref_sys table of projections,
this seems to work:

  INSERT INTO spatial_ref_sys
    (srid, auth_name, auth_srid, srtext, proj4text)
    VALUES
    (
      900913, 'spatialreference.org', 900913,
      'PROJCS["Popular Visualisation CRS / Mercator",GEOGCS["Popular Visualisation CRS",DATUM["Popular_Visualisation_Datum",SPHEROID["Popular Visualisation Sphere",6378137,0,AUTHORITY["EPSG","7059"]],TOWGS84[0,0,0,0,0,0,0],AUTHORITY["EPSG","6055"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.01745329251994328,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4055"]],UNIT["metre",1,AUTHORITY["EPSG","9001"]],PROJECTION["Mercator_1SP"],PARAMETER["central_meridian",0],PARAMETER["scale_factor",1],PARAMETER["false_easting",0],PARAMETER["false_northing",0],AUTHORITY["EPSG","3785"],AXIS["X",EAST],AXIS["Y",NORTH]]',
      '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs +over'
    );
"""

from re import compile
from copy import copy as _copy
from binascii import unhexlify as _unhexlify

try:
    from json import JSONEncoder
except ImportError:
    from simplejson import JSONEncoder

try:
    from shapely.wkb import loads as _loadshape
    from shapely.geometry import Polygon
    from shapely.geos import TopologicalError
    from psycopg2 import connect as _connect
    from psycopg2.extras import RealDictCursor
except ImportError:
    # At least it should be possible to build the documentation.
    pass


from TileStache.Core import KnownUnknown
from TileStache.Geography import getProjectionByName

def row2feature(row, id_field, geometry_field):
    """ Convert a database row dict to a feature dict.
    """
    feature = {'type': 'Feature', 'properties': _copy(row)}

    geometry = feature['properties'].pop(geometry_field)
    feature['geometry'] = _loadshape(_unhexlify(geometry))
    feature['id'] = feature['properties'].pop(id_field)
    
    return feature

def _p2p(xy, projection):
    """ Convert a simple (x, y) coordinate to a (lon, lat) position.
    """
    loc = projection.projLocation(_Point(*xy))
    return loc.lon, loc.lat

class _InvisibleBike(Exception): pass

def shape2geometry(shape, projection, clip):
    """ Convert a Shapely geometry object to a GeoJSON-suitable geometry dict.
    """
    if clip:
        try:
            shape = shape.intersection(clip)
        except TopologicalError:
            raise _InvisibleBike("Clipping shape resulted in a topological error")
        
        if shape.is_empty:
            raise _InvisibleBike("Clipping shape resulted in a null geometry")
    
    geom = shape.__geo_interface__
    
    if geom['type'] == 'Point':
        geom['coordinates'] = _p2p(geom['coordinates'], projection)
    
    elif geom['type'] in ('MultiPoint', 'LineString'):
        geom['coordinates'] = [_p2p(c, projection)
                               for c in geom['coordinates']]
    
    elif geom['type'] in ('MultiLineString', 'Polygon'):
        geom['coordinates'] = [[_p2p(c, projection)
                                for c in cs]
                               for cs in geom['coordinates']]
    
    elif geom['type'] == 'MultiPolygon':
        geom['coordinates'] = [[[_p2p(c, projection)
                                 for c in cs]
                                for cs in ccs]
                               for ccs in geom['coordinates']]
    
    return geom

class _Point:
    """ Local duck for (x, y) points.
    """
    def __init__(self, x, y):
        self.x = x
        self.y = y

class SaveableResponse:
    """ Wrapper class for JSON response that makes it behave like a PIL.Image object.
    
        TileStache.getTile() expects to be able to save one of these to a buffer.
    """
    def __init__(self, content, indent=2, precision=2):
        self.content = content
        self.indent = indent
        self.precision = precision

    def save(self, out, format):
        if format != 'JSON':
            raise KnownUnknown('PostGeoJSON only saves .json tiles, not "%s"' % format)

        indent = None
        
        if int(self.indent) > 0:
            indent = self.indent
        
        encoded = JSONEncoder(indent=indent).iterencode(self.content)
        float_pat = compile(r'^-?\d+\.\d+$')

        precision = 6

        if int(self.precision) > 0:
            precision = self.precision

        format = '%.' + str(precision) +  'f'

        for atom in encoded:
            if float_pat.match(atom):
                out.write(format % float(atom))
            else:
                out.write(atom)

class Provider:
    """
    """
    def __init__(self, layer, dsn, query, clipping=False, id_column='id', geometry_column='geometry', indent=2, precision=6):
        self.layer = layer
        self.dbdsn = dsn
        self.query = query
        self.mercator = getProjectionByName('spherical mercator')
        self.geometry_field = geometry_column
        self.id_field = id_column
        self.indent = indent
        self.precision = precision
        self.clipping = clipping

    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.
        
            This only accepts "json".
        """
        if extension.lower() != 'json':
            raise KnownUnknown('PostGeoJSON only makes .json tiles, not "%s"' % extension)
    
        return 'application/json', 'JSON'

    def renderTile(self, width, height, srs, coord):
        """ Render a single tile, return a SaveableResponse instance.
        """
        nw = self.layer.projection.coordinateLocation(coord)
        se = self.layer.projection.coordinateLocation(coord.right().down())

        ul = self.mercator.locationProj(nw)
        lr = self.mercator.locationProj(se)
        
        bbox = 'ST_SetSRID(ST_MakeBox2D(ST_MakePoint(%.6f, %.6f), ST_MakePoint(%.6f, %.6f)), 900913)' % (ul.x, ul.y, lr.x, lr.y)
        clip = self.clipping and Polygon([(ul.x, ul.y), (lr.x, ul.y), (lr.x, lr.y), (ul.x, lr.y)]) or None

        db = _connect(self.dbdsn).cursor(cursor_factory=RealDictCursor)

        db.execute(self.query.replace('!bbox!', bbox))
        rows = db.fetchall()
        
        db.close()
        
        response = {'type': 'FeatureCollection', 'features': []}
        
        for row in rows:
            feature = row2feature(row, self.id_field, self.geometry_field)
            
            try:
                geom = shape2geometry(feature['geometry'], self.mercator, clip)
            except _InvisibleBike:
                # don't output this geometry because it's empty
                pass
            else:
                feature['geometry'] = geom
                response['features'].append(feature)
    
        return SaveableResponse(response, self.indent, self.precision)
