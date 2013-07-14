''' GeoPack encoding support for VecTiles.

GeoPack is a data format based on TopoJSON, with three key differences:

 1. No "type=Topology" property is included in the base object.

 2. Each geometry has an additional "bounds" array with four elements: minlon,
    minlat, maxlon, and maxlat. Point bounds have two elements, lon and lat.

 3. GeoPack implicitly uses a tile dimension of 4096 pixels instead of 1024
    pixels as in TopoJSON, because it's expected to be used in server-side
    cases where zoom=14 tiles supply complete geometry for zoom=18 tiles.
'''
from shapely.wkb import loads
import msgpack

from ... import getTile
from ...Core import KnownUnknown

# most core geometry functions are simply borrowed from TopoJSON
from .topojson import update_arc_indexes, get_transform, diff_encode

def get_tiles(names, config, coord):
    ''' Retrieve a list of named GeoPack layer tiles from a TileStache config.
    
        Check integrity and compatibility of each, looking at known layers,
        correct MessagePack mime-types and matching affine transformations.
    '''
    unknown_layers = set(names) - set(config.layers.keys())
    
    if unknown_layers:
        raise KnownUnknown("%s.get_tiles didn't recognize %s when trying to load %s." % (__name__, ', '.join(unknown_layers), ', '.join(names)))
    
    layers = [config.layers[name] for name in names]
    mimes, bodies = zip(*[getTile(layer, coord, 'geopack') for layer in layers])
    bad_mimes = [(name, mime) for (mime, name) in zip(mimes, names) if not mime == 'application/msgpack']
    
    if bad_mimes:
        raise KnownUnknown('%s.get_tiles encountered a non-plaintext mime-type in %s sub-layer: "%s"' % ((__name__, ) + bad_mimes[0]))
    
    geopacks = map(msgpack.loads, bodies)
    transforms = [pack['transform'] for pack in geopacks]
    unique_xforms = set([tuple(xform['scale'] + xform['translate']) for xform in transforms])
    
    if len(unique_xforms) > 1:
        raise KnownUnknown('%s.get_tiles encountered incompatible transforms: %s' % (__name__, list(unique_xforms)))
    
    return geopacks

def decode(file):
    ''' Stub function to decode a GeoPack file into a list of features.
    
        Not currently implemented, modeled on geojson.decode().
    '''
    raise NotImplementedError('geopack.decode() not yet written')

def encode(file, features, bounds, is_clipped):
    ''' Encode a list of (WKB, property dict) features into a GeoPack stream.
    
        Also accept three-element tuples as features: (WKB, property dict, id).
    
        Geometries in the features list are assumed to be unprojected lon, lats.
        Bounds are given in geographic coordinates as (xmin, ymin, xmax, ymax).
    '''
    transform, forward = get_transform(bounds, 1<<12)
    geometries, arcs = list(), list()
    
    for feature in features:
        shape = loads(feature[0])
        geometry = dict(properties=feature[1], bounds=shape.bounds)
        geometries.append(geometry)
        
        if is_clipped:
            geometry.update(dict(clipped=True))
        
        if len(feature) >= 2:
            # ID is an optional third element in the feature tuple
            geometry.update(dict(id=feature[2]))
        
        if shape.type == 'GeometryCollection':
            geometries.pop()
            continue
    
        elif shape.type == 'Point':
            geometry.update(dict(type='Point', coordinates=forward(shape.x, shape.y)))
            geometry.update(dict(bounds=geometry['bounds'][:2]))
    
        elif shape.type == 'LineString':
            geometry.update(dict(type='LineString', arcs=[len(arcs)]))
            arcs.append(diff_encode(shape, forward))
    
        elif shape.type == 'Polygon':
            geometry.update(dict(type='Polygon', arcs=[]))

            rings = [shape.exterior] + list(shape.interiors)
            
            for ring in rings:
                geometry['arcs'].append([len(arcs)])
                arcs.append(diff_encode(ring, forward))
        
        elif shape.type == 'MultiPoint':
            geometry.update(dict(type='MultiPoint', coordinates=[]))
            
            for point in shape.geoms:
                geometry['coordinates'].append(forward(point.x, point.y))
        
        elif shape.type == 'MultiLineString':
            geometry.update(dict(type='MultiLineString', arcs=[]))
            
            for line in shape.geoms:
                geometry['arcs'].append([len(arcs)])
                arcs.append(diff_encode(line, forward))
        
        elif shape.type == 'MultiPolygon':
            geometry.update(dict(type='MultiPolygon', arcs=[]))
            
            for polygon in shape.geoms:
                rings = [polygon.exterior] + list(polygon.interiors)
                polygon_arcs = []
                
                for ring in rings:
                    polygon_arcs.append([len(arcs)])
                    arcs.append(diff_encode(ring, forward))
            
                geometry['arcs'].append(polygon_arcs)
        
        else:
            raise NotImplementedError("Can't do %s geometries" % shape.type)
    
    result = {
        'transform': transform,
        'objects': {
            'vectile': {
                'type': 'GeometryCollection',
                'geometries': geometries
                }
            },
        'arcs': arcs
        }
    
    msgpack.dump(result, file)

def merge(file, names, config, coord):
    ''' Retrieve a list of GeoPack tile responses and merge them into one.
    
        get_tiles() retrieves data and performs basic integrity checks.
    '''
    inputs = get_tiles(names, config, coord)
    
    output = {
        'transform': inputs[0]['transform'],
        'objects': dict(),
        'arcs': list()
        }
    
    for (name, input) in zip(names, inputs):
        for (index, object) in enumerate(input['objects'].values()):
            if len(input['objects']) > 1:
                output['objects']['%(name)s-%(index)d' % locals()] = object
            else:
                output['objects'][name] = object
            
            for geometry in object['geometries']:
                update_arc_indexes(geometry, output['arcs'], input['arcs'])
    
    msgpack.dump(output, file)
