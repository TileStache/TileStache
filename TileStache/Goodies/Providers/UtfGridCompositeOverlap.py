import json
import TileStache
from TileStache.Core import KnownUnknown

class Provider:
  
  def __init__(self, layer, stack, layer_id=None, wrapper=None):
    #Set up result storage
    self.resultGrid = []
    self.gridKeys = []
    self.gridData = {}
    
    self.layer = layer
    self.stack = stack
    self.layer_id = layer_id
    self.wrapper = wrapper
    self.curId = 0

  def renderTile(self, width, height, srs, coord):
    for l in self.stack:
      self.addLayer(l, coord)
    return SaveableResponse(self.writeResult())

  def getTypeByExtension(self, extension):
    """ Get mime-type and format by file extension.
      This only accepts "json".
    """
    if extension.lower() != 'json':
      raise KnownUnknown('UtfGridComposite only makes .json tiles, not "%s"' % extension)
    
    return 'text/json', 'JSON'

  def addLayer( self, layerDef, coord ):
    layer = TileStache.getTile(self.layer.config.layers[layerDef['src']], coord, 'JSON')[1]

    if layerDef['wrapper'] == None:
      layer = json.loads(layer)
    else:
      # Strip "Wrapper(...)"
      layer = json.loads(layer[(len(layerDef['wrapper'])+1):-1])

    grid_size = len(layer['grid'])

    # Init resultGrid based on given layers (if required)
    if len(self.resultGrid) == 0:
      for i in xrange(grid_size):
        self.resultGrid.append([])
        for j in xrange(grid_size):
          self.resultGrid[i].append(-1)

    layer_keys = layer['keys']

    for y in xrange(grid_size):
      line = layer['grid'][y]
      for x in xrange(grid_size):
        src_id = self.decodeId(line[x])
        
        if layer_keys[src_id] == "":
          continue

        src_key = layer_keys[src_id]

        # Add layer name attribute
        if layerDef['layer_id'] != None and self.layer_id != None:
          layer['data'][src_key][self.layer_id] = layerDef['layer_id']

        if self.resultGrid[x][y] == -1:
          cur_id = self.curId
          self.curId += 1
          cur_key = json.dumps(cur_id)

          # Set key for current point.
          self.resultGrid[x][y] = self.encodeId(cur_id)
          self.gridKeys.insert(cur_id + 1, cur_key)

          # Initialize data bucket.
          self.gridData[cur_key] = []

        else:
          cur_id = self.decodeId(self.resultGrid[x][y])
          cur_key = json.dumps(cur_id)

        self.gridData[cur_key].append(layer['data'][src_key])

  def writeResult( self ):
    result = "{\"keys\": ["
    for i in xrange(len(self.gridKeys)):
      if i > 0:
        result += ","
      result += "\"" + self.gridKeys[i] + "\""
  
    result += "], \"data\": { "
    
    first = True
    for key in self.gridData:
      if not first:
        result += ","
      first = False
      result += "\"" + key + "\": " + json.dumps(self.gridData[key]) + ""
    
    result += "}, \"grid\": ["
    
    grid_size = len(self.resultGrid)
    first = True
    for y in xrange(grid_size):
      line = ""

      for x in xrange(grid_size):
        if self.resultGrid[x][y] == -1:
          self.resultGrid[x][y] = ' '

        line = line + self.resultGrid[x][y]

      if not first:
        result += ","
      first = False

      result += json.dumps(line)

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
      raise KnownUnknown('UtfGridCompositeOverlap only saves .json tiles, not "%s"' % format)
    out.write(self.content)

