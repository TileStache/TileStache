""" The core class bits of TileStache.

Two important classes can be found here.

Layer represents a set of tiles in TileStache. It keeps references to
providers, projections, a Configuration instance, and other details required
for to the storage and rendering of a tile set. Layers are represented in the
configuration file as a dictionary:

    {
      "cache": ...,
      "layers": 
      {
        "example-name":
        {
            "provider": { ... },
            "metatile": { ... },
            "stale lock timeout": ...,
            "projection": ...
        }
      }
    }

- "provider" refers to a Provider, explained in detail in TileStache.Providers.
- "metatile" optionally makes it possible for multiple individual tiles to be
  rendered at one time, for greater speed and efficiency. This is commonly used
  for the Mapnik provider. See below for more information on metatiles.
- "projection" names a geographic projection, explained in TileStache.Geography.
  If omitted, defaults to spherical mercator.
- "stale lock timeout" is an optional number of seconds to wait before forcing
  a lock that might be stuck. This is defined on a per-layer basis, rather than
  for an entire cache at one time, because you may have different expectations
  for the rendering speeds of different layer configurations. Defaults to 15.

The public-facing URL of a single tile for this layer might look like this:

    http://example.com/tilestache.cgi/example-name/0/0/0.png

Metatile represents a larger area to be rendered at one time. Metatiles are
represented in the configuration file as a dictionary:

    {
        "rows": 4,
        "columns": 4,
        "buffer": 64
    }

- "rows" and "columns" are the height and width of the metatile measured in
  tiles. This example metatile is four rows tall and four columns wide, so it
  will render sixteen tiles simultaneously.
- "buffer" is a buffer area around the metatile, measured in pixels. This is
  useful for providers with labels or icons, where it's necessary to draw a
  bit extra around the edges to ensure that text is not cut off. This example
  metatile has a buffer of 64 pixels, so the resulting metatile will be 1152
  pixels square: 4 rows x 256 pixels + 2 x 64 pixel buffer.
"""

from StringIO import StringIO

from ModestMaps.Core import Coordinate

class Metatile:
    """ Some basic characteristics of a metatile.
    
        Properties:
        - rows: number of tile rows this metatile covers vertically.
        - columns: number of tile columns this metatile covers horizontally.
        - buffer: pixel width of outer edge.
    """
    def __init__(self, buffer=0, rows=1, columns=1):
        assert rows >= 1
        assert columns >= 1
        assert buffer >= 0

        self.rows = rows
        self.columns = columns
        self.buffer = buffer

    def isForReal(self):
        """ Return True if this is really a metatile with a buffer or multiple tiles.
        
            A default 1x1 metatile with buffer=0 is not for real.
        """
        return self.buffer > 0 or self.rows > 1 or self.columns > 1

    def firstCoord(self, coord):
        """ Return a new coordinate for the upper-left corner of a metatile.
        
            This is useful as a predictable way to refer to an entire metatile
            by one of its sub-tiles, currently needed to do locking correctly.
        """
        return self.allCoords(coord)[0]

    def allCoords(self, coord):
        """ Return a list of coordinates for a complete metatile.
        
            Results are guaranteed to be ordered left-to-right, top-to-bottom.
        """
        rows, columns = int(self.rows), int(self.columns)
        
        # upper-left corner of coord's metatile
        row = rows * (int(coord.row) / rows)
        column = columns * (int(coord.column) / columns)
        
        coords = []
        
        for r in range(rows):
            for c in range(columns):
                coords.append(Coordinate(row + r, column + c, coord.zoom))

        return coords

class Layer:
    """ A Layer.
    
        Properties:
        - provider: render provider, see Providers module.
        - config: Configuration instance, see Config module.
        - projection: geographic projection, see Geography module.
        - metatile: some information on drawing many tiles at once.
        - stale_lock_timeout: number of seconds until a cache lock is forced.
    """
    def __init__(self, config, projection, metatile, stale_lock_timeout=15):
        self.provider = None
        self.config = config
        self.projection = projection
        self.metatile = metatile
        
        self.stale_lock_timeout = stale_lock_timeout

    def name(self):
        """ Figure out what I'm called, return a name if there is one.
        """
        for (name, layer) in self.config.layers.items():
            if layer is self:
                return name

        return None

    def doMetatile(self):
        """ Return True if we have a real metatile and the provider is OK with it.
        """
        return self.metatile.isForReal() and self.provider.metatileOK
    
    def render(self, coord, format):
        """ Render a tile for a coordinate, return PIL Image-like object.
        
            Perform metatile slicing here as well, if required, writing the
            full set of rendered tiles to cache as we go.
        """
        srs = self.projection.srs
        xmin, ymin, xmax, ymax = self.envelope(coord)
        width, height = 256, 256
        
        provider = self.provider
        metatile = self.metatile
        
        if self.doMetatile():
            # adjust render size and coverage for metatile
            xmin, ymin, xmax, ymax = self.metaEnvelope(coord)
            width, height = self.metaSize(coord)

            subtiles = self.metaSubtiles(coord)
        
        if not self.doMetatile() and hasattr(provider, 'renderTile'):
            # draw a single tile
            tile = provider.renderTile(256, 256, srs, coord)

        elif hasattr(provider, 'renderArea'):
            # draw an area, defined in projected coordinates
            tile = provider.renderArea(width, height, srs, xmin, ymin, xmax, ymax)

        else:
            raise Exception('Your provider lacks renderTile and renderArea methods')

        assert hasattr(tile, 'save'), \
               'Return value of provider.renderArea() must act like an image.'
        
        if self.doMetatile():
            # tile will be set again later
            tile, surtile = None, tile
            
            for (other, x, y) in subtiles:
                buff = StringIO()
                bbox = (x, y, x + 256, y + 256)
                subtile = surtile.crop(bbox)
                subtile.save(buff, format)
                body = buff.getvalue()
                
                self.config.cache.save(body, self, other, format)
                
                if other == coord:
                    # the one that actually gets returned
                    tile = subtile
        
        return tile

    def envelope(self, coord):
        """ Projected rendering envelope (xmin, ymin, xmax, ymax) for a Coordinate.
        """
        ul = self.projection.coordinateProj(coord)
        lr = self.projection.coordinateProj(coord.down().right())
        
        return min(ul.x, lr.x), min(ul.y, lr.y), max(ul.x, lr.x), max(ul.y, lr.y)
    
    def metaEnvelope(self, coord):
        """ Projected rendering envelope (xmin, ymin, xmax, ymax) for a metatile.
        """
        # size of buffer expressed as fraction of tile size
        buffer = float(self.metatile.buffer) / 256
        
        # full set of metatile coordinates
        coords = self.metatile.allCoords(coord)
        
        # upper-left and lower-right expressed as fractional coordinates
        ul = coords[0].left(buffer).up(buffer)
        lr = coords[-1].right(1 + buffer).down(1 + buffer)

        # upper-left and lower-right expressed as projected coordinates
        ul = self.projection.coordinateProj(ul)
        lr = self.projection.coordinateProj(lr)
        
        # new render area coverage in projected coordinates
        return min(ul.x, lr.x), min(ul.y, lr.y), max(ul.x, lr.x), max(ul.y, lr.y)
    
    def metaSize(self, coord):
        """ Pixel width and height of full rendered image for a metatile.
        """
        # size of buffer expressed as fraction of tile size
        buffer = float(self.metatile.buffer) / 256
        
        # new master image render size
        width = int(256 * (buffer * 2 + self.metatile.columns))
        height = int(256 * (buffer * 2 + self.metatile.rows))
        
        return width, height

    def metaSubtiles(self, coord):
        """ List of all coords in a metatile and their x, y offsets in a parent image.
        """
        subtiles = []

        coords = self.metatile.allCoords(coord)

        for other in coords:
            r = other.row - coords[0].row
            c = other.column - coords[0].column
            
            x = c * 256 + self.metatile.buffer
            y = r * 256 + self.metatile.buffer
            
            subtiles.append((other, x, y))

        return subtiles
