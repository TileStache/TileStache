""" Provider that returns GeoJSON data responses from PostGIS queries.

This is an example of a provider that does not return an image, but rather
queries a database for raw data and replies with a string of GeoJSON. For
example, it's possible to retrieve data for locations of OpenStreetMap points
of interest based on a query with a bounding box intersection.

Read more about the GeoJSON spec at: http://geojson.org/geojson-spec.html

Caveats:

Currently only databases in the 900913 (google) projection are usable, though
this is the default setting for imports from osm2pgsql. The "!bbox!" query
placeholder (see example below) must be lowercase, and expands to:
    
    ST_SetSRID(ST_MakeBox2D(ST_MakePoint(ulx, uly), ST_MakePoint(lrx, lry)), 900913)
    
You must support the "900913" SRID in your PostGIS database for now. I'll make
this more flexible if this provider proves useful.

Example TileStache provider configuration:

"pois":
{
    "provider": {"class": "TileStache.Goodies.Providers.PostGeoJSON.Provider",
                 "kwargs": {
                    "dsn": "dbname=geodata user=postgres",
                    "query": "SELECT osm_id, name, way FROM planet_osm_point WHERE way && !bbox! AND name IS NOT NULL",
                    "id_column": "osm_id", "geometry_column": "way",
                    "indent": 2
                 }}
}
"""

from re import compile
from json import JSONEncoder
from copy import copy as _copy
from binascii import unhexlify as _unhexlify

from shapely.wkb import loads as _loadshape
from psycopg2 import connect as _connect
from psycopg2.extras import RealDictCursor
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

def shape2geometry(shape, projection):
    """ Convert a Shapely geometry object to a GeoJSON-suitable geometry dict.
    """
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
    def __init__(self, layer, dsn, query, id_column='id', geometry_column='geometry', indent=2, precision=6):
        self.layer = layer
        self.dbdsn = dsn
        self.query = query
        self.mercator = getProjectionByName('spherical mercator')
        self.geometry_field = geometry_column
        self.id_field = id_column
        self.indent = indent
        self.precision = precision

    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.
        
            This only accepts "json".
        """
        if extension.lower() != 'json':
            raise KnownUnknown('PostGeoJSON only makes .json tiles, not "%s"' % extension)
    
        return 'text/json', 'JSON'

    def renderTile(self, width, height, srs, coord):
        """ Render a single tile, return a SaveableResponse instance.
        """
        nw = self.layer.projection.coordinateLocation(coord)
        se = self.layer.projection.coordinateLocation(coord.right().down())

        ul = self.mercator.locationProj(nw)
        lr = self.mercator.locationProj(se)
        
        bbox = 'ST_SetSRID(ST_MakeBox2D(ST_MakePoint(%.6f, %.6f), ST_MakePoint(%.6f, %.6f)), 900913)' % (ul.x, ul.y, lr.x, lr.y)

        db = _connect(self.dbdsn).cursor(cursor_factory=RealDictCursor)

        db.execute(self.query.replace('!bbox!', bbox))
        rows = db.fetchall()
        
        db.close()
        
        response = {'type': 'FeatureCollection', 'features': []}
        
        for row in rows:
            feature = row2feature(row, self.id_field, self.geometry_field)
            feature['geometry'] = shape2geometry(feature['geometry'], self.mercator)
            response['features'].append(feature)
    
        return SaveableResponse(response, self.indent, self.precision)
