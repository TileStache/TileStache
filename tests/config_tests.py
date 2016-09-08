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