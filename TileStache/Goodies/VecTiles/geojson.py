from re import compile
from math import pi, log, tan, ceil

import json

from shapely.wkb import loads
from shapely.geometry import asShape

from ... import getTile
from ...Core import KnownUnknown
from .ops import transform

float_pat = compile(r'^-?\d+\.\d+(e-?\d+)?$')
charfloat_pat = compile(r'^[\[,\,]-?\d+\.\d+(e-?\d+)?$')

# floating point lat/lon precision for each zoom level, good to ~1/4 pixel.
precisions = [int(ceil(log(1<<zoom + 8+2) / log(10)) - 2) for zoom in range(23)]

def get_tiles(names, config, coord):
    ''' Retrieve a list of named GeoJSON layer tiles from a TileStache config.
    
        Check integrity and compatibility of each, looking at known layers,
        correct JSON mime-types and "FeatureCollection" in the type attributes.
    '''
    unknown_layers = set(names) - set(config.layers.keys())
    
    if unknown_layers:
        raise KnownUnknown("%s.get_tiles didn't recognize %s when trying to load %s." % (__name__, ', '.join(unknown_layers), ', '.join(names)))
    
    layers = [config.layers[name] for name in names]
    mimes, bodies = zip(*[getTile(layer, coord, 'json') for layer in layers])
    bad_mimes = [(name, mime) for (mime, name) in zip(mimes, names) if not mime.endswith('/json')]
    
    if bad_mimes:
        raise KnownUnknown('%s.get_tiles encountered a non-JSON mime-type in %s sub-layer: "%s"' % ((__name__, ) + bad_mimes[0]))
    
    geojsons = [json.loads(body.decode('utf8')) for body in bodies]
    bad_types = [(name, topo['type']) for (topo, name) in zip(geojsons, names) if topo['type'] != 'FeatureCollection']
    
    if bad_types:
        raise KnownUnknown('%s.get_tiles encountered a non-FeatureCollection type in %s sub-layer: "%s"' % ((__name__, ) + bad_types[0]))
    
    return geojsons

def mercator(xy):
    ''' Project an (x, y) tuple to spherical mercator.
    '''
    _x, _y = xy
    x, y = pi * _x/180, pi * _y/180
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

def encode(file, features, zoom, is_clipped):
    ''' Encode a list of (WKB, property dict) features into a GeoJSON stream.
    
        Also accept three-element tuples as features: (WKB, property dict, id).
    
        Geometries in the features list are assumed to be unprojected lon, lats.
        Floating point precision in the output is truncated to six digits.
    '''
    try:
        # Assume three-element features
        features = [dict(type='Feature', properties=p, geometry=loads(g).__geo_interface__, id=i) for (g, p, i) in features]

    except ValueError:
        # Fall back to two-element features
        features = [dict(type='Feature', properties=p, geometry=loads(g).__geo_interface__) for (g, p) in features]
    
    if is_clipped:
        for feature in features:
            feature.update(dict(clipped=True))
    
    geojson = dict(type='FeatureCollection', features=features)
    encoder = json.JSONEncoder(separators=(',', ':'))
    encoded = encoder.iterencode(geojson)
    flt_fmt = '%%.%df' % precisions[zoom]
    
    for token in encoded:
        if charfloat_pat.match(token):
            # in python 2.7, we see a character followed by a float literal
            piece = token[0] + flt_fmt % float(token[1:])
        elif float_pat.match(token):
            # in python 2.6, we see a simple float literal
            piece = flt_fmt % float(token)
        else:
            piece = token
        file.write(piece.encode('utf8'))

def merge(file, names, config, coord):
    ''' Retrieve a list of GeoJSON tile responses and merge them into one.
    
        get_tiles() retrieves data and performs basic integrity checks.
    '''
    inputs = get_tiles(names, config, coord)
    output = dict(zip(names, inputs))

    encoder = json.JSONEncoder(separators=(',', ':'))
    encoded = encoder.iterencode(output)
    flt_fmt = '%%.%df' % precisions[coord.zoom]
    
    for token in encoded:
        if charfloat_pat.match(token):
            # in python 2.7, we see a character followed by a float literal
            piece = token[0] + flt_fmt % float(token[1:])
        elif float_pat.match(token):
            # in python 2.6, we see a simple float literal
            piece = flt_fmt % float(token)
        else:
            piece = token
        file.write(piece.encode('utf8'))
