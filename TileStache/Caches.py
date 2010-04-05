import os

from sys import stderr, stdout
from os.path import isdir, exists, dirname, join as pathjoin

class Disk:
    
    def __init__(self, cachepath, umask=0022):
        self.cachepath = cachepath
        self.umask = umask

    def filepath(self, layer, coord, format, query):
        """
        """
        l = layer.name()
        z = '%d' % coord.zoom
        x = '%06d' % coord.column
        y = '%06d' % coord.row
        e = format.lower()
        
        x1, x2 = x[:3], x[3:]
        y1, y2 = y[:3], y[3:]
        
        filepath = os.sep.join( (l, z, x1, x2, y1, y2 + '.' + e) )

        return filepath

    def fullpath(self, layer, coord, format, query):
        """
        """
        filepath = self.filepath(layer, coord, format, query)
        fullpath = pathjoin(self.cachepath, filepath)

        return fullpath
    
    def read(self, layer, coord, format, query):
        """
        """
        fullpath = self.fullpath(layer, coord, format, query)
        
        if exists(fullpath):
            return open(fullpath, 'r').read()

        return None
    
    def save(self, body, layer, coord, format, query):
        """
        """
        fullpath = self.fullpath(layer, coord, format, query)
        
        if not isdir(dirname(fullpath)):
            umask_old = os.umask(self.umask)
            os.makedirs(dirname(fullpath), 0777^self.umask)
            os.umask(umask_old)
        
        open(fullpath, 'w').write(body)
        os.chmod(fullpath, 0666^self.umask)
        
        print >> stderr, fullpath
