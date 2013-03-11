import json
import mapnik
from shapely.geometry import asShape
from .ops import transform

srs = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +no_defs'
proj = mapnik.Projection(srs)

def mercator((x, y)):
    ''' Project an (x, y) tuple to spherical mercator.
    '''
    coord = proj.forward(mapnik.Coord(x, y))
    return coord.x, coord.y

def decode(file):
    ''' Load data from a GeoJSON stream.
        
        Returns a list of (WKB, property dict) pairs.
    '''
    data = json.load(file)
    features = []
    
    for feature in data['features']:
        if feature['type'] != 'Feature':
            continue
        
        if feature['geometry']['type'] == 'GeometryCollection':
            continue
        
        prop = feature['properties']
        geom = transform(asShape(feature['geometry']), mercator)
        features.append((geom.wkb, prop))
    
    return features
