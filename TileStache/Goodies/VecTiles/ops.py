''' Per-coordinate transformation function for shapely geometries.

To be replaced with shapely.ops.transform in Shapely 1.2.18.

See also:
    https://github.com/Toblerity/Shapely/issues/46

>>> from shapely.geometry import *

>>> coll0 = GeometryCollection()
>>> coll1 = transform(coll0, lambda (x, y): (x+1, y+1))
>>> print coll1                                                                 # doctest: +ELLIPSIS
GEOMETRYCOLLECTION EMPTY

>>> point0 = Point(0, 0)
>>> point1 = transform(point0, lambda (x, y): (x+1, y+1))
>>> print point1                                                                # doctest: +ELLIPSIS
POINT (1.00... 1.00...)

>>> mpoint0 = MultiPoint(((0, 0), (1, 1), (2, 2)))
>>> mpoint1 = transform(mpoint0, lambda (x, y): (x+1, y+1))
>>> print mpoint1                                                               # doctest: +ELLIPSIS
MULTIPOINT (1.00... 1.00..., 2.00... 2.00..., 3.00... 3.00...)

>>> line0 = LineString(((0, 0), (1, 1), (2, 2)))
>>> line1 = transform(line0, lambda (x, y): (x+1, y+1))
>>> print line1                                                                 # doctest: +ELLIPSIS
LINESTRING (1.00... 1.00..., 2.00... 2.00..., 3.00... 3.00...)

>>> mline0 = MultiLineString((((0, 0), (1, 1), (2, 2)), ((3, 3), (4, 4), (5, 5))))
>>> mline1 = transform(mline0, lambda (x, y): (x+1, y+1))
>>> print mline1                                                                # doctest: +ELLIPSIS
MULTILINESTRING ((1.00... 1.00..., 2.00... 2.00..., 3.00... 3.00...), (4.00... 4.00..., 5.00... 5.00..., 6.00... 6.00...))

>>> poly0 = Polygon(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)))
>>> poly1 = transform(poly0, lambda (x, y): (x+1, y+1))
>>> print poly1                                                                 # doctest: +ELLIPSIS
POLYGON ((1.00... 1.00..., 2.00... 1.00..., 2.00... 2.00..., 1.00... 2.00..., 1.00... 1.00...))

>>> poly0 = Polygon(((0, 0), (3, 0), (3, 3), (0, 3), (0, 0)), [((1, 1), (2, 1), (2, 2), (1, 2), (1, 1))])
>>> poly1 = transform(poly0, lambda (x, y): (x+1, y+1))
>>> print poly1                                                                 # doctest: +ELLIPSIS
POLYGON ((1.00... 1.00..., 4.00... 1.00..., 4.00... 4.00..., 1.00... 4.00..., 1.00... 1.00...), (2.00... 2.00..., 3.00... 2.00..., 3.00... 3.00..., 2.00... 3.00..., 2.00... 2.00...))

>>> mpoly0 = MultiPolygon(((((0, 0), (3, 0), (3, 3), (0, 3), (0, 0)), [((1, 1), (2, 1), (2, 2), (1, 2), (1, 1))]), (((10, 10), (13, 10), (13, 13), (10, 13), (10, 10)), [((11, 11), (12, 11), (12, 12), (11, 12), (11, 11))])))
>>> mpoly1 = transform(mpoly0, lambda (x, y): (x+1, y+1))
>>> print mpoly1                                                                # doctest: +ELLIPSIS
MULTIPOLYGON (((1.00... 1.00..., 4.00... 1.00..., 4.00... 4.00..., 1.00... 4.00..., 1.00... 1.00...), (2.00... 2.00..., 3.00... 2.00..., 3.00... 3.00..., 2.00... 3.00..., 2.00... 2.00...)), ((11.00... 11.00..., 14.00... 11.00..., 14.00... 14.00..., 11.00... 14.00..., 11.00... 11.00...), (12.00... 12.00..., 13.00... 12.00..., 13.00... 13.00..., 12.00... 13.00..., 12.00... 12.00...)))
'''

def transform(shape, func):
    ''' Apply a function to every coordinate in a geometry.
    '''
    construct = shape.__class__
    
    if shape.type.startswith('Multi'):
        parts = [transform(geom, func) for geom in shape.geoms]
        return construct(parts)
    
    if shape.type in ('Point', 'LineString'):
        return construct(map(func, shape.coords))
        
    if shape.type == 'Polygon':
        exterior = map(func, shape.exterior.coords)
        rings = [map(func, ring.coords) for ring in shape.interiors]
        return construct(exterior, rings)
    
    if shape.type == 'GeometryCollection':
        return construct()
    
    raise ValueError('Unknown geometry type, "%s"' % shape.type)

if __name__ == '__main__':
    from doctest import testmod
    testmod()
