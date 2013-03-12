from .server import Provider
from .client import Datasource

#
# Smaller numbers prioritize roads in front of other roads.
#
highway_priorities = {
    'motorway': 0, 'trunk': 1, 'primary': 2, 'secondary': 3, 'tertiary': 4,
    'motorway_link': 5, 'trunk_link': 5, 'primary_link': 5, 'secondary_link': 5, 'tertiary_link': 5,
    'residential': 6, 'unclassified': 6, 'road': 6,
    'unclassified': 7, 'service': 7, 'minor': 7
    }

def feature_sortkey((geom, props)):
    ''' Get highway layer (z-index) as an integer.
    '''
    # explicit layering mostly wins
    layer = props.get('explicit_layer', 0) * 1000
    
    # implicit layering less important.
    if props['is_bridge'] == 'yes':
        layer += 100
    
    if props['is_tunnel'] == 'yes':
        layer -= 100
    
    # leave the +/-10 order of magnitude open for bridge casings.
    
    # adjust slightly based on priority derived from highway type
    highway = props.get('highway', None)
    layer -= highway_priorities.get(highway, 9)
    
    return layer
