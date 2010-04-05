""" Blah!
"""

import ModestMaps
from math import log, pi

class SphericalMercator(ModestMaps.Geo.MercatorProjection):
    """
    """
    srs = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0' \
        + ' +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +no_defs'
    
    def __init__(self):
        # these numbers are slightly magic.
        t = ModestMaps.Geo.Transformation(1.068070779e7, 0, 3.355443185e7,
		                                  0, -1.068070890e7, 3.355443057e7)

        ModestMaps.Geo.MercatorProjection.__init__(self, 26, t)

    def coordinateProj(self, coord):
        """ Convert from Coordinate object to a Point object in EPSG:900913
        """
        # the zoom at which we're dealing with meters on the ground
        diameter = 2 * pi * 6378137
        zoom = log(diameter) / log(2)
        coord = coord.zoomTo(zoom)
        
        # global offsets
        coord.column -= diameter/2
        coord.row = diameter/2 - coord.row

        return ModestMaps.Core.Point(coord.column, coord.row)

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
    
        # print 'fuck'
        # 
        # radius = 6378137
        # diameter = 2 * pi radius
        # 
        # point1 = -pi, pi, -diameter, diameter
        # print ModestMaps.Geo.deriveTransformation(a1x, a1y, a2x, a2y, b1x, b1y, b2x, b2y, c1x, c1y, c2x, c2y)
        
    else:
        raise Exception('Unknown projection: "%s"' % name)
