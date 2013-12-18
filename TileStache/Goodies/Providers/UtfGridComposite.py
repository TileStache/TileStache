""" Composite Provider for UTFGrid layers
https://github.com/mapbox/utfgrid-spec/blob/master/1.2/utfgrid.md

Combines multiple UTFGrid layers to create a single result.
The given layers will be added to the result in the order they are given.
Therefore the last one will have the highest priority.

Sample configuration:
	"provider":
	{
		"class": "TileStache.Goodies.Providers.UtfGridComposite:Provider",
		"kwargs":
		{
			"stack":
			[
				{ "layer_id": "layer1", "src": "my_utf_layer1", "wrapper": "grid" },
				{ "layer_id": "layer2", "src": "my_utf_layer2", "wrapper": "grid" }
			],
			"layer_id": "l",
			"wrapper": "grid"
		}
	}

stack: list of layers (and properties) to composite together
	layer_id: an id attribute that will be added to each json data object for this layer: { "layer_id": "layer1", "name": "blah", "address": "something"}
	src: layer name of the layer to composite
	wrapper: the wrapper definition of this layer if there is one (so we can remove it)
layer_id: the key for the layer_id attribute that is added to each data object: { "l": "layer1", ...}
wrapper: wrapper to add to the resulting utfgrid "WRAPPER({...})". Usually "grid"

if layer_id is not set in the layer or the provider config then it will not be set on data objects
"""

import json
import TileStache
from TileStache.Core import KnownUnknown

class Provider:
	
	def __init__(self, layer, stack, layer_id=None, wrapper=None):

		#Set up result storage
		
		self.layer = layer
		self.stack = stack
		self.layer_id = layer_id
		self.wrapper = wrapper
	
	def renderTile(self, width, height, srs, coord):

		resultGrid = []
		gridKeys = []
		gridData = {}
		
		for l in self.stack:
			self.addLayer(resultGrid, gridKeys, gridData, l, coord)
		return SaveableResponse(self.writeResult(resultGrid, gridKeys, gridData))

	def getTypeByExtension(self, extension):
		""" Get mime-type and format by file extension.
			This only accepts "json".
		"""
		if extension.lower() != 'json':
			raise KnownUnknown('UtfGridComposite only makes .json tiles, not "%s"' % extension)
		
		return 'text/json', 'JSON'

	def addLayer( self, resultGrid, gridKeys, gridData, layerDef, coord ):
		
		mime, layer = TileStache.getTile(self.layer.config.layers[layerDef['src']], coord, 'JSON')
#		raise KnownUnknown(layer)
		if layerDef['wrapper'] == None:
			layer = json.loads(layer)
		else:
			layer = json.loads(layer[(len(layerDef['wrapper'])+1):-1]) #Strip "Wrapper(...)"
		
		gridSize = len(layer['grid'])

		#init resultGrid based on given layers (if required)
		if len(resultGrid) == 0:
			for i in xrange(gridSize):
				resultGrid.append([])
				for j in xrange(gridSize):
					resultGrid[i].append(-1)
	
		keys = layer['keys']
		
		keyRemap = {}
		for k in keys:
			if k in gridKeys:
				for ext in xrange(ord('a'), ord('z')+1):
					if not k+chr(ext) in gridKeys:
						keyRemap[k] = (k+chr(ext))
						break
				if not k in keyRemap:
					raise Error("Couldn't remap")
		
		addedKeys = [] #FIXME: HashSet<string>?
		
		for y in xrange(gridSize):
			line = layer['grid'][y]
			for x in xrange(gridSize):
				idNo = self.decodeId(line[x])
				
				if keys[idNo] == "":
					continue
				
				key = keys[idNo]
				if keys[idNo] in keyRemap:
					key = keyRemap[keys[idNo]]
				
				if not key in addedKeys:
					gridKeys.append(key)
					addedKeys.append(key)
					if layerDef['layer_id'] != None and self.layer_id != None: #Add layer name attribute
						layer['data'][keys[idNo]][self.layer_id] = layerDef['layer_id']
					gridData[key] = layer['data'][keys[idNo]]
						
						
				newId = gridKeys.index(key)
				
				resultGrid[x][y] = newId

	def writeResult( self, resultGrid, gridKeys, gridData ):
		gridSize = len(resultGrid)
	
		finalKeys = []
		finalData = {}
		finalGrid = []
		for i in xrange(gridSize):
			finalGrid.append("")
		
		finalIdCounter = 0
		idToFinalId = {}
		
		for y in xrange(gridSize):
			for x in xrange(gridSize):
				id = resultGrid[x][y]
				
				if not id in idToFinalId:
					idToFinalId[id] = finalIdCounter
					finalIdCounter = finalIdCounter + 1
					
					if id == -1:
						finalKeys.append("")
					else:
						finalKeys.append(gridKeys[id])
						finalData[gridKeys[id]] = gridData[gridKeys[id]]
				
				finalId = idToFinalId[id]
				finalGrid[y] = finalGrid[y] + self.encodeId(finalId)
	
		result = "{\"keys\": ["
		for i in xrange(len(finalKeys)):
			if i > 0:
				result += ","
			result += "\"" + finalKeys[i] + "\""
	
		result += "], \"data\": { "
		
		first = True
		for entry in gridData:
			if not first:
				result += ","
			first = False
			result += "\"" + entry + "\": " + json.dumps(gridData[entry]) + ""
		
		result += "}, \"grid\": ["
		
		for i in xrange(gridSize):
			line = finalGrid[i]
			result += json.dumps(line)
			if i < gridSize - 1:
				result += ","
		
		if self.wrapper == None:
			return result + "]}"
		else:
			return self.wrapper + "(" + result + "]})"

	def encodeId ( self, id ):
		id += 32
		if id >= 34:
			id = id + 1
		if id >= 92:
			id = id + 1
		if id > 127:
			return unichr(id)
		return chr(id)

	def decodeId( self, id ):
		id = ord(id)
		
		if id >= 93:
			id = id - 1
		if id >= 35:
			id = id - 1
		return id - 32


class SaveableResponse:
	""" Wrapper class for JSON response that makes it behave like a PIL.Image object.
		TileStache.getTile() expects to be able to save one of these to a buffer.
	"""
	def __init__(self, content):
		self.content = content
	def save(self, out, format):
		if format != 'JSON':
			raise KnownUnknown('MapnikGrid only saves .json tiles, not "%s"' % format)
		out.write(self.content)
