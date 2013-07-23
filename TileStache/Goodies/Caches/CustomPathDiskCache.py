""" CustomPathDiskCache is a extension for Disk cache that gain better 
    peformance when there are tens of thousands layers.  If there are 
    too many layer folders in the same path, it will slow down the file read/write speed.
    The CustomPathDiskCache will create sub folders to place the layer image files automatically.
    
    Example:  
      root path :/tmp/stache
      layer : contact   (md5 value:2f8a6bf31f3bd67bd2d9720c58b19c9a)
      full path : /tmp/stache/9a/9c/contact/....
      
      "cache":
      {
        "class": "TileStache.Goodies.Caches.CustomPathDiskCache:Cache",
        "kwargs": 
        {
            "pattern": "**/**",
            "path": "/tmp/stache",
            "umask": "0000",
            "dirs": "portable",
            "gzip": ["xml", "json"]
        }
      }
"""


import os
import hashlib

from os.path import join as pathjoin
from TileStache.Caches import Disk

class Cache (Disk):
    def __init__(self, path, umask=0022, dirs='safe', gzip='txt text json xml'.split(), pattern='**/**'):
        Disk.__init__(self, path, umask, dirs, gzip)
        self.pattern = pattern
    
    def _fullpath(self, layer, coord, format):
        """
        """
        filepath = self._filepath(layer, coord, format)
        
        l = layer.name()
        
        md5_layer = hashlib.md5(l).hexdigest();
        pattern_list = self.pattern.split('/')
        folder_list = []
        index = 0 
        for i in range(0, len(pattern_list)):
            folder_length = len(pattern_list[i])
            
            if index == 0:
                folder_list.append(md5_layer[-folder_length:])
            else:
                folder_list.append(md5_layer[-(index + folder_length): - index])
            index = index + folder_length
        for j in folder_list:
            filepath = os.sep.join((j,filepath))
        
        fullpath = pathjoin(self.cachepath, filepath)

        return fullpath