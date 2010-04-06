""" The geography bits of TileStache.

A Projection defines the relationship between the rendered tiles and the
underlying geographic data. Generally, just one popular projection is used
for most web maps, "spherical mercator".

Built-in projections:
- spherical mercator

Example use projection in a layer definition:

    "layer-name": {
        "projection": "spherical mercator",
        ...
    }

"""

from ModestMaps.Core import Point
from ModestMaps.Geo import Transformation, MercatorProjection
from math import log as _log, pi as _pi

class SphericalMercator(MercatorProjection):
    """ Spherical mercator projection for most commonly-used web map tile scheme.
    
        This projection is identified by the name "spherical mercator" in the
        TileStache config. The simplified projection used here is described in
        greater detail at: http://trac.openlayers.org/wiki/SphericalMercator
    """
    srs = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0' \
        + ' +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +no_defs'
    
    def __init__(self):
        # these numbers are slightly magic.
        t = Transformation(1.068070779e7, 0, 3.355443185e7,
		                   0, -1.068070890e7, 3.355443057e7)

        MercatorProjection.__init__(self, 26, t)

    def coordinateProj(self, coord):
        """ Convert from Coordinate object to a Point object in EPSG:900913
        """
        # the zoom at which we're dealing with meters on the ground
        diameter = 2 * _pi * 6378137
        zoom = _log(diameter) / _log(2)
        coord = coord.zoomTo(zoom)
        
        # global offsets
        coord.column -= diameter/2
        coord.row = diameter/2 - coord.row

        return Point(coord.column, coord.row)

    def locationProj(self, location):
        """ Convert from Location object to a Point object in EPSG:900913
        """
        return self.coordinateProj(self.locationCoordinate(location))

def getProjectionByName(name):
    """ Retrieve a projection object by name.
    
        Raise an exception if the name doesn't work out.
    """
    if name == 'spherical mercator':
        return SphericalMercator()
        
    else:
        raise Exception('Unknown projection: "%s"' % name)
