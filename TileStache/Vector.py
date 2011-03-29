from re import compile
from urlparse import urlparse, urljoin

try:
    from json import JSONEncoder, loads as json_loads
except ImportError:
    from simplejson import JSONEncoder, loads as json_loads

try:
    from osgeo import ogr, osr
except ImportError:
    # At least we'll be able to build the documentation.
    pass

from Core import KnownUnknown
from Geography import getProjectionByName

class VectorResponse:
    """ Wrapper class for Vector response that makes it behave like a PIL.Image object.
    
        TileStache.getTile() expects to be able to save one of these to a buffer.
    """
    def __init__(self, content, indent=2, precision=6):
        self.content = content
        self.indent = indent
        self.precision = precision

    def save(self, out, format):
        if format != 'GeoJSON':
            raise KnownUnknown('PostGeoJSON only saves .geojson tiles, not "%s"' % format)

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

def _tile_perimeter(coord, projection):
    """ Get a tile's outer edge for a coordinate and a projection.
    
        Returns a list of 17 (x, y) coordinates corresponding to a clockwise
        circumambulation of a tile boundary in a given projection. Projection
        is like those found in TileStache.Geography, used for tile output.
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

def _tile_perimeter_geom(coord, projection):
    """ Get an OGR Geometry object for a coordinate tile polygon.
    
        Uses _tile_perimeter().
    """
    perimeter = _tile_perimeter(coord, projection)
    wkt = 'POLYGON((%s))' % ', '.join(['%.3f %.3f' % xy for xy in perimeter])
    geom = ogr.CreateGeometryFromWkt(wkt)
    
    ref = osr.SpatialReference()
    ref.ImportFromProj4(projection.srs)
    geom.AssignSpatialReference(ref)
    
    return geom

def _feature_properties(feature, layer_definition, whitelist=None):
    """ Returns a dictionary of feature properties for a feature in a layer.
    
        Third argument is an optional list or dictionary of properties to
        whitelist by case-sensitive name - leave it None to include everything.
        A dictionary will cause property names to be re-mapped.
    
        OGR property types:
        OFTInteger (0), OFTIntegerList (1), OFTReal (2), OFTRealList (3),
        OFTString (4), OFTStringList (5), OFTWideString (6), OFTWideStringList (7),
        OFTBinary (8), OFTDate (9), OFTTime (10), OFTDateTime (11).
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
        
        if type(whitelist) in (list, dict) and name not in whitelist:
            continue
        
        property = type(whitelist) is dict and whitelist[name] or name
        properties[property] = feature.GetField(name)
    
    return properties

def _open_layer(driver_name, parameters, dirpath):
    """ Open a layer, return it and its datasource.
    
        Dirpath comes from configuration, and is used to locate files.
    """
    #
    # Set up the driver
    #
    okay_drivers = 'Postgresql', 'ESRI Shapefile', 'GeoJSON'
    
    if driver_name not in okay_drivers:
        raise KnownUnknown('Got a driver type Vector doesn\'t understand: "%s". Need one of %s.' % (driver_name, ', '.join(okay_drivers)))

    driver = ogr.GetDriverByName(str(driver_name))
    
    #
    # Set up the datasource
    #
    if driver_name == 'Postgresql':
        if 'dbname' not in parameters:
            raise KnownUnknown('Need at least a "dbname" parameter for postgis')
    
        conn_parts = []
        
        for part in ('dbname', 'user', 'host', 'password'):
            if part in parameters:
                conn_parts.append("%s='%s'" % (part, parameters[part]))
        
        source_name = 'PG:' + ' '.join(conn_parts)
        
    elif driver_name in ('ESRI Shapefile', 'GeoJSON'):
        if 'file' not in parameters:
            raise KnownUnknown('Need at least a "file" parameter for a shapefile')
    
        file_href = urljoin(dirpath, parameters['file'])
        scheme, h, file_path, q, p, f = urlparse(file_href)
        
        if scheme not in ('file', ''):
            raise KnownUnknown('Shapefiles need to be local, not %s' % file_href)
        
        source_name = file_path

    datasource = driver.Open(str(source_name))

    if datasource is None:
        raise KnownUnknown('Couldn\'t open datasource %s' % source_name)
    
    #
    # Set up the layer
    #
    if driver_name == 'Postgresql':
        if 'query' in parameters:
            layer = datasource.ExecuteSQL(str(parameters['query']))
        elif 'table' in parameters:
            layer = datasource.GetLayerByName(str(parameters['table']))
        else:
            raise KnownUnknown('Need at least a "query" or "table" parameter for postgis')

    else:
        layer = datasource.GetLayer(0)

    if layer.GetSpatialRef() is None: 
        raise KnownUnknown('Couldn\'t get a layer from data source %s' % source_name)

    #
    # Return the layer and the datasource.
    #
    # Technically, the datasource is no longer needed
    # but layer segfaults when it falls out of scope.
    #
    return layer, datasource

def _get_features(coord, properties, projection, layer, clip):
    """ Return a list of features in an OGR layer with properties in GeoJSON form.
    
        Optionally clip features to coordinate bounding box.
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
    definition = layer.GetLayerDefn()
    layer_sref = layer.GetSpatialRef()
    
    #
    # Spatially filter the layer
    #
    bbox = _tile_perimeter_geom(coord, projection)
    bbox.TransformTo(layer_sref)
    layer.SetSpatialFilter(bbox)
    
    features = []
    
    for feature in layer:
        geometry = feature.geometry().Clone()
        
        if not geometry.Intersect(bbox):
            continue
        
        if clip:
            geometry = geometry.Intersection(bbox)
        
        if geometry is None:
            # may indicate a TopologyException
            continue
        
        geometry.AssignSpatialReference(layer_sref)
        geometry.TransformTo(output_sref)

        geom = json_loads(geometry.ExportToJson())
        prop = _feature_properties(feature, definition, properties)
        
        features.append({'type': 'Feature', 'properties': prop, 'geometry': geom})
    
    return features

class Provider:
    """ Vector Provider for OGR datasources.
    """
    
    def __init__(self, layer, driver, parameters, clipped, verbose, properties):
        self.layer = layer
        self.driver = driver
        self.clipped = clipped
        self.verbose = verbose
        self.parameters = parameters
        self.properties = properties

    def renderTile(self, width, height, srs, coord):
        """ Render a single tile, return a SaveableResponse instance.
        """
        layer, ds = _open_layer(self.driver, self.parameters, self.layer.config.dirpath)
        features = _get_features(coord, self.properties, self.layer.projection, layer, self.clipped)
        response = {'type': 'FeatureCollection', 'features': features}

        return VectorResponse(response, self.verbose and 2 or 0)
        
    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.
        
            This only accepts "geojson".
        """
        if extension.lower() != 'geojson':
            raise KnownUnknown('Vector Provider only makes .geojson tiles, not "%s"' % extension)
    
        return 'text/json', 'GeoJSON'
