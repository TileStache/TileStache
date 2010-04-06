""" The cache bits of TileStache.

A Cache is the part of TileStache that stores static files to speed up future
requests. A few default caches are found here, but it's possible to define your
own and pull them into TileStache dynamically by class name.

Built-in providers:
- test
- disk

Example built-in cache:

    "cache": {
      "name": "Disk",
      "path": "/tmp/stache",
      "umask": "0000"
    }

Example external cache, for JSON configuration file:

    *** NOT YET IMPLEMENTED ***

"""

import os

from os.path import isdir, exists, dirname, join as pathjoin

class Test:
    """ Simple cache that doesn't actually cache anything.
    
        Activity is logged, though.
    
        Example configuration:

            "cache": {
              "name": "Test"
            }
    """
    def __init__(self, logfunc):
        self.logfunc = logfunc

    def _description(self, layer, coord, format):
        """
        """
        name = layer.name()
        tile = '%(zoom)d/%(column)d/%(row)d' % coord.__dict__
        
        return ' '.join( (name, tile, format) )
    
    def read(self, layer, coord, format):
        """
        """
        name = self._description(layer, coord, format)
        self.logfunc('Test cache read: ' + name)

        return None
    
    def save(self, body, layer, coord, format):
        """
        """
        name = self._description(layer, coord, format)
        self.logfunc('Test cache save: %d bytes to %s' % (len(body), name))

class Disk:
    """ Caches files to disk.
    
        Example configuration:

            "cache": {
              "name": "Disk",
              "path": "/tmp/stache",
              "umask": "0000"
            }

        Extra parameters:
        - path: required local directory path where files should be stored.
        - umask: optional string representation of octal permission mask
          for stored files. Defaults to 0022.
    """
    def __init__(self, path, umask=0022):
        self.cachepath = path
        self.umask = umask

    def _filepath(self, layer, coord, format):
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

    def _fullpath(self, layer, coord, format):
        """
        """
        filepath = self._filepath(layer, coord, format)
        fullpath = pathjoin(self.cachepath, filepath)

        return fullpath
    
    def read(self, layer, coord, format):
        """
        """
        fullpath = self._fullpath(layer, coord, format)
        
        if exists(fullpath):
            return open(fullpath, 'r').read()

        return None
    
    def save(self, body, layer, coord, format):
        """
        """
        fullpath = self._fullpath(layer, coord, format)
        
        if not isdir(dirname(fullpath)):
            umask_old = os.umask(self.umask)
            os.makedirs(dirname(fullpath), 0777^self.umask)
            os.umask(umask_old)
        
        open(fullpath, 'w').write(body)
        os.chmod(fullpath, 0666^self.umask)
