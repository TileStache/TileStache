from re import compile

import json
import mapnik

from shapely.wkb import loads
from shapely.geometry import asShape
from .ops import transform

srs = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +no_defs'
proj = mapnik.Projection(srs)

float_pat = compile(r'^-?\d+\.\d+(e-?\d+)?$')
charfloat_pat = compile(r'^[\[,\,]-?\d+\.\d+(e-?\d+)?$')

def mercator((x, y)):
    ''' Project an (x, y) tuple to spherical mercator.
    '''
    coord = proj.forward(mapnik.Coord(x, y))
    return coord.x, coord.y

def decode(file):
    ''' Decode a GeoJSON file into a list of (WKB, property dict) features.
    
        Result can be passed directly to mapnik.PythonDatasource.wkb_features().
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

def encode(file, features):
    '''
    '''
    features = [dict(type='Feature', properties=p, geometry=loads(g).__geo_interface__) for (g, p) in features]
    
    geojson = dict(type='FeatureCollection', features=features)
    encoder = json.JSONEncoder(separators=(',', ':'))
    encoded = encoder.iterencode(geojson)
    
    for token in encoded:
        if charfloat_pat.match(token):
            # in python 2.7, we see a character followed by a float literal
            file.write(token[0] + '%.6f' % float(token[1:]))
        
        elif float_pat.match(token):
            # in python 2.6, we see a simple float literal
            file.write('%.6f' % float(token))
        
        else:
            file.write(token)
