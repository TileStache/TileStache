# This Python file uses the following encoding: utf-8

from unittest import TestCase
from . import utils

class ProviderTests(TestCase):
    '''Tests Proxy Provider that reads from cfg file'''

    def test_proxy_mercator(self):
        '''Fetch tile from OSM using Proxy provider (web mercator)'''

        config_file_content = '''
        {
           "layers":{
              "osm":{
                 "provider":{
                    "name":"proxy",
                    "url": "http://tile.openstreetmap.org/{Z}/{X}/{Y}.png"
                 }
              }
            },
            "cache": {
                "name": "Test"
            }
        }
        '''

        tile_mimetype, tile_content = utils.request(config_file_content, "osm", "png", 0, 0, 0)
        self.assertEqual(tile_mimetype, "image/png")
        self.assertTrue(tile_content[:4] in '\x89\x50\x4e\x47') #check it is a png based on png magic number


    def test_url_template_wgs84(self):
        '''Fetch two WGS84 tiles from WMS using bbox'''

        config_file_content = '''
        {
           "layers":{
              "osgeo_wms":{
                 "projection":"WGS84",
                 "provider":{
                    "name":"url template",
                    "template":"http://vmap0.tiles.osgeo.org/wms/vmap0?LAYERS=basic&SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&STYLES=&FORMAT=image%2Fpng&SRS=EPSG%3A4326&BBOX=$xmin,$ymin,$xmax,$ymax&WIDTH=256&HEIGHT=256"
                 }
              }
            },
            "cache": {
                "name": "Test"
            }
        }
        '''

        tile_mimetype, tile_content = utils.request(config_file_content, "osgeo_wms", "png", 0, 0, 0)
        self.assertEqual(tile_mimetype, "image/png")
        self.assertTrue(tile_content[:4] in '\x89\x50\x4e\x47') #check it is a png based on png magic number

        #in WGS84 we typically have two tiles at zoom level 0. Get the second tile
        tile_mimetype, tile_content = utils.request(config_file_content, "osgeo_wms", "png", 0, 1, 0)
        self.assertEqual(tile_mimetype, "image/png")
        self.assertTrue(tile_content[:4] in '\x89\x50\x4e\x47') #check it is a png based on png magic number


class ProviderWithDummyResponseServer(TestCase):
    '''
    The following test starts a new Dummy Response Server and does some checks.
    The reason it is in a separate class is because we want to make sure that the setup and teardown
    methods - ***which are specific to this test*** - get called.
    '''

    def setUp(self):
        #create custom binary file that pretends to be a png and a server that always returns the same response
        self.response_content = '\x89\x50\x4e\x47Meh, I am a custom file that loves utf8 chars like éøæ®!!!'
        self.response_mimetype = 'image/png'

        self.temp_file_name = utils.create_temp_file(self.response_content)
        self.server_process, self.server_port = utils.create_dummy_server(self.temp_file_name, self.response_mimetype)

    def tearDown(self):
        self.server_process.kill()

    def test_url_template_custom_binary(self):
        '''Fetch custom binary result using URL Template(result should not be modified)'''

        config_file_content = '''
        {
           "layers":{
              "local_layer":{
                 "projection":"WGS84",
                 "provider":{
                    "name":"url template",
                    "template":"http://localhost:<<port>>/&BBOX=$xmin,$ymin,$xmax,$ymax"
                 }
              }
            },
            "cache": {
                "name": "Test"
            }
        }
        '''.replace('<<port>>', str(self.server_port))

        tile_mimetype, tile_content = utils.request(config_file_content, "local_layer", "png", 0, 0, 0)

        self.assertEquals(tile_mimetype, self.response_mimetype)
        self.assertEquals(tile_content, self.response_content)
