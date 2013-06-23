from shapely.wkb import loads
import json

from ... import getTile
from ...Core import KnownUnknown

class MultiProvider:
    ''' TopoJSON provider to gather layers into a single multi-response.
    
        names:
          List of names of TopoJSON-generating layers from elsewhere in config.
        
        Sample configuration, for a layer with combined data from water
        and land areas, both assumed to be TopoJSON-returning layers:
        
          "provider":
          {
            "class": "TileStache.Goodies.VecTiles.topojson:MultiProvider",
            "kwargs":
            {
              "names": ["water-areas", "land-areas"]
            }
          }
    '''
    def __init__(self, layer, names):
        self.layer = layer
        self.names = names
        
    def renderTile(self, width, height, srs, coord):
        ''' Render a single tile, return a Response instance.
        '''
        inputs = get_tile_topojsons(self.layer.config, self.names, coord)
        
        output = {
            'type': 'Topology',
            'transform': inputs[0]['transform'],
            'objects': dict(),
            'arcs': list()
            }
        
        for (name, input) in zip(self.names, inputs):
            for (index, object) in enumerate(input['objects'].values()):
                if len(input['objects']) > 1:
                    output['objects']['%(name)s-%(index)d' % locals()] = object
                else:
                    output['objects'][name] = object
                
                for geometry in object['geometries']:
                    update_arc_indexes(geometry, output['arcs'], input['arcs'])
        
        return JSONResponse(output)

    def getTypeByExtension(self, extension):
        ''' Get mime-type and format by file extension, "topojson" only.
        '''
        if extension.lower() == 'topojson':
            return 'application/json', 'TopoJSON'
        
        raise ValueError(extension)

class JSONResponse:
    '''
    '''
    def __init__(self, object):
        self.object = object
    
    def save(self, out, format):
        json.dump(self.object, out, separators=(',', ':'))

def get_tile_topojsons(config, names, coord):
    '''
    '''
    unknown_layers = set(names) - set(config.layers.keys())
    
    if unknown_layers:
        raise KnownUnknown("%s.get_tile_topojsons didn't recognize %s when trying to load %s." % (__name__, ', '.join(unknown_layers), ', '.join(names)))
    
    layers = [config.layers[name] for name in names]
    mimes, bodies = zip(*[getTile(layer, coord, 'topojson') for layer in layers])
    bad_mimes = [(name, mime) for (mime, name) in zip(mimes, names) if not mime.endswith('/json')]
    
    if bad_mimes:
        raise KnownUnknown('%s.get_tile_topojsons encountered a non-JSON mime-type in %s sub-layer: "%s"' % ((__name__, ) + bad_mimes[0]))
    
    topojsons = map(json.loads, bodies)
    bad_types = [(name, topo['type']) for (topo, name) in zip(topojsons, names) if topo['type'] != 'Topology']
    
    if bad_types:
        raise KnownUnknown('%s.get_tile_topojsons encountered a non-Topology type in %s sub-layer: "%s"' % ((__name__, ) + bad_types[0]))
    
    transforms = [topo['transform'] for topo in topojsons]
    unique_xforms = set([tuple(xform['scale'] + xform['translate']) for xform in transforms])
    
    if len(unique_xforms) > 1:
        raise KnownUnknown('%s.get_tile_topojsons encountered incompatible transforms: %s' % (__name__, list(unique_xforms)))
    
    return topojsons

def update_arc_indexes(geometry, merged_arcs, old_arcs):
    ''' Updated geometry arc indexes, and add arcs to merged_arcs along the way.
    
        Arguments are modified in-place, and nothing is returned.
    '''
    if geometry['type'] in ('Point', 'MultiPoint'):
        return
    
    elif geometry['type'] == 'LineString':
        for (arc_index, old_arc) in enumerate(geometry['arcs']):
            geometry['arcs'][arc_index] = len(merged_arcs)
            merged_arcs.append(old_arcs[old_arc])
    
    elif geometry['type'] == 'Polygon':
        for ring in geometry['arcs']:
            for (arc_index, old_arc) in enumerate(ring):
                ring[arc_index] = len(merged_arcs)
                merged_arcs.append(old_arcs[old_arc])
    
    elif geometry['type'] == 'MultiLineString':
        for part in geometry['arcs']:
            for (arc_index, old_arc) in enumerate(part):
                part[arc_index] = len(merged_arcs)
                merged_arcs.append(old_arcs[old_arc])
    
    elif geometry['type'] == 'MultiPolygon':
        for part in geometry['arcs']:
            for ring in part:
                for (arc_index, old_arc) in enumerate(ring):
                    ring[arc_index] = len(merged_arcs)
                    merged_arcs.append(old_arcs[old_arc])
    
    else:
        raise NotImplementedError("Can't do %s geometries" % geometry['type'])

def get_transform(bounds, size=512):
    ''' Return a TopoJSON transform dictionary and a point-transforming function.
    '''
    trans = bounds[0], bounds[1]
    scale = (bounds[2] - bounds[0]) / size, (bounds[3] - bounds[1]) / size
    
    def forward(lon, lat):
        ''' Transform a longitude and latitude to TopoJSON integer space.
        '''
        return int((lon - trans[0]) / scale[0]), int((lat - trans[1]) / scale[1])
    
    return dict(translate=trans, scale=scale), forward

def diff_encode(line, transform):
    ''' Differentially encode a shapely linestring or ring.
    '''
    coords = [transform(x, y) for (x, y) in line.coords]
    
    pairs = zip(coords[:], coords[1:])
    diffs = [(x2 - x1, y2 - y1) for ((x1, y1), (x2, y2)) in pairs]
    
    return coords[:1] + [(x, y) for (x, y) in diffs if (x, y) != (0, 0)]

def decode(file):
    ''' Stub function to decode a TopoJSON file into a list of features.
    
        Not currently implemented, modeled on geojson.decode().
    '''
    raise NotImplementedError('topojson.decode() not yet written')

def encode(file, features, bounds):
    ''' Encode a list of (WKB, property dict) features into a TopoJSON stream.
    
        Also accept three-element tuples as features: (WKB, property dict, id).
    
        Geometries in the features list are assumed to be unprojected lon, lats.
        Bounds are given in geographic coordinates as (xmin, ymin, xmax, ymax).
    '''
    transform, forward = get_transform(bounds)
    geometries, arcs = list(), list()
    
    for feature in features:
        shape = loads(feature[0])
        geometry = dict(properties=feature[1])
        geometries.append(geometry)
        
        if len(feature) >= 2:
            # ID is an optional third element in the feature tuple
            geometry.update(dict(id=feature[2]))
        
        if shape.type == 'GeometryCollection':
            geometries.pop()
            continue
    
        elif shape.type == 'Point':
            geometry.update(dict(type='Point', coordinates=forward(shape.x, shape.y)))
    
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
        'type': 'Topology',
        'transform': transform,
        'objects': {
            'vectile': {
                'type': 'GeometryCollection',
                'geometries': geometries
                }
            },
        'arcs': arcs
        }
    
    json.dump(result, file, separators=(',', ':'))
