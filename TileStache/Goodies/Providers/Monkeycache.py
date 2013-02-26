""" Monkeycache is a tile provider that reads data from an existing cache.

    Normally, TileStache creates new tiles at request-time and saves them to a
    cache for later visitors. Monkeycache supports a different workflow, where
    a cache is seeded ahead of time, and then only existing tiles are served
    from this cache.
    
    For example, you might have a TileStache configuration with a Mapnik
    provider, which requires PostGIS and other software to be installed on your
    system. Monkeycache would allow you to seed that cache into a directory of
    files or an MBTiles file on a system with a fast processor and I/O, and then
    serve the contents of the cache from another system with a faster network
    connection but no Mapnik or PostGIS.
    
    Two sample configurations:

    {
      "cache": {"name": "Disk", "path": "/var/cache"},
      "layers": 
      {
        "expensive-layer":
        {
          "provider": {"name": "Mapnik", "mapfile": "style.xml"}
        }
      }
    }
    
    {
      "cache": {"name": "Test"},
      "layers": 
      {
        "cheap-layer":
        {
          "provider":
          {
            "class": "TileStache.Goodies.Providers.Monkeycache:Provider",
            "kwargs":
            {
              "layer_name": "expensive-layer",
              "cache_config": {"name": "Disk", "path": "/var/cache"},
              "format": "PNG"
            }
          }
        }
      }
    }
"""

from TileStache.Config import buildConfiguration
from TileStache.Core import KnownUnknown

class CacheResponse:
    """ Wrapper class for Cache response that makes it behave like a PIL.Image object.
    
        TileStache.getTile() expects to be able to save one of these to a buffer.
        
        Constructor arguments:
        - body: Raw data pulled from cache.
        - format: File format to check against.
    """
    def __init__(self, body, format):
        self.body = body
        self.format = format
    
    def save(self, out, format):
        if format != self.format:
            raise KnownUnknown('Monkeycache only knows how to make %s tiles, not %s' % (self.format, format))
        
        out.write(self.body)

class Provider:
    """ Monkeycache Provider with source_layer, source_cache and tile_format attributes.
    
        Source_layer is an instance of TileStache.Core.Layer.
        Source_cache is a valid TileStache Cache provider.
        Tile_format is a string.
    """
    def __init__(self, layer, cache_config, layer_name, format='PNG'):
        """ Initialize the Monkeycache Provider.
        
            Cache_config is a complete cache configuration dictionary that you
            might use in a TileStache setup (http://tilestache.org/doc/#caches).
            This is where Monkeycache will look for already-rendered tiles.
            
            Layer_name is the name of a layer saved in that cache.
        
            Format should match the second return value of your original
            layer's getTypeByExtention() method, e.g. "PNG", "JPEG", or for
            the Vector provider "GeoJSON" and others. This might not necessarily
            match the file name extension, though common cases like "jpg"/"JPEG"
            are accounted for.
        """
        fake_layer_dict = {'provider': {'name': 'Proxy', 'url': 'http://localhost/{Z}/{X}/{Y}.png'}}
        fake_config_dict = {'cache': cache_config, 'layers': {layer_name: fake_layer_dict}}
        fake_config = buildConfiguration(fake_config_dict, layer.config.dirpath)
        
        self.source_layer = fake_config.layers[layer_name]
        self.source_cache = fake_config.cache
        
        formats = dict(png='PNG', jpg='JPEG', jpeg='JPEG')
        self.tile_format = formats.get(format.lower(), format)

    def renderTile(self, width, height, srs, coord):
        """ Pull a single tile from self.source_cache.
        """
        body = self.source_cache.read(self.source_layer, coord, self.tile_format)
        return ResponseWrapper(body, self.tile_format)
