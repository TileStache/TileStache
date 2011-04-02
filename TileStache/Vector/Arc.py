""" Arc-specific Vector provider helpers.
"""
from operator import add

from TileStache.Core import KnownUnknown

geometry_types = {
    'Point': 'esriGeometryPoint',
    'LineString': 'esriGeometryPolyline',
    'Polygon': 'esriGeometryPolygon',
    'MultiPoint': 'esriGeometryMultipoint',
    'MultiLineString': 'esriGeometryPolyline',
    'MultiPolygon': 'esriGeometryPolygon'
  }

class amfFeatureSet(dict):
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

class amfSpatialReference(dict):
    """ Registered PyAMF class for com.esri.ags.SpatialReference
    
        http://help.arcgis.com/en/webapi/flex/apiref/com/esri/ags/SpatialReference.html
    """
    def __init__(self, wkid, wkt):
        self.wkid = wkid
        self.wkt = wkt
        dict.__init__(self, {'wkid': wkid, 'wkt': wkt})

class amfFeature(dict):
    """ Registered PyAMF class for com.esri.ags.Feature
    
        No URL for class information - this class shows up in AMF responses
        from ESRI webservices but does not seem to be otherwise documented.
    """
    def __init__(self, attributes, geometry):
        self.attributes = attributes
        self.geometry = geometry
        dict.__init__(self, {'attributes': attributes, 'geometry': geometry})

class amfGeometryMapPoint(dict):
    """ Registered PyAMF class for com.esri.ags.geometry.MapPoint
    
        http://help.arcgis.com/en/webapi/flex/apiref/com/esri/ags/geometry/MapPoint.html
    """
    def __init__(self, x, y):
        self.x = x
        self.y = y
        dict.__init__(self, {'x': x, 'y': y})

class amfGeometryPolyline(dict):
    """ Registered PyAMF class for com.esri.ags.geometry.Polyline
    
        http://help.arcgis.com/en/webapi/flex/apiref/com/esri/ags/geometry/Polyline.html
    """
    def __init__(self, paths):
        self.paths = paths
        dict.__init__(self, {'paths': paths})

class amfGeometryPolygon(dict):
    """ Registered PyAMF class for com.esri.ags.geometry.Polygon
    
        http://help.arcgis.com/en/webapi/flex/apiref/com/esri/ags/geometry/Polygon.html
    """
    def __init__(self, rings):
        self.rings = rings
        dict.__init__(self, {'rings': rings})

pyamf_classes = {
    amfFeatureSet: 'com.esri.ags.tasks.FeatureSet',
    amfSpatialReference: 'com.esri.ags.SpatialReference',
    amfGeometryMapPoint: 'com.esri.ags.geometry.MapPoint',
    amfGeometryPolyline: 'com.esri.ags.geometry.Polyline',
    amfGeometryPolygon: 'com.esri.ags.geometry.Polygon',
    amfFeature: 'com.esri.ags.Feature'
  }

def reserialize_to_arc(content):
    """ Convert from "geo" (GeoJSON) to ESRI's GeoServices REST serialization.
    
        Much of this cribbed from sample server queries and page 191+ of:
          http://www.esri.com/library/whitepapers/pdfs/geoservices-rest-spec.pdf
    """
    found_geometry_types = set([feat['geometry']['type'] for feat in content['features']])
    found_geometry_types = set([geometry_types.get(type) for type in found_geometry_types])
    
    if len(found_geometry_types) > 1:
        raise KnownUnknown('Arc serialization needs a single geometry type, not ' + ', '.join(found_geometry_types))
    
    crs = content['crs']
    sref = amfSpatialReference(crs.get('wkid', None), crs.get('wkt', None))
    geometry_type, features = None, []
    
    for feature in content['features']:
        geometry = feature['geometry']

        if geometry['type'] == 'Point':
            arc_geometry = amfGeometryMapPoint(*geometry['coordinates'])
        
        elif geometry['type'] == 'LineString':
            path = geometry['coordinates']
            path = [amfGeometryMapPoint(*xy) for xy in path]
            paths = [amfGeometryPolyline(path)]
            arc_geometry = {'paths': paths}

        elif geometry['type'] == 'Polygon':
            rings = geometry['coordinates']
            rings = [[amfGeometryMapPoint(*xy) for xy in ring] for ring in rings]
            rings = [amfGeometryPolygon(ring) for ring in rings]
            arc_geometry = {'rings': rings}

        elif geometry['type'] == 'MultiPoint':
            points = geometry['coordinates']
            arc_geometry = {'points': points}

        elif geometry['type'] == 'MultiLineString':
            paths = geometry['coordinates']
            paths = [[amfGeometryMapPoint(*xy) for xy in path] for path in paths]
            paths = [amfGeometryPolyline(path) for path in paths]
            arc_geometry = {'paths': paths}

        elif geometry['type'] == 'MultiPolygon':
            rings = reduce(add, geometry['coordinates'])
            rings = [[amfGeometryMapPoint(*xy) for xy in ring] for ring in rings]
            rings = [amfGeometryPolygon(ring) for ring in rings]
            arc_geometry = {'rings': rings}

        else:
            raise Exception(geometry['type'])
        
        arc_feature = amfFeature(feature['properties'], arc_geometry)
        geometry_type = geometry_types[geometry['type']]
        features.append(arc_feature)
    
    return amfFeatureSet(sref, geometry_type, features)
