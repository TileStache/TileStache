import mapbox_vector_tile

# extracted from Mapzen TileStache fork version 0.9.0, more recent versions doesn't seem to work.
# https://github.com/tilezen/TileStache/blob/089ee60f9902e85678499fe8455580a8a013be89/TileStache/Goodies/VecTiles/mvt.py

# coordindates are scaled to this range within tile
extents = 4096


def decode(file):
    tile = file.read()
    data = mapbox_vector_tile.decode(tile)
    return data


def encode(file, features, coord, layer_name=''):
    layers = []

    layers.append(get_feature_layer(layer_name, features))

    data = mapbox_vector_tile.encode(layers)
    file.write(data)


def merge(file, feature_layers, coord):
    '''
    Retrieve a list of mapbox vector tile responses and merge them into one.

        get_tiles() retrieves data and performs basic integrity checks.
    '''
    layers = []

    for layer in feature_layers:
        layers.append(get_feature_layer(layer['name'], layer['features']))

    data = mapbox_vector_tile.encode(layers)
    file.write(data)


def get_feature_layer(name, features):
    _features = []

    for feature in features:
        wkb, props, fid = feature
        _features.append({
            'geometry': wkb,
            'properties': props,
            'id': fid,
        })

    return {
        'name': name or '',
        'features': _features
    }
