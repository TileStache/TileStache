import mapbox_vector_tile

# coordindates are scaled to this range within tile
extents = 4096

# tiles are padded by this number of pixels for the current zoom level 
padding = 0


def decode(file):
    tile = file.read()
    data = mapbox_vector_tile.decode(tile)
    return data # print data or write to file?


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
