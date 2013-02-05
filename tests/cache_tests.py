from unittest import TestCase
from . import utils
import memcache

class CacheTests(TestCase):
    '''Tests various Cache configurations that reads from cfg file'''

    def setUp(self):
        self.mc = memcache.Client(['127.0.0.1:11211'], debug=0)
        self.mc.flush_all()

    def test_memcache(self):
        '''Fetch tile and check the existence in memcached'''

        config_file_content = '''
        {
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
        '''

        tile_mimetype, tile_content = utils.request(config_file_content, "memcache_osm", "png", 0, 0, 0)
        self.assertEqual(tile_mimetype, "image/png")

        self.assertEqual(self.mc.get('/4/memcache_osm/0/0/0.PNG'), tile_content,
            'Contents of memcached and value returned from TileStache do not match')

    def test_memcache_keyprefix(self):
        '''Fetch tile and check the existence of key with prefix in memcached'''

        config_file_content = '''
        {
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
                "revision": 1,
                "key prefix" : "cool_prefix"
            }
        }
        '''

        tile_mimetype, tile_content = utils.request(config_file_content, "memcache_osm", "png", 0, 0, 0)
        self.assertEqual(tile_mimetype, "image/png")

        self.assertEqual(self.mc.get('cool_prefix/1/memcache_osm/0/0/0.PNG'), tile_content,
            'Contents of memcached and value returned from TileStache do not match')

        self.assertEqual(self.mc.get('/1/memcache_osm/0/0/0.PNG'), None,
            'Memcache returned a value even though it should have been empty')





