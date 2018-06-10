""" Support for 8-bit image palettes in PNG output.

PNG images can be significantly cut down in size by using a color look-up table.
TileStache layers support Adobe Photoshop's .act file format for PNG output,
and can be referenced in a layer configuration file like this:

    "osm":
    {
      "provider": {"name": "proxy", "provider": "OPENSTREETMAP"},
      "png options": {"palette": "http://tilestache.org/example-palette-openstreetmap-mapnik.act"}
    }

The example OSM palette above is a real file with a 32 color (5 bit) selection
of colors appropriate for use with OpenStreetMap's default Mapnik cartography.

To generate an .act file, convert an existing image in Photoshop to indexed
color, and access the color table under Image -> Mode -> Color Table. Saving
the color table results in a usable .act file, internally structured as a
fixed-size 772-byte table with 256 3-byte RGB triplets, followed by a two-byte
unsigned int with the number of defined colors (may be less than 256) and a
finaly two-byte unsigned int with the optional index of a transparent color
in the lookup table. If the final byte is 0xFFFF, there is no transparency.
"""
from struct import unpack, pack
from math import sqrt, ceil, log
from .py3_compat import urlopen, reduce
from operator import add

try:
    from PIL import Image
except ImportError:
    # On some systems, PIL.Image is known as Image.
    import Image

def load_palette(file_href):
    """ Load colors from a Photoshop .act file, return palette info.

        Return tuple is an array of [ (r, g, b), (r, g, b), ... ],
        bit depth of the palette, and a numeric transparency index
        or None if not defined.
    """
    bytes_ = urlopen(file_href).read()
    count, t_index = unpack('!HH', bytes_[768:768+4])
    t_index = (t_index <= 0xff) and t_index or None

    palette = []

    for offset in range(0, count):
        if offset == t_index:
            rgb = 0xff, 0x99, 0x00
        else:
            rgb = unpack('!BBB', bytes_[offset*3:(offset + 1)*3])

        palette.append(rgb)

    bits = int(ceil(log(len(palette)) / log(2)))

    return palette, bits, t_index

def palette_color(r, g, b, palette, t_index):
    """ Return best palette match index.

        Find the closest color in the palette based on dumb euclidian distance,
        assign its index in the palette to a mapping from 24-bit color tuples.
    """
    distances = [(r - _r)**2 + (g - _g)**2 + (b - _b)**2 for (_r, _g, _b) in palette]
    distances = list(map(sqrt, distances))

    if t_index is not None:
        distances = distances[:t_index] + distances[t_index+1:]

    return distances.index(min(distances))

def apply_palette(image, palette, t_index):
    """ Apply a palette array to an image, return a new image.
    """
    image = image.convert('RGBA')
    pixels = image.tobytes()

    t_value = (t_index in range(256)) and pack('!B', t_index) or None
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

    if hasattr(Image, 'frombytes'):
        # Image.fromstring is deprecated past Pillow 2.0
        output = Image.frombytes('P', image.size, b''.join(indexes))
    else:
        # PIL still uses Image.fromstring
        output = Image.fromstring('P', image.size, b''.join(indexes))

    bits = int(ceil(log(len(palette)) / log(2)))

    palette += [(0, 0, 0)] * (256 - len(palette))
    palette = reduce(add, palette)
    output.putpalette(palette)

    return output

def apply_palette256(image):
    """ Get PIL to generate and apply an optimum 256 color palette to the given image and return it
    """
    return image.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=256, dither=Image.NONE)
