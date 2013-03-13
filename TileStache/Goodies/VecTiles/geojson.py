from re import compile
from math import pi, log, tan

import json

from shapely.wkb import loads
from shapely.geometry import asShape
from .ops import transform

float_pat = compile(r'^-?\d+\.\d+(e-?\d+)?$')
charfloat_pat = compile(r'^[\[,\,]-?\d+\.\d+(e-?\d+)?$')

def mercator((x, y)):
    ''' Project an (x, y) tuple to spherical mercator.
    '''
    x, y = pi * x/180, pi * y/180
    y = log(tan(0.25 * pi + 0.5 * y))
    return 6378137 * x, 6378137 * y

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
    ''' Encode a list of (WKB, property dict) features into a GeoJSON stream.
    
        Geometries in the features list are assumed to be unprojected lon, lats.
        Floating point precision in the output is truncated to six digits.
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
