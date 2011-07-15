from struct import unpack, pack
from numpy import zeros, uint8, sqrt as nsqrt
from math import log, ceil

try:
    from PIL import Image, ImagePalette
except:
    import Image, ImagePalette

def load_palette(filename):
    """ Load colors from a Photoshop .act file, return an Nx3 uint8 palette array.
    """
    bytes = open(filename, 'r').read()
    count, transparent = unpack('!HH', bytes[768:772])
    palette = zeros((count, 3), dtype=uint8)
    
    for offset in range(0, count):
        if offset == transparent:
            rgb = 0xff, 0x99, 0x00
        else:
            rgb = unpack('!BBB', bytes[offset*3:offset*3+3])

        palette[offset,:] = rgb
    
    return palette, transparent

def palette_color(r, g, b, palette):
    """ Return best palette match index.

        Find the closest color in the palette based on dumb euclidian distance,
        assign its index in the palette to a mapping from 24-bit color tuples.
    """
    distances = (palette[:,0] - r)**2 + (palette[:,1] - g)**2 + (palette[:,2] - b)**2
    distances = list(nsqrt(distances))
    
    return distances.index(min(distances))

def palettize(image, palette, t_index):
    """ Apply an Nx3 palette array to an image, return it and calculate bit depth.
    """
    image = image.convert('RGBA')
    pixels = image.tostring()
    palette = palette.astype(float)
    t_index = (t_index <= 0xff) and pack('!B', t_index) or None
    mapping = {}
    indexes = []
    
    for offset in range(0, len(pixels), 4):
        r, g, b, a = unpack('!BBBB', pixels[offset:offset+4])
        
        if a < 0x80 and t_index is not None:
            # Sufficiently transparent
            indexes.append(t_index)
            continue
        
        try:
            indexes.append(mapping[(r, g, b)])

        except KeyError:
            # Never seen this color
            mapping[(r, g, b)] = pack('!B', palette_color(r, g, b, palette))
        
        else:
            continue
        
        indexes.append(mapping[(r, g, b)])

    output = Image.fromstring('P', image.size, ''.join(indexes))
    bits = int(ceil(log(palette.shape[0]) / log(2)))
    
    palette = [unpack('!B', char)[0] for char in palette.astype(uint8).data]
    palette += [0] * (768 - len(palette))
    output.putpalette(palette)
    
    return output, bits

image = Image.open('/Users/migurski/Pictures/stupid bicycle.jpg')
palette, transparent = load_palette('/tmp/bicycle.act')

image = Image.open('/tmp/inundation_b.png')
palette, transparent = load_palette('/tmp/inundation_b.act')

output, bits = palettize(image, palette, transparent)
kwargs = dict(optimize=True, transparency=transparent, bits=bits)

output.save('/tmp/inundation_b-P.png', **kwargs)
