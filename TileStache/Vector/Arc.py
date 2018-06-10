""" Arc-specific Vector provider helpers.
"""
from operator import add

from ..Core import KnownUnknown

from ..py3_compat import reduce

geometry_types = {
    'Point': 'esriGeometryPoint',
    'LineString': 'esriGeometryPolyline',
    'Polygon': 'esriGeometryPolygon',
    'MultiPoint': 'esriGeometryMultipoint',
    'MultiLineString': 'esriGeometryPolyline',
    'MultiPolygon': 'esriGeometryPolygon'
  }

class _amfFeatureSet(dict):
    """ Registered PyAMF class for com.esri.ags.tasks.FeatureSet

        http://help.arcgis.com/en/webapi/flex/apiref/com/esri/ags/FeatureSet.html
    """
    def __init__(self, spatial_reference, geometry_type, features):
        self.spatialReference = spatial_reference
        self.geometryType = geometry_type
        self.features = features
        dict.__init__(self, {'geometryType': geometry_type,
                             'spatialReference': spatial_reference,
                             'features': features})

class _amfSpatialReference(dict):
    """ Registered PyAMF class for com.esri.ags.SpatialReference

        http://help.arcgis.com/en/webapi/flex/apiref/com/esri/ags/SpatialReference.html
    """
    def __init__(self, wkid, wkt):
        if wkid:
            self.wkid = wkid
            dict.__init__(self, {'wkid': wkid})
        elif wkt:
            self.wkt = wkt
            dict.__init__(self, {'wkt': wkt})

class _amfFeature(dict):
    """ Registered PyAMF class for com.esri.ags.Feature

        No URL for class information - this class shows up in AMF responses
        from ESRI webservices but does not seem to be otherwise documented.
    """
    def __init__(self, attributes, geometry):
        self.attributes = attributes
        self.geometry = geometry
        dict.__init__(self, {'attributes': attributes, 'geometry': geometry})

class _amfGeometryMapPoint(dict):
    """ Registered PyAMF class for com.esri.ags.geometry.MapPoint

        http://help.arcgis.com/en/webapi/flex/apiref/com/esri/ags/geometry/MapPoint.html
    """
    def __init__(self, sref, x, y):
        self.x = x
        self.y = y
        self.spatialReference = sref
        dict.__init__(self, {'spatialReference': sref, 'x': x, 'y': y})

class _amfGeometryPolyline(dict):
    """ Registered PyAMF class for com.esri.ags.geometry.Polyline

        http://help.arcgis.com/en/webapi/flex/apiref/com/esri/ags/geometry/Polyline.html
    """
    def __init__(self, sref, paths):
        self.paths = paths
        self.spatialReference = sref
        dict.__init__(self, {'spatialReference': sref, 'paths': paths})

class _amfGeometryPolygon(dict):
    """ Registered PyAMF class for com.esri.ags.geometry.Polygon

        http://help.arcgis.com/en/webapi/flex/apiref/com/esri/ags/geometry/Polygon.html
    """
    def __init__(self, sref, rings):
        self.rings = rings
        self.spatialReference = sref
        dict.__init__(self, {'spatialReference': sref, 'rings': rings})

pyamf_classes = {
    _amfFeatureSet: 'com.esri.ags.tasks.FeatureSet',
    _amfSpatialReference: 'com.esri.ags.SpatialReference',
    _amfGeometryMapPoint: 'com.esri.ags.geometry.MapPoint',
    _amfGeometryPolyline: 'com.esri.ags.geometry.Polyline',
    _amfGeometryPolygon: 'com.esri.ags.geometry.Polygon',
    _amfFeature: 'com.esri.ags.Feature'
  }

def reserialize_to_arc(content, point_objects):
    """ Convert from "geo" (GeoJSON) to ESRI's GeoServices REST serialization.

        Second argument is a boolean flag for whether to use the class
        _amfGeometryMapPoint for points in ring and path arrays, or tuples.
        The formal class is needed for AMF responses, plain tuples otherwise.

        Much of this cribbed from sample server queries and page 191+ of:
          http://www.esri.com/library/whitepapers/pdfs/geoservices-rest-spec.pdf
    """
    mapPointList = point_objects and _amfGeometryMapPoint or (lambda s, x, y: (x, y))
    mapPointDict = point_objects and _amfGeometryMapPoint or (lambda s, x, y: {'x': x, 'y': y})

    found_geometry_types = set([feat['geometry']['type'] for feat in content['features']])
    found_geometry_types = set([geometry_types.get(type) for type in found_geometry_types])

    if len(found_geometry_types) > 1:
        raise KnownUnknown('Arc serialization needs a single geometry type, not ' + ', '.join(found_geometry_types))

    crs = content['crs']
    sref = _amfSpatialReference(crs.get('wkid', None), crs.get('wkt', None))
    geometry_type, features = None, []

    for feature in content['features']:
        geometry = feature['geometry']

        if geometry['type'] == 'Point':
            arc_geometry = mapPointDict(sref, *geometry['coordinates'])

        elif geometry['type'] == 'LineString':
            path = geometry['coordinates']
            paths = [[mapPointList(sref, *xy) for xy in path]]
            arc_geometry = _amfGeometryPolyline(sref, paths)

        elif geometry['type'] == 'Polygon':
            rings = geometry['coordinates']
            rings = [[mapPointList(sref, *xy) for xy in ring] for ring in rings]
            arc_geometry = _amfGeometryPolygon(sref, rings)

        elif geometry['type'] == 'MultiPoint':
            points = geometry['coordinates']
            points = [mapPointList(sref, *xy) for xy in points]
            arc_geometry = {'points': points}

        elif geometry['type'] == 'MultiLineString':
            paths = geometry['coordinates']
            paths = [[mapPointList(sref, *xy) for xy in path] for path in paths]
            arc_geometry = _amfGeometryPolyline(sref, paths)

        elif geometry['type'] == 'MultiPolygon':
            rings = reduce(add, geometry['coordinates'])
            rings = [[mapPointList(sref, *xy) for xy in ring] for ring in rings]
            arc_geometry = _amfGeometryPolygon(sref, rings)

        else:
            raise Exception(geometry['type'])

        arc_feature = _amfFeature(feature['properties'], arc_geometry)
        geometry_type = geometry_types[geometry['type']]
        features.append(arc_feature)

    return _amfFeatureSet(sref, geometry_type, features)
