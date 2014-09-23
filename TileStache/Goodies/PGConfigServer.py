""" ExternalConfigServer is a replacement for WSGITileServer that uses external
    configuration fetched via HTTP to service all config requests.
    
    Example usage, with gunicorn (http://gunicorn.org):
      
      gunicorn --bind localhost:8888 "TileStache.Goodies.ExternalConfigServer:WSGIServer(url)"
"""

from urllib import urlopen
import logging

try:
	from json import load as json_load
except ImportError:
	from simplejson import load as json_load

import TileStache


class DBLayers:

    @staticmethod
    def query_db(query, results='all'):
        cursor = self.connection.cursor()
        cursor.execute(select_keys_query)
        if results == 'all':
            result = cursor.fetchall()
        cursor.close()
        return result

    def __init__(self, db_connection_dict, config_name='default'):
        self.connection = psycopg2.connect(**db_connection_dict)
        self.cursor = self.db_connection.cursor()

    def keys(self):
        # return a list of key strings
        return self.query_db("SELECT key FROM tilestache_layer;")

    def items(self):
        # return a list of (key, layer) tuples
        return self.query_db("SELECT key, layer FROM tilestache_layer;")

    def __contains__(self, key):
        result = self.query_db("SELECT COUNT(key) FROM tilestache_layer WHERE key={0};".format(key), results='one')
        # return True if the key is here
        return result[0] == True

    def __getitem__(self, key):
        # return the layer named by the key
        return self.query_db("SELECT layer FROM tilestache_layer WHERE key={0}".format(key))[0]


class PGConfiguration:

    def __init__(self, db_connection_dict, dirpath):
        self.db_connection = psycopg2.connect(**db_connection_dict)

        cache_dict = self.get_cache_dict(config_name)
        self.cache = TileStache.Config._parseConfigfileCache(cache_dict, dirpath)
        self.dirpath = dirpath
        self.layers = DBLayers(self, url_root, cache_responses, dirpath)


    def get_cache_dict(self, config_name):
        self.cursor.execute("SELECT cache FROM tilestache_config WHERE name={0}".format(config_name))
        config_singleton = self.cursor.fetchone()[0]
        return config_singleton


class WSGIServer (TileStache.WSGITileServer):
	
	"""
		Wrap WSGI application, passing it a custom configuration.
		
		The WSGI application is an instance of TileStache:WSGITileServer.
		
		This method is initiated with a url_root that contains the scheme, host, port
		and path that must prefix the API calls on our local server.  Any valid http
		or https urls should work.
		
		The cache_responses parameter tells TileStache to cache all responses from
		the configuration server.
	"""
	
	def __init__(self, db_connection_str, debug_level="DEBUG"):
		logging.basicConfig(level=debug_level)

		db_connection_dict = db_connection_str.split(' ')
		# Call API server at url to grab cache_dict
		cache_dict = json_load(urlopen(url_root + "/cache"))
		
		dirpath = '/tmp/stache'
		
		config = PGConfiguration(db_connection_dict)
		
		TileStache.WSGITileServer.__init__(self, config, False)
	
	def __call__(self, environ, start_response):
		response = TileStache.WSGITileServer.__call__(self, environ, start_response)
		return response
