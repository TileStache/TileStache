from sqlite3 import connect
from urlparse import urlparse, urljoin
from os.path import exists

def create_tileset(filename, name, type, version, description, format, bounds=None):
    """ Create a tileset 1.1 with the given filename and metadata.
    
        From the documentation:

        The metadata table is used as a key/value store for settings.
        Five keys are required:

        name:
          The plain-english name of the tileset.

        type:
          overlay or baselayer
        
        version:
          The version of the tileset, as a plain number.

        description:
          A description of the layer as plain text.
        
        format:
          The image file format of the tile data: png or jpg
        
        One row in metadata is suggested and, if provided, may enhance performance.

        bounds:
          The maximum extent of the rendered map area. Bounds must define
          an area covered by all zoom levels. The bounds are represented in
          WGS:84 - latitude and longitude values, in the OpenLayers Bounds
          format - left, bottom, right, top. Example of the full earth:
          -180.0,-85,180,85.
    """
    if format not in ('png', 'jpg'):
        raise Exception('Format must be one of "png" or "jpg", not "%s"' % format)
    
    db = connect(filename)
    
    db.execute('CREATE TABLE metadata (name TEXT, value TEXT, PRIMARY KEY (name))')
    db.execute('CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB)')
    db.execute('CREATE UNIQUE INDEX coord ON tiles (zoom_level, tile_column, tile_row)')
    
    db.execute('INSERT INTO metadata VALUES (?, ?)', ('name', name))
    db.execute('INSERT INTO metadata VALUES (?, ?)', ('type', type))
    db.execute('INSERT INTO metadata VALUES (?, ?)', ('version', version))
    db.execute('INSERT INTO metadata VALUES (?, ?)', ('description', description))
    db.execute('INSERT INTO metadata VALUES (?, ?)', ('format', format))
    
    if bounds is not None:
        db.execute('INSERT INTO metadata VALUES (?, ?)', ('bounds', bounds))
    
    db.commit()
    db.close()

def tileset_exists(filename):
    """ Return true if the tileset exists and appears to have the right tables.
    """
    if not exists(filename):
        return False
    
    # this always works
    db = connect(filename)
    
    try:
        db.execute('SELECT name, value FROM metadata LIMIT 1')
        db.execute('SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles LIMIT 1')
    except:
        return False
    
    return True

def get_tile(filename, coord):
    """
    """
    db = connect(filename)
    
    formats = {'png': 'image/png', 'jpg': 'image/jpeg', None: None}
    format = db.execute("SELECT value FROM metadata WHERE name='format'").fetchone()
    format = format and format[0] or None
    mime_type = formats[format]
    
    tile_row = (2**coord.zoom - 1) - coord.row # Hello, Paul Ramsey.
    q = 'SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?'
    content = db.execute(q, (coord.zoom, coord.column, tile_row)).fetchone()
    content = content and content[0] or None

    return mime_type, content

class Provider:
    """
    """
    def __init__(self, layer, tileset):
        """
        """
        sethref = urljoin(layer.config.dirpath, tileset)
        scheme, h, path, q, p, f = urlparse(sethref)
        
        if scheme not in ('file', ''):
            raise Exception('Bad scheme in MBTiles provider: "%s"' % scheme)
        
        self.tileset = path
        self.layer = layer
    
    def renderTile(self, width, height, srs, coord):
        """
        """
        mime_type, content = get_tile(self.tileset, coord)
        formats = {'image/png': 'PNG', 'image/jpeg': 'JPEG', None: None}
        return SaveableTile(formats[mime_type], content)

class SaveableTile:
    def __init__(self, format, content):
        self.format = format
        self.content = content
    
    def save(self, out, format):
        if self.format is not None and format != self.format:
            raise Exception('fuck')

        out.write(self.content)