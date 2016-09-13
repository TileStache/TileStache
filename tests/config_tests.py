from unittest import TestCase
from TileStache import Core, parseConfig

class ConfigTests(TestCase):

    def test_config(self):
        '''Read configuration and verify successful read'''

        config_content = {
           "layers":{
              "memcache_osm":{
                 "provider":{
                    "name":"proxy",
                    "url": "http://tile.openstreetmap.org/{Z}/{X}/{Y}.png"
                 }
              }
            },
            "cache": {
                "name": "Memcache",
                "servers": ["127.0.0.1:11211"],
                "revision": 4
            }
        }

        config = parseConfig(config_content)
        self.assertEqual(config.cache.servers, ["127.0.0.1:11211"])
        self.assertEqual(config.cache.revision, 4)
        self.assertTrue(config.layers['memcache_osm'])
        self.assertTrue(isinstance(config.layers['memcache_osm'], Core.Layer))

    def test_config_mapnik_string(self):
        '''Read configuration and pass mapnik configuration as string'''

        mapnik_config = '''
            <?xml version="1.0"?>
            <Map font-directory="./fonts" srs="+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0.0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs +over">
            <Layer name="raster-layer" srs="+proj=cea +lon_0=-117.333333333333 +lat_ts=33.75 +x_0=0 +y_0=0 +datum=NAD27 +units=m +no_defs " status="on">
                <StyleName>raster-style</StyleName>
                <Datasource>
                    <Parameter name="type">gdal</Parameter>
                    <Parameter name="file">cea.tif</Parameter>
                    <Parameter name="format">tiff</Parameter>
                </Datasource>
            </Layer>
            <Style name="raster-style">
                <Rule>
                    <RasterSymbolizer/>
                </Rule>
            </Style>
            </Map>'''

        config_content = {
            "cache": {
                "name": "Test",
                "path": "/tmp/stache",
                "umask": "0000"
            },
            "layers": {
                "geotiff": {
                    "provider": {"name": "mapnik", "mapfile": mapnik_config},
                    "projection": "spherical mercator"
                }
            }
        }

        config = parseConfig(config_content)
        self.assertTrue(config.layers['geotiff'])
        self.assertTrue(isinstance(config.layers['geotiff'], Core.Layer))