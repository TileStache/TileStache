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

def reserialize_to_arc(content):
    """ Convert from "geo" (GeoJSON) to ESRI's GeoServices REST serialization.
    
        Much of this cribbed from sample server queries and page 191+ of:
          http://www.esri.com/library/whitepapers/pdfs/geoservices-rest-spec.pdf
    """
    found_geometry_types = set([feat['geometry']['type'] for feat in content['features']])
    found_geometry_types = set([geometry_types.get(type) for type in found_geometry_types])
    
    if len(found_geometry_types) > 1:
        raise KnownUnknown('Arc serialization needs a single geometry type, not ' + ', '.join(found_geometry_types))
    
    response = {'spatialReference': {'wkid': 4326}, 'features': []}
    
    if 'wkid' in content['crs']:
        response['spatialReference'] = {'wkid': content['crs']['wkid']}
    
    elif 'wkt' in content['crs']:
        response['spatialReference'] = {'wkt': content['crs']['wkt']}
    
    for feature in content['features']:
        geometry = feature['geometry']

        if geometry['type'] == 'Point':
            x, y = geometry['coordinates']
            arc_geometry = {'x': x, 'y': y}
        
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
