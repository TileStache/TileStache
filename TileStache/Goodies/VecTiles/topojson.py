from shapely.wkb import loads
import json

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
        raise NotImplementedError("Working on it")

    def getTypeByExtension(self, extension):
        ''' Get mime-type and format by file extension, "topojson" only.
        '''
        if extension.lower() == 'topojson':
            return 'application/json', 'TopoJSON'
        
        raise ValueError(extension)

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
