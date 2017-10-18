""" ExternalConfigServer is a replacement for WSGITileServer that uses external
    configuration fetched via HTTP to service all config requests.

    Example usage, with gunicorn (http://gunicorn.org):

      gunicorn --bind localhost:8888 "TileStache.Goodies.ExternalConfigServer:WSGIServer(url)"
"""

import logging

try:
	from json import load as json_load
except ImportError:
	from simplejson import load as json_load

from TileStache.py3_compat import urlopen

import TileStache

class DynamicLayers:

	def __init__(self, config, url_root, cache_responses, dirpath):
		self.config = config
		self.url_root = url_root
		self.dirpath = dirpath
		self.cache_responses = cache_responses;
		self.seen_layers = {}
		self.lookup_failures = set()

	def keys(self):
		return self.seen_layers.keys()

	def items(self):
		return self.seen_layers.items()

	def parse_layer(self, layer_json):
		layer_dict = json_load(layer_json)
		return TileStache.Config._parseConfigLayer(layer_dict, self.config, self.dirpath)

	def __contains__(self, key):
		# If caching is enabled and we've seen a request for this layer before, return True unless
		# the prior lookup failed to find this layer.
		if self.cache_responses:
			if key in self.seen_layers:
				return True
			elif key in self.lookup_failures:
				return False

		res = urlopen(self.url_root + "/layer/" + key)

		if self.cache_responses:
			if res.getcode() != 200:
				# Cache a failed lookup
				self.lookup_failures.add(key)
			else :
				# If lookup succeeded and we are caching, parse the layer now so that a subsequent
				# call to __getitem__ doesn't require a call to the config server.  If we aren't
				# caching, we skip this step to avoid an unnecessary json parse.
				try:
					self.seen_layers[key] = self.parse_layer(res)
				except ValueError:
					# The JSON received by the config server was invalid.  Treat this layer as a
					# failure.  We don't want to raise ValueError from here because other parts
					# of TileStache are just expecting a boolean response from __contains__
					logging.error("Invalid JSON response seen for %s", key)
					self.lookup_failures.add(key)
					return False

		if res.getcode() != 200:
			logging.info("Config response code %s for %s", res.getcode(), key)
		return res.getcode() == 200

	def __getitem__(self, key):
		if self.cache_responses:
			if key in self.seen_layers:
				return self.seen_layers[key]
			elif key in self.lookup_failures:
				# If we are caching, raise KnownUnknown if we have previously failed to find this layer
				raise TileStache.KnownUnknown("Layer %s previously not found", key)

		logging.debug("Requesting layer %s", self.url_root + "/layer/" + key)
		res = urlopen(self.url_root + "/layer/" + key)
		if (res.getcode() != 200) :
			logging.info("Config response code %s for %s", res.getcode(), key)
			if (self.cache_responses) :
				self.lookup_failures.add(key)
			raise TileStache.KnownUnknown("Layer %s not found", key)

		try :
			layer = self.parse_layer(res)
			self.seen_layers[key] = layer
			return layer
		except ValueError:
			logging.error("Invalid JSON response seen for %s", key)
			if (self.cache_responses) :
				# If caching responses, cache this failure
				self.lookup_failures.add(key)
			# KnownUnknown seems like the appropriate thing to raise here since this is akin
			# to a missing configuration.
			raise TileStache.KnownUnknown("Failed to parse JSON configuration for %s", key)

class ExternalConfiguration:

	def __init__(self, url_root, cache_dict, cache_responses, dirpath):
		self.cache = TileStache.Config._parseConfigCache(cache_dict, dirpath)
		self.dirpath = dirpath
		self.layers = DynamicLayers(self, url_root, cache_responses, dirpath)

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

	def __init__(self, url_root, cache_responses=True, debug_level="DEBUG"):
		logging.basicConfig(level=debug_level)

		# Call API server at url to grab cache_dict
		cache_dict = json_load(urlopen(url_root + "/cache"))

		dirpath = '/tmp/stache'

		config = ExternalConfiguration(url_root, cache_dict, cache_responses, dirpath)

		TileStache.WSGITileServer.__init__(self, config, False)

	def __call__(self, environ, start_response):
		response = TileStache.WSGITileServer.__call__(self, environ, start_response)
		return response
