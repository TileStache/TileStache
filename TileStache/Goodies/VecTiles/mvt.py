''' Implementation of MVT (Mapnik Vector Tiles) data format.

Mapnik's PythonDatasource.features() method can return a list of WKB features,
pairs of WKB format geometry and dictionaries of key-value pairs that are
rendered by Mapnik directly. PythonDatasource is new in Mapnik as of version
2.1.0.

More information:
    http://mapnik.org/docs/v2.1.0/api/python/mapnik.PythonDatasource-class.html

The MVT file format is a simple container for Mapnik-compatible vector tiles
that minimizes the amount of conversion performed by the renderer, in contrast
to other file formats such as GeoJSON.

An MVT file starts with 8 bytes.

    4 bytes "\\x89MVT"
    uint32  Length of body
    bytes   zlib-compressed body

The following body is a zlib-compressed bytestream. When decompressed,
it starts with four bytes indicating the total feature count.

    uint32  Feature count
    bytes   Stream of feature data

Each feature has two parts, a raw WKB (well-known binary) representation of
the geometry in spherical mercator and a JSON blob for feature properties.

    uint32  Length of feature WKB
    bytes   Raw bytes of WKB
    uint32  Length of properties JSON
    bytes   JSON dictionary of feature properties

By default, encode() approximates the floating point precision of WKB geometry
to 26 bits for a significant compression improvement and no visible impact on
rendering at zoom 18 and lower.
'''
try:
    from io import StringIO
except ImportError:
    # Python 2
    from StringIO import StringIO
from zlib import decompress as _decompress, compress as _compress
from struct import unpack as _unpack, pack as _pack
import json

from .wkb import approximate_wkb

def decode(file):
    ''' Decode an MVT file into a list of (WKB, property dict) features.
    
        Result can be passed directly to mapnik.PythonDatasource.wkb_features().
    '''
    head = file.read(4)
    
    if head != '\x89MVT':
        raise Exception('Bad head: "%s"' % head)
    
    body = StringIO(_decompress(file.read(_next_int(file))))
    features = []
    
    for i in range(_next_int(body)):
        wkb = body.read(_next_int(body))
        raw = body.read(_next_int(body))

        props = json.loads(raw)
        features.append((wkb, props))
    
    return features

def encode(file, features):
    ''' Encode a list of (WKB, property dict) features into an MVT stream.
    
        Geometries in the features list are assumed to be in spherical mercator.
        Floating point precision in the output is approximated to 26 bits.
    '''
    parts = []
    
    for feature in features:
        wkb = approximate_wkb(feature[0])
        prop = json.dumps(feature[1])
        
        parts.extend([_pack('>I', len(wkb)), wkb, _pack('>I', len(prop)), prop])
    
    body = _compress(_pack('>I', len(features)) + b''.join(parts))
    
    file.write(b'\x89MVT')
    file.write(_pack('>I', len(body)))
    file.write(body)

def _next_int(file):
    ''' Read the next big-endian 4-byte unsigned int from a file.
    '''
    return _unpack('!I', file.read(4))[0]
