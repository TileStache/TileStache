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

class DynamicLayers:
	
	def __init__(self, config, url_root, dirpath):
		self.config = config
		self.url_root = url_root
		self.dirpath = dirpath
		self.seen_layers = {}
	
	def keys(self):
		return self.seen_layers.keys()
	
	def items(self):
		return self.seen_layers.items()
	
	def __contains__(self, key):
		res = urlopen(self.url_root + "/layer/" + key)
		return res.getcode() != 404
	
	def __getitem__(self, key):
		logging.debug("Requesting layer %s", self.url_root + "/layer/" + key)
		res = urlopen(self.url_root + "/layer/" + key)
		if (res.getcode() == 404) :
			raise TileStache.KnownUnknown("Layer %s not found", key)
		layer_dict = json_load(res)
		logging.debug("Got layer_obj %s", layer_dict)
		layer = TileStache.Config._parseConfigfileLayer(layer_dict, self.config, self.dirpath)
		self.seen_layers[key] = layer
		return layer

class ExternalConfiguration:
	
	def __init__(self, url_root, cache_dict, dirpath):
		self.cache = TileStache.Config._parseConfigfileCache(cache_dict, dirpath)
		self.dirpath = dirpath
		self.layers = DynamicLayers(self, url_root, dirpath)

class WSGIServer (TileStache.WSGITileServer):
	
	"""
		Wrap WSGI application, passing it a custom configuration.
		
		The WSGI application is an instance of TileStache:WSGITileServer.
		
		This method is initiated with a url_root that contains the scheme, host, port
		and path that must prefix the API calls on our local server.  Any valid http
		or https urls should work.
	"""
	
	def __init__(self, url_root, debug_level="DEBUG"):
		logging.basicConfig(level=debug_level)
		
		# Call API server at url to grab cache_dict
		cache_dict = json_load(urlopen(url_root + "/cache"))
		
		dirpath = '/tmp/stache'
		
		config = ExternalConfiguration(url_root, cache_dict, dirpath)
		
		TileStache.WSGITileServer.__init__(self, config, False)
	
	def __call__(self, environ, start_response):
		response = TileStache.WSGITileServer.__call__(self, environ, start_response)
		return response
