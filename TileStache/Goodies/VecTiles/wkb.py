''' Shapeless handling of WKB geometries.

Use approximate_wkb() to copy an approximate well-known binary representation of
a geometry. Along the way, reduce precision of double floating point coordinates
by replacing their three least-significant bytes with nulls. The resulting WKB
will match the original at up to 26 bits of precision, close enough for
spherical mercator zoom 18 street scale geography.

Reduced-precision WKB geometries will compress as much as 50% smaller with zlib.

See also:
    http://edndoc.esri.com/arcsde/9.0/general_topics/wkb_representation.htm
    http://en.wikipedia.org/wiki/Double-precision_floating-point_format
'''

from struct import unpack
try:
    from io import StringIO
except ImportError:
    # Python 2
    from StringIO import StringIO

#
# wkbByteOrder
#
wkbXDR = 0 # Big Endian
wkbNDR = 1 # Little Endian

#
# wkbGeometryType
#
wkbPoint = 1
wkbLineString = 2
wkbPolygon = 3
wkbMultiPoint = 4
wkbMultiLineString = 5
wkbMultiPolygon = 6
wkbGeometryCollection = 7

wkbMultis = wkbMultiPoint, wkbMultiLineString, wkbMultiPolygon, wkbGeometryCollection

def copy_byte(src, dest):
    ''' Copy an unsigned byte between files, and return it.
    '''
    byte = src.read(1)
    dest.write(byte)

    (val, ) = unpack('B', byte)
    return val

def copy_int_little(src, dest):
    ''' Copy a little-endian unsigned 4-byte int between files, and return it.
    '''
    word = src.read(4)
    dest.write(word)
    
    (val, ) = unpack('<I', word)
    return val

def copy_int_big(src, dest):
    ''' Copy a big-endian unsigned 4-byte int between files, and return it.
    '''
    word = src.read(4)
    dest.write(word)
    
    (val, ) = unpack('>I', word)
    return val

def approx_point_little(src, dest):
    ''' Copy a pair of little-endian doubles between files, truncating significands.
    '''
    xy = src.read(2 * 8)
    dest.write('\x00\x00\x00')
    dest.write(xy[-13:-8])
    dest.write('\x00\x00\x00')
    dest.write(xy[-5:])

def approx_point_big(src, dest):
    ''' Copy a pair of big-endian doubles between files, truncating significands.
    '''
    xy = src.read(2 * 8)
    dest.write(xy[:5])
    dest.write('\x00\x00\x00')
    dest.write(xy[8:13])
    dest.write('\x00\x00\x00')

def approx_line(src, dest, copy_int, approx_point):
    '''
    '''
    points = copy_int(src, dest)
    
    for i in range(points):
        approx_point(src, dest)

def approx_polygon(src, dest, copy_int, approx_point):
    '''
    '''
    rings = copy_int(src, dest)
    
    for i in range(rings):
        approx_line(src, dest, copy_int, approx_point)

def approx_geometry(src, dest):
    '''
    '''
    end = copy_byte(src, dest)
    
    if end == wkbNDR:
        copy_int = copy_int_little
        approx_point = approx_point_little
    
    elif end == wkbXDR:
        copy_int = copy_int_big
        approx_point = approx_point_big
    
    else:
        raise ValueError(end)
    
    type = copy_int(src, dest)
    
    if type == wkbPoint:
        approx_point(src, dest)
            
    elif type == wkbLineString:
        approx_line(src, dest, copy_int, approx_point)
            
    elif type == wkbPolygon:
        approx_polygon(src, dest, copy_int, approx_point)
            
    elif type in wkbMultis:
        parts = copy_int(src, dest)
        
        for i in range(parts):
            approx_geometry(src, dest)
            
    else:
        raise ValueError(type)

def approximate_wkb(wkb_in):
    ''' Return an approximation of the input WKB with lower-precision geometry.
    '''
    input, output = StringIO(wkb_in), StringIO()
    approx_geometry(input, output)
    wkb_out = output.getvalue()

    assert len(wkb_in) == input.tell(), 'The whole WKB was not processed'
    assert len(wkb_in) == len(wkb_out), 'The output WKB is the wrong length'
    
    return wkb_out

if __name__ == '__main__':

    from random import random
    from math import hypot

    from shapely.wkb import loads
    from shapely.geometry import *
    
    point1 = Point(random(), random())
    point2 = loads(approximate_wkb(point1.wkb))
    
    assert hypot(point1.x - point2.x, point1.y - point2.y) < 1e-8
    
    
    
    point1 = Point(random(), random())
    point2 = Point(random(), random())
    point3 = point1.union(point2)
    point4 = loads(approximate_wkb(point3.wkb))
    
    assert hypot(point3.geoms[0].x - point4.geoms[0].x, point3.geoms[0].y - point4.geoms[0].y) < 1e-8
    assert hypot(point3.geoms[1].x - point4.geoms[1].x, point3.geoms[1].y - point4.geoms[1].y) < 1e-8
    
    
    
    line1 = Point(random(), random()).buffer(1 + random(), 3).exterior
    line2 = loads(approximate_wkb(line1.wkb))
    
    assert abs(1. - line2.length / line1.length) < 1e-8
    
    
    
    line1 = Point(random(), random()).buffer(1 + random(), 3).exterior
    line2 = Point(random(), random()).buffer(1 + random(), 3).exterior
    line3 = MultiLineString([line1, line2])
    line4 = loads(approximate_wkb(line3.wkb))
    
    assert abs(1. - line4.length / line3.length) < 1e-8
    
    
    
    poly1 = Point(random(), random()).buffer(1 + random(), 3)
    poly2 = loads(approximate_wkb(poly1.wkb))
    
    assert abs(1. - poly2.area / poly1.area) < 1e-8
    
    
    
    poly1 = Point(random(), random()).buffer(2 + random(), 3)
    poly2 = Point(random(), random()).buffer(1 + random(), 3)
    poly3 = poly1.difference(poly2)
    poly4 = loads(approximate_wkb(poly3.wkb))
    
    assert abs(1. - poly4.area / poly3.area) < 1e-8
    
    
    
    poly1 = Point(random(), 2 + random()).buffer(1 + random(), 3)
    poly2 = Point(2 + random(), random()).buffer(1 + random(), 3)
    poly3 = poly1.union(poly2)
    poly4 = loads(approximate_wkb(poly3.wkb))
    
    assert abs(1. - poly4.area / poly3.area) < 1e-8
