""" The cache bits of TileStache.

A Cache is the part of TileStache that stores static files to speed up future
requests. A few default caches are found here, but it's possible to define your
own and pull them into TileStache dynamically by class name.

Built-in providers:
- test
- disk

Example built-in cache, for JSON configuration file:

    "cache": {
      "name": "Disk",
      "path": "/tmp/stache",
      "umask": "0000"
    }

Example external cache, for JSON configuration file:

    "cache": {
      "class": "Module.Classname",
      "kwargs": {"frob": "yes"}
    }

- The "class" value is split up into module and classname, and dynamically
  included. If this doesn't work for some reason, TileStache will fail loudly
  to let you know.
- The "kwargs" value is fed to the class constructor as a dictionary of keyword
  args. If your defined class doesn't accept any of these keyword arguments,
  TileStache will throw an exception.

A cache must provide these methods: lock(), unlock(), read(), and save().
Each method accepts three arguments:

- layer: instance of a Layer.
- coord: single Coordinate that represents a tile.
- format: string like "png" or "jpg" that is used as a filename extension.

The save() method accepts an additional argument before the others:

- body: raw content to save to the cache.
"""

import os
import sys
import time

from tempfile import mkstemp
from os.path import isdir, exists, dirname, basename, join as pathjoin

def getCacheByName(name):
    """ Retrieve a cache object by name.
    
        Raise an exception if the name doesn't work out.
    """
    if name.lower() == 'test':
        return Test

    elif name.lower() == 'disk':
        return Disk

    raise Exception('Unknown cache name: "%s"' % name)

class Test:
    """ Simple cache that doesn't actually cache anything.
    
        Activity is optionally logged, though.
    
        Example configuration:

            "cache": {
              "name": "Test",
              "verbose": True
            }

        Extra configuration parameters:
        - verbose: optional boolean flag to write cache activities to a logging
          function, defaults to False if omitted.
    """
    def __init__(self, logfunc=None):
        self.logfunc = logfunc

    def _description(self, layer, coord, format):
        """
        """
        name = layer.name()
        tile = '%(zoom)d/%(column)d/%(row)d' % coord.__dict__

        return ' '.join( (name, tile, format) )
    
    def lock(self, layer, coord, format):
        """ Pretend to acquire a cache lock for this tile.
        """
        name = self._description(layer, coord, format)
        
        if self.logfunc:
            self.logfunc('Test cache lock: ' + name)
    
    def unlock(self, layer, coord, format):
        """ Pretend to release a cache lock for this tile.
        """
        name = self._description(layer, coord, format)

        if self.logfunc:
            self.logfunc('Test cache unlock: ' + name)
    
    def read(self, layer, coord, format):
        """ Pretend to read a cached tile.
        """
        name = self._description(layer, coord, format)
        
        if self.logfunc:
            self.logfunc('Test cache read: ' + name)

        return None
    
    def save(self, body, layer, coord, format):
        """ Pretend to save a cached tile.
        """
        name = self._description(layer, coord, format)
        
        if self.logfunc:
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

        If your configuration file is loaded from a remote location, e.g.
        "http://example.com/tilestache.cfg", the path *must* be an unambiguous
        filesystem path, e.g. "file:///tmp/cache"
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

    def _lockpath(self, layer, coord, format):
        """
        """
        return self._fullpath(layer, coord, format) + '.lock'
    
    def lock(self, layer, coord, format):
        """ Acquire a cache lock for this tile.
        
            Returns nothing, but blocks until the lock has been acquired.
            Lock is implemented as an empty directory next to the tile file.
        """
        lockpath = self._lockpath(layer, coord, format)
        due = time.time() + layer.stale_lock_timeout
        
        while True:
            # try to acquire a directory lock, repeating if necessary.
            try:
                umask_old = os.umask(self.umask)
                
                if time.time() > due:
                    # someone left the door locked.
                    os.rmdir(lockpath)
                
                os.makedirs(lockpath, 0777&~self.umask)
                break
            except OSError, e:
                if e.errno != 17:
                    raise
                time.sleep(.2)
            finally:
                os.umask(umask_old)
    
    def unlock(self, layer, coord, format):
        """ Release a cache lock for this tile.

            Lock is implemented as an empty directory next to the tile file.
        """
        lockpath = self._lockpath(layer, coord, format)
        os.rmdir(lockpath)
    
    def read(self, layer, coord, format):
        """ Read a cached tile.
        """
        fullpath = self._fullpath(layer, coord, format)
        
        if exists(fullpath):
            return open(fullpath, 'r').read()

        return None
    
    def save(self, body, layer, coord, format):
        """ Save a cached tile.
        """
        fullpath = self._fullpath(layer, coord, format)
        
        try:
            umask_old = os.umask(self.umask)
            os.makedirs(dirname(fullpath), 0777&~self.umask)
        except OSError, e:
            if e.errno != 17:
                raise
        finally:
            os.umask(umask_old)

        fh, tmp_path = mkstemp(dir=self.cachepath, suffix='.' + format.lower())
        os.write(fh, body)
        os.close(fh)
        
        try:
            os.rename(tmp_path, fullpath)
        except OSError:
            os.unlink(fullpath)
            os.rename(tmp_path, fullpath)

        os.chmod(fullpath, 0666&~self.umask)
