""" Arc-specific Vector provider helpers.
"""
from TileStache.Core import KnownUnknown

geometry_types = {
    'Point': 'esriGeometryPoint',
    'LineString': 'esriGeometryPolyline',
    'Polygon': 'esriGeometryPolygon',
    'MultiPoint': 'esriGeometryMultipoint',
    'MultiLineString': 'esriGeometryPolyline',
    'MultiPolygon': 'esriGeometryPolygon'
  }

class amfSpatialReference(dict):
    """ Registered PyAMF class for com.esri.ags.SpatialReference
    
        http://help.arcgis.com/en/webapi/flex/apiref/com/esri/ags/SpatialReference.html
    """
    def __init__(self, wkid, wkt):
        self.wkid = wkid
        self.wkt = wkt
        dict.__init__(self, {'wkid': wkid, 'wkt': wkt})

class amfGeometryMapPoint(dict):
    """ Registered PyAMF class for com.esri.ags.geometry.MapPoint
    
        http://help.arcgis.com/en/webapi/flex/apiref/com/esri/ags/geometry/MapPoint.html
    """
    def __init__(self, x, y):
        self.x = x
        self.y = y
        dict.__init__(self, {'x': x, 'y': y})

pyamf_classes = {
    amfSpatialReference: 'com.esri.ags.SpatialReference',
    amfGeometryMapPoint: 'com.esri.ags.geometry.MapPoint'
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
    
    response = {'spatialReference': sref, 'features': []}
    
    for feature in content['features']:
        geometry = feature['geometry']

        if geometry['type'] == 'Point':
            arc_geometry = amfGeometryMapPoint(*geometry['coordinates'])
        
        elif geometry['type'] == 'LineString':
            path = geometry['coordinates']
            arc_geometry = {'paths': [path]}

        elif geometry['type'] == 'Polygon':
            rings = geometry['coordinates']
            arc_geometry = {'rings': rings}

        elif geometry['type'] == 'MultiPoint':
            points = geometry['coordinates']
            arc_geometry = {'points': points}

        elif geometry['type'] == 'MultiLineString':
            paths = geometry['coordinates']
            arc_geometry = {'paths': paths}

        elif geometry['type'] == 'MultiPolygon':
            rings = reduce(add, geometry['coordinates'])
            arc_geometry = {'rings': rings}

        else:
            raise Exception(geometry['type'])
        
        arc_feature = {'attributes': feature['properties'], 'geometry': arc_geometry}
        response['geometryType'] = geometry_types[geometry['type']]
        response['features'].append(arc_feature)
    
    return response
