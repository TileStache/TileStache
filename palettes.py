from struct import unpack, pack
from math import log, ceil, sqrt
from operator import add

try:
    from PIL import Image, ImagePalette
except:
    import Image, ImagePalette

def load_palette(filename):
    """ Load colors from a Photoshop .act file, return a palette array.
    
        Return array is structured as: [ (r, g, b), (r, g, b), ... ]
    """
    bytes = open(filename, 'r').read()
    count, t_index = unpack('!HH', bytes[768:768+4])
    palette = []
    
    for offset in range(0, count):
        if offset == t_index:
            rgb = 0xff, 0x99, 0x00
        else:
            rgb = unpack('!BBB', bytes[offset*3:(offset + 1)*3])
        
        palette.append(rgb)
    
    return palette, t_index

def palette_color(r, g, b, palette, t_index):
    """ Return best palette match index.

        Find the closest color in the palette based on dumb euclidian distance,
        assign its index in the palette to a mapping from 24-bit color tuples.
    """
    distances = [(r - _r)**2 + (g - _g)**2 + (b - _b)**2 for (_r, _g, _b) in palette]
    distances = map(sqrt, distances)
    
    if t_index is not None:
        distances = distances[:t_index] + distances[t_index+1:]
    
    return distances.index(min(distances))

def palettize(image, palette, t_index=None):
    """ Apply an Nx3 palette array to an image, return it and calculate bit depth.
    """
    image = image.convert('RGBA')
    pixels = image.tostring()
    t_value = (t_index <= 0xff) and pack('!B', t_index) or None
    mapping = {}
    indexes = []
    
    for offset in range(0, len(pixels), 4):
        r, g, b, a = unpack('!BBBB', pixels[offset:offset+4])
        
        if a < 0x80 and t_value is not None:
            # Sufficiently transparent
            indexes.append(t_value)
            continue
        
        try:
            indexes.append(mapping[(r, g, b)])

        except KeyError:
            # Never seen this color
            mapping[(r, g, b)] = pack('!B', palette_color(r, g, b, palette, t_index))
        
        else:
            continue
        
        indexes.append(mapping[(r, g, b)])

    output = Image.fromstring('P', image.size, ''.join(indexes))
    bits = int(ceil(log(len(palette)) / log(2)))
    
    palette += [(0, 0, 0)] * (256 - len(palette))
    palette = reduce(add, palette)
    output.putpalette(palette)
    
    return output, bits

image = Image.open('/Users/migurski/Pictures/stupid bicycle.jpg')
palette, t_index = load_palette('/tmp/bicycle.act')

image = Image.open('/tmp/inundation_b.png')
palette, t_index = load_palette('/tmp/inundation_b.act')

output, bits = palettize(image, palette, t_index)
kwargs = dict(optimize=True, transparency=t_index, bits=bits)

output.save('/tmp/inundation_b-P.png', **kwargs)
