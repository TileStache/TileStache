from StringIO import StringIO
from zlib import decompress
from struct import unpack
import json

def decode(file):
    '''
    '''
    head = file.read(4)
    
    if head != '\x89MVT':
        raise Exception('Bad head: "%s"' % head)
    
    body = StringIO(decompress(file.read(_next_int(file))))
    features = []
    
    for i in range(_next_int(body)):
        wkb = body.read(_next_int(body))
        raw = body.read(_next_int(body))

        props = json.loads(raw)
        features.append((wkb, props))
    
    return features

def _next_int(file):
    ''' Read the next big-endian 4-byte unsigned int from a file.
    '''
    return unpack('!I', file.read(4))[0]
