from pyproj import Proj, transform
from osgeo import ogr, osr

src = ogr.Open('null/null.shp')

print '-' * 80
print src
print src.GetLayerCount()

lyr = src.GetLayer(0)
srs = lyr.GetSpatialRef()
dfn = lyr.GetLayerDefn()

print '-' * 80
print lyr
print srs
print dfn

gtp = dfn.GetGeomType()

print '-' * 80
print gtp
print srs.ExportToProj4()

print '-' * 80

lyr.SetSpatialFilterRect(0, -100, 200, 100)

def mangle_linestring(line):
    """
    """
    assert line.GetGeometryType() == ogr.wkbLineString

    for p in range(line.GetPointCount()):
        line.SetPoint_2D(p, 13, 37)

def mangle_polygon(polygon):
    """
    """
    assert polygon.GetGeometryType() == ogr.wkbPolygon
    
    for r in range(polygon.GetGeometryCount()):
        line = polygon.GetGeometryRef(r)
        mangle_linestring(line)

def mangle_feature(feature):
    """
    """
    geom = feature.geometry()
    type = geom.GetGeometryType()
    
    if type == ogr.wkbMultiPolygon:
        for g in range(geo.GetGeometryCount()):
            poly = geom.GetGeometryRef(g)
            mangle_polygon(poly)
    
    else:
        names = [name for name in dir(ogr)
                 if getattr(ogr, name) == geom.GetGeometryType()
                    and name.startswith('wkb')]

        raise RuntimeError("Don\'t know what to do with %s yet." % names[0])

for ftr in lyr:
    geo = ftr.geometry()
    print ', '.join(dir(geo))
    print geo.GetGeometryCount(),
    print geo.GetGeometryType(),
    print [name for name in dir(ogr) if getattr(ogr, name) == geo.GetGeometryType()]
    
    for index in range(geo.GetGeometryCount()):
        print index,
        print geo.GetGeometryRef(index).GetGeometryCount(),
        print geo.GetGeometryRef(index).GetGeometryType(),
        print [name for name in dir(ogr) if getattr(ogr, name) == geo.GetGeometryRef(index).GetGeometryType()],
        print geo.GetGeometryRef(index).GetGeometryRef(0).GetPoint(0)
    
    print '-' * 20
    print mangle_feature(ftr)
    
    print ftr.geometry()
    print dir(ftr.geometry())
