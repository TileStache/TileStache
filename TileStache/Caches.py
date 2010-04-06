import os

from sys import stderr, stdout
from os.path import isdir, exists, dirname, join as pathjoin

class Test:

    def __init__(self, logerror):
        self.logerror = logerror

    def description(self, layer, coord, format):
        """
        """
        name = layer.name()
        tile = '%(zoom)d/%(column)d/%(row)d' % coord.__dict__
        
        return ' '.join( (name, tile, format) )
    
    def read(self, layer, coord, format):
        """
        """
        name = self.description(layer, coord, format)
        self.logerror('Test cache read: ' + name)

        return None
    
    def save(self, body, layer, coord, format):
        """
        """
        name = self.description(layer, coord, format)
        self.logerror('Test cache save: %d bytes to %s' % (len(body), name))

class Disk:
    
    def __init__(self, cachepath, umask=0022):
        self.cachepath = cachepath
        self.umask = umask

    def filepath(self, layer, coord, format):
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

    def fullpath(self, layer, coord, format):
        """
        """
        filepath = self.filepath(layer, coord, format)
        fullpath = pathjoin(self.cachepath, filepath)

        return fullpath
    
    def read(self, layer, coord, format):
        """
        """
        fullpath = self.fullpath(layer, coord, format)
        
        if exists(fullpath):
            return open(fullpath, 'r').read()

        return None
    
    def save(self, body, layer, coord, format):
        """
        """
        fullpath = self.fullpath(layer, coord, format)
        
        if not isdir(dirname(fullpath)):
            umask_old = os.umask(self.umask)
            os.makedirs(dirname(fullpath), 0777^self.umask)
            os.umask(umask_old)
        
        open(fullpath, 'w').write(body)
        os.chmod(fullpath, 0666^self.umask)
        
        print >> stderr, fullpath
