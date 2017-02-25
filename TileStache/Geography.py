""" The geography bits of TileStache.

A Projection defines the relationship between the rendered tiles and the
underlying geographic data. Generally, just one popular projection is used
for most web maps, "spherical mercator".

Built-in projections:
- spherical mercator
- WGS84

Example use projection in a layer definition:

    "layer-name": {
        "projection": "spherical mercator",
        ...
    }

You can define your own projection, with a module and object name as arguments:

    "layer-name": {
        ...
        "projection": "Module:Object"
    }

The object must include methods that convert between coordinates, points, and
locations. See the included mercator and WGS84 implementations for example.
You can also instantiate a projection class using this syntax:

    "layer-name": {
        ...
        "projection": "Module:Object()"
    }
"""

from ModestMaps.Core import Point, Coordinate
from ModestMaps.Geo import deriveTransformation, MercatorProjection, LinearProjection, Location
from math import log as _log, pi as _pi

from . import Core

class SphericalMercator(MercatorProjection):
    """ Spherical mercator projection for most commonly-used web map tile scheme.
    
        This projection is identified by the name "spherical mercator" in the
        TileStache config. The simplified projection used here is described in
        greater detail at: http://trac.openlayers.org/wiki/SphericalMercator
    """
    srs = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs +over'
    
    def __init__(self):
        pi = _pi

        # Transform from raw mercator projection to tile coordinates
        t = deriveTransformation(-pi, pi, 0, 0, pi, pi, 1, 0, -pi, -pi, 0, 1)

        MercatorProjection.__init__(self, 0, t)

    def coordinateProj(self, coord):
        """ Convert from Coordinate object to a Point object in EPSG:900913
        """
        # the zoom at which we're dealing with meters on the ground
        diameter = 2 * _pi * 6378137
        zoom = _log(diameter) / _log(2)
        coord = coord.zoomTo(zoom)
        
        # global offsets
        point = Point(coord.column, coord.row)
        point.x = point.x - diameter/2
        point.y = diameter/2 - point.y

        return point

    def projCoordinate(self, point):
        """ Convert from Point object in EPSG:900913 to a Coordinate object
        """
        # the zoom at which we're dealing with meters on the ground
        diameter = 2 * _pi * 6378137
        zoom = _log(diameter) / _log(2)

        # global offsets
        coord = Coordinate(point.y, point.x, zoom)
        coord.column = coord.column + diameter/2
        coord.row = diameter/2 - coord.row
        
        return coord

    def locationProj(self, location):
        """ Convert from Location object to a Point object in EPSG:900913
        """
        return self.coordinateProj(self.locationCoordinate(location))

    def projLocation(self, point):
        """ Convert from Point object in EPSG:900913 to a Location object
        """
        return self.coordinateLocation(self.projCoordinate(point))

class WGS84(LinearProjection):
    """ Unprojected projection for the other commonly-used web map tile scheme.
    
        This projection is identified by the name "WGS84" in the TileStache config.
    """
    srs = '+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs'
    
    def __init__(self):
        p = _pi

        # Transform from geography in radians to tile coordinates
        t = deriveTransformation(-p, p/2, 0, 0, p, p/2, 2, 0, -p, -p/2, 0, 1)

        LinearProjection.__init__(self, 0, t)

    def coordinateProj(self, coord):
        """ Convert from Coordinate object to a Point object in EPSG:4326
        """
        return self.locationProj(self.coordinateLocation(coord))

    def projCoordinate(self, point):
        """ Convert from Point object in EPSG:4326 to a Coordinate object
        """
        return self.locationCoordinate(self.projLocation(point))

    def locationProj(self, location):
        """ Convert from Location object to a Point object in EPSG:4326
        """
        return Point(location.lon, location.lat)

    def projLocation(self, point):
        """ Convert from Point object in EPSG:4326 to a Location object
        """
        return Location(point.y, point.x)

def getProjectionByName(name):
    """ Retrieve a projection object by name.
    
        Raise an exception if the name doesn't work out.
    """
    if name.lower() == 'spherical mercator':
        return SphericalMercator()
        
    elif name.lower() == 'wgs84':
        return WGS84()
        
    else:
        try:
            return Core.loadClassPath(name)
        except Exception as e:
            raise Core.KnownUnknown('Failed projection in configuration: "%s" - %s' % (name, e))
