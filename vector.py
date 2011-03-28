import json

from osgeo import ogr, osr

from ModestMaps.Core import Coordinate
from TileStache.Core import KnownUnknown
from TileStache.Geography import getProjectionByName

def tile_perimeter(coord, projection):
    """
    """
    ul = projection.coordinateProj(coord)
    lr = projection.coordinateProj(coord.right().down())
    
    xmin, ymin, xmax, ymax = ul.x, ul.y, lr.x, lr.y
    xspan, yspan = xmax - xmin, ymax - ymin
    
    perimeter = [
        (xmin, ymin),
        (xmin + 1 * xspan/4, ymin),
        (xmin + 2 * xspan/4, ymin),
        (xmin + 3 * xspan/4, ymin),
        (xmax, ymin),
        (xmax, ymin + 1 * yspan/4),
        (xmax, ymin + 2 * yspan/4),
        (xmax, ymin + 3 * yspan/4),
        (xmax, ymax),
        (xmax - 1 * xspan/4, ymax),
        (xmax - 2 * xspan/4, ymax),
        (xmax - 3 * xspan/4, ymax),
        (xmin, ymax),
        (xmin, ymax - 1 * yspan/4),
        (xmin, ymax - 2 * yspan/4),
        (xmin, ymax - 3 * yspan/4),
        (xmin, ymin)
      ]
    
    return perimeter

def tile_perimeter_geom(coord, projection):
    """
    """
    perimeter = tile_perimeter(coord, projection)
    wkt = 'POLYGON((%s))' % ', '.join(['%.3f %.3f' % xy for xy in perimeter])
    geom = ogr.CreateGeometryFromWkt(wkt)
    
    ref = osr.SpatialReference()
    ref.ImportFromProj4(projection.srs)
    geom.AssignSpatialReference(ref)
    
    return geom

def feature_properties(feature, layer_definition):
    """
    
        OFTInteger: 0, OFTIntegerList: 1, OFTReal: 2, OFTRealList: 3,
        OFTString: 4, OFTStringList: 5, OFTWideString: 6, OFTWideStringList: 7,
        OFTBinary: 8, OFTDate: 9, OFTTime: 10, OFTDateTime: 11
    """
    properties = {}
    okay_types = ogr.OFTInteger, ogr.OFTReal, ogr.OFTString, ogr.OFTWideString
    
    for index in range(layer_definition.GetFieldCount()):
        field_definition = layer_definition.GetFieldDefn(index)
        field_type = field_definition.GetType()
        
        if field_type not in okay_types:
            try:
                name = [oft for oft in dir(ogr) if oft.startswith('OFT') and getattr(ogr, oft) == field_type][0]
            except IndexError:
                raise KnownUnknown("Found an OGR field type I've never even seen: %d" % field_type)
            else:
                raise KnownUnknown("Found an OGR field type I don't know what to do with: ogr.%s" % name)

        name = field_definition.GetNameRef()
        properties[name] = feature.GetField(name)
    
    return properties

def open_layer(driver_name, **kwargs):
    """
    """
    #
    # Set up the driver
    #
    if driver_name not in ('Postgresql', 'ESRI Shapefile'):
        raise KnownUnkown("Got a driver type I don't understand: %s" % driver_name)

    driver = ogr.GetDriverByName(driver_name)
    
    #
    # Set up the datasource
    #
    if driver_name == 'Postgresql':
        if 'dbname' not in kwargs:
            raise KnownUnknown('Need at least a "dbname" parameter for postgis')
    
        conn_parts = []
        
        for part in ('dbname', 'user', 'host', 'password'):
            if part in kwargs:
                conn_parts.append("%s='%s'" % (part, kwargs[part]))
        
        datasource = driver.Open('PG:' + ' '.join(conn_parts))
        
    elif driver_name == 'ESRI Shapefile':
        if 'file' not in kwargs:
            raise KnownUnknown('Need at least a "file" parameter for a shapefile')
    
        datasource = driver.Open(kwargs['file'])

    #
    # Set up the layer
    #
    if driver_name == 'Postgresql':
        if 'query' in kwargs:
            layer = datasource.ExecuteSQL(kwargs['query'])
        elif 'table' in kwargs:
            layer = datasource.GetLayerByName(kwargs['table'])
        else:
            raise KnownUnknown('Need at least a "query" or "table" parameter for postgis')

    else:
        layer = datasource.GetLayer(0)

    layer_sref = layer.GetSpatialRef()
    assert layer_sref is not None

    #
    # Return the layer and the datasource.
    #
    # Technically, the datasource is no longer needed
    # but layer segfaults when it falls out of scope.
    #
    return layer, datasource

def get_layer_postgis_points():
    return open_layer('Postgresql', dbname='geodata', user='geodata', table='planet_osm_point')

def get_layer_postgis_lines():
    return open_layer('Postgresql', dbname='geodata', user='geodata', table='planet_osm_line')

def get_layer_postgis_polygons():
    return open_layer('Postgresql', dbname='geodata', user='geodata', table='planet_osm_polygon')

def get_layer_shapefile_points():
    return open_layer('ESRI Shapefile', file='oakland-uptown-point.shp')

def get_layer_shapefile_lines():
    return open_layer('ESRI Shapefile', file='oakland-uptown-line.shp')

def get_layer_query_lines():
    return open_layer('Postgresql', dbname='geodata', user='geodata', query="SELECT osm_id, name, highway, way FROM planet_osm_line WHERE SUBSTR(name, 1, 1) = '1'")

def get_stuff(projection, coord, get_layer):
    """
    """
    #
    # Prepare output spatial reference - always WGS84.
    #
    output_sref = osr.SpatialReference()
    output_proj = getProjectionByName('WGS84')
    output_sref.ImportFromProj4(output_proj.srs)
    
    #
    # Load layer information
    #
    layer, datasource = get_layer()
    definition = layer.GetLayerDefn()
    layer_sref = layer.GetSpatialRef()
    
    #
    # Spatially filter the layer
    #
    bbox = tile_perimeter_geom(coord, projection)
    bbox.TransformTo(layer_sref)
    layer.SetSpatialFilter(bbox)
    
    print '-' * 80
    
    for feature in layer:
        geometry = feature.geometry().Clone()
        
        if not geometry.Intersect(bbox):
            continue
        
        geometry = geometry.Intersection(bbox)
        
        if geometry is None:
            # may indicate a TopologyException
            continue
        
        geometry.AssignSpatialReference(layer_sref)
        geometry.TransformTo(output_sref)

        geom = json.loads(geometry.ExportToJson())
        prop = feature_properties(feature, definition)
        
        print {'type': 'Feature', 'properties': prop, 'geometry': geom}

projection = getProjectionByName('spherical mercator')
coord = Coordinate(50648, 21021, 17)

get_stuff(projection, coord, get_layer_postgis_points)
get_stuff(projection, coord, get_layer_postgis_lines)
get_stuff(projection, coord, get_layer_postgis_polygons)
get_stuff(projection, coord, get_layer_shapefile_points)
get_stuff(projection, coord, get_layer_shapefile_lines)
get_stuff(projection, coord, get_layer_query_lines)

#layer.SetSpatialFilterRect(xmin, ymin, xmax, ymax)
