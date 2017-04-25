""" Populate an OSM rendering database using tiled data requests.

This provider is unusual in that requests for tiles have the side effect of
running osm2pgsql to populate a PostGIS database of OSM data from a remote API
source. Returned tiles are just text confirmations that the process has been
successful, while the stored data is expected to be used in other providers
to render OSM data. It would be normal to use this provider outside the regular
confines of a web server, perhaps with a call to tilestache-seed.py governed
by a cron job or some other out-of-band process.

MirrorOSM is made tenable by MapQuest's hosting of the XAPI service:
  http://open.mapquestapi.com/xapi/

Osm2pgsql is an external utility:
  http://wiki.openstreetmap.org/wiki/Osm2pgsql

Example configuration:

  "mirror-osm":
  {
    "provider":
    {
      "class": "TileStache.Goodies.Providers.MirrorOSM:Provider",
      "kwargs":
      {
        "username": "osm",
        "database": "planet",
        "api_base": "http://open.mapquestapi.com/xapi/"
      }
    }
  }

Provider parameters:

  database:
    Required Postgres database name.
  
  username:
    Required Postgres user name.
  
  password:
    Optional Postgres password.
  
  hostname:
    Optional Postgres host name.
  
  table_prefix:
    Optional table prefix for osm2pgsql. Defaults to "mirrorosm" if omitted.
    Four tables will be created with this prefix: <prefix>_point, <prefix>_line,
    <prefix>_polygon, and <prefix>_roads. Must result in valid table names!
  
  api_base:
    Optional OSM API base URL. Because we don't want to overtax the main OSM
    API, this defaults to MapQuest's XAPI, "http://open.mapquestapi.com/xapi/".
    The trailing slash must be included, up to but not including the "api/0.6"
    portion of a URL. If you're careful to limit your usage, the primary
    OSM API can be specified with "http://api.openstreetmap.org/".
  
  osm2pgsql:
    Optional filesystem path to osm2pgsql, just in case it's someplace outside
    /usr/bin or /usr/local/bin. Defaults to "osm2pgsql --utf8-sanitize".
    Additional arguments such as "--keep-coastlines" can be added to this string,
    e.g. "/home/user/bin/osm2pgsql --keep-coastlines --utf8-sanitize".
"""
from sys import stderr
from os import write, close, unlink
from tempfile import mkstemp
from subprocess import Popen, PIPE
from httplib import HTTPConnection
from os.path import basename, join
try:
    from io import StringIO
except ImportError:
    # Python 2
    from StringIO import StringIO
from datetime import datetime
try:
    from urllib.parse import urlparse
except ImportError:
    # Python 2
    from urlparse import urlparse
from base64 import b16encode
from urllib import urlopen
from gzip import GzipFile
from time import time

from TileStache.Core import KnownUnknown, NoTileLeftBehind
from TileStache.Geography import getProjectionByName

try:
    from psycopg2 import connect as _connect, ProgrammingError
except ImportError:
    # well it won't work but we can still make the documentation.
    pass

try:
    from PIL import Image
    from PIL.ImageDraw import ImageDraw
except ImportError:
    # On some systems, PIL.Image is known as Image.
    import Image
    from ImageDraw import ImageDraw

_thumbs_up_bytes = '\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00@\x00\x00\x00@\x08\x03\x00\x00\x00\x9d\xb7\x81\xec\x00\x00\x00\x19tEXtSoftware\x00Adobe ImageReadyq\xc9e<\x00\x00\x00\x0fPLTEy\xb3yn\xa2n\x91\xd6\x91\x85\xc5\x85\x9d\xe8\x9d\xfd\'\x17\xea\x00\x00\x01\x93IDATx\xda\xec\xd6A\x8e\xc3 \x0c\x05P\xf3\xcd\xfd\xcf<\t4\x80\x8d\r\xa6YU\x1aoZE\xe2\xf5\x03.\x84\xf2T`\xe4x\xd1\xfc\x88\x19x\x03\x80\xf0\x0e\xe0;\x01\xde\x01\xfc\x1a8\x10\x1c\xe0\xaa\xb7\x00\xe1k\x80*\x10\x14\xacm\xe4\x13\xc1j\xa4\'BH0\x80\x1e!"\x18\xc0\x99`\x01\xcf$B{A\xf6Sn\x85\xaf\x00\xc4\x05\xca\xbb\x08\x9b\x9et\x00\x0e\x0b\x0e0\xcea\xddR\x11`)\xb8\x80\x8c\xe0\x0b\xee\x1aha\x0b\xa0\x1d"\xd7\x81\xc6S\x11\xaf\x81+r\xf9Msp\x15\x96\x00\xea\xf0{\xbcO\xac\x80q\xb8K\xc0\x07\xa0\xc6\xe3 \x02\xf5]\xc7V\x80;\x05V\t\xdcu\x00\xa7\xab\xee\x19?{F\xe3m\x12\x10\x98\xcaxJ\x15\xe2\xd6\x07\x1c\x8cp\x0b\xfd\xb8\xa1\x84\xa7\x0f\xb8\xa4\x8aE\x18z\xb4\x01\xd3\x0cb@O@3\x80\x05@\xb5\xae\xef\xb9\x01\xb0\xca\x02\xea">\xb5\x01\xb0\x01\x12\xf5m\x04\x82\x84\x00\xda6\xc2\x05`\xf7\xc1\x07@\xeb\x83\x85\x00\x15\xa0\x03)\xe5\x01\xe0( f0t""\x11@"\x00\x82\x00\xc4\x0c\x86\xcaQ\x00\xe2\xcf\xd8\x8a\xe3\xc0\xc7\x00\xe9\x00}\x11\x89\x03\x80\x0c@\xeaX\x0fLB\x06\x80\xbcX\x10\xd8\x889\xc0x3\x05\xdayZ\x81\x10 \xdaXn\x81\x04\xecnVm\xac\x03\x88\xcb\x95x\xfb7P+\xa8\x00\xefX\xeb\xad\xabWP_\xef\xce\xc1|\x7f\xcf\x94\xac\t\xe8\xf7\x031\xba|t\xdc\x9c\x80\xfb\x82a\xdda\xe6\xf8\x03\xa0\x04\xe4\xb2\x12\x9c\xbf\x04\x0e\xde\x91\xfe\x81\xdf\x02\xfe\x04\x18\x00\\_2;\x7fBc\xdd\x00\x00\x00\x00IEND\xaeB`\x82'
_thumbs_up_color = 0x9d, 0xe8, 0x9d

_thumbs_down_bytes = '\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00@\x00\x00\x00@\x08\x03\x00\x00\x00\x9d\xb7\x81\xec\x00\x00\x00\x19tEXtSoftware\x00Adobe ImageReadyq\xc9e<\x00\x00\x00\x0fPLTE\xc4\x8c\x8c\xb1~~\xeb\xa7\xa7\xd8\x9a\x9a\xfe\xb5\xb5\xc9\xe5\xcd\n\x00\x00\x01\x8aIDATx\xda\xec\x97\xd1\xb2\x84 \x0cCc\xe2\xff\x7f\xf3U\x14\x04,P\xf0ign\x1fw&\xc7\xa4\xad.`\xffX\xf8\x07\xfc"\x80\x14\xb8\x068\x94\xd8\xaeb\x1f\xc0T\xf9\xaf[^-\x80\xf4\x88\x15*QX\x00`\x03r\xfd\xc3\xb8*\xd9\xbfJ\x16\xa0\xd6\xe7\x08@*\x08\xf4\x01\n\x13\xb2\xda\x80\xbc\xcb\xb4*\x8fa\x84\x18\x03r\x86\x11\xc2\x05H\x08c\x12p\xe9m\x02\x0b\x00\xd5\x05\xdc\x88\xb7\x85\x08 \x06\xfa\x00 ^\x16\x90F\xa8\xf1\xf3\xc5\xb7\x05tv\xc0\x98C\xb9\xd0\x9b\x1b\x90\xe6xf@\xac\x90\x01\x9e\x1eV\xdb\xf8\x10\x90M\xc1\x0b(-\xf8"\xa8\x05\xc0\x91\x01\xc3)\xaa\xaa\x02\xa0\x08P\x0b u\x01x\x00^\xfd\x91\x01\x19\xa1\xef@2\x01\x9b\xb2&t\x00R\x13\xf0\xe4\xd1\xd3D\xf9\xf4g\x13\x0c\xc0~~\xf4V\x00@ZD9\x01w\x84k\x91\xa2\x833A\x05h??\xbe\x8ag\xea\xb8\x89\x82O\xcf\xf0\xde+\xff\xcf\xba?l5\xc0\xd6\xb7\xff\x9dQE\xf0\xebS\x84\xc2C\xd3\x7f\xfb|\x10\x9a\xaa~\xf5\x0f\x18\x0c&\x8e\xe6\xb4\x9e\x0f\xce\x9cP\xa8\xda\x0e4w\xc4a\x99\x08\xc0\xec\x19\xa9\xd6\xf3#\x80\xb3\xa74\xc2\x93\xdf\x0b\xd0\xc29q\xbc@\x831\xc2\xabo\x00\xfcz\x1b\x90\xd6\xa8\xdb\xbe6 \xea\xe1\xd0[\x00\xce\xe8-\xc0m\xc0\xa7\xb7\x00\xc9\xc0\xe2}\x81\x98\xd1\x1b\x80\x98\x80\xcb\x00\xdf\xfc\xfb\x80\xea\xae\xb1\x02\xf8p\xe9\xba\x0e+_nmS\x06\xccM\xfc\n\xd8g\xf4\xfb\x9f\x00\x03\x00\x0eA2jW\xf7\x1bk\x00\x00\x00\x00IEND\xaeB`\x82'
_thumbs_down_color = 0xfe, 0xb5, 0xb5

def coordinate_latlon_bbox(coord, projection):
    """ Return an (xmin, ymin, xmax, ymax) bounding box for a projected tile.
    """
    ul = projection.coordinateLocation(coord)
    ur = projection.coordinateLocation(coord.right())
    ll = projection.coordinateLocation(coord.down())
    lr = projection.coordinateLocation(coord.down().right())
    
    n = max(ul.lat, ur.lat, ll.lat, lr.lat)
    s = min(ul.lat, ur.lat, ll.lat, lr.lat)
    e = max(ul.lon, ur.lon, ll.lon, lr.lon)
    w = min(ul.lon, ur.lon, ll.lon, lr.lon)
    
    return w, s, e, n

def download_api_data(filename, coord, api_base, projection):
    """ Download API data for a tile to a named file, return size in kilobytes.
    """
    s, host, path, p, q, f = urlparse(api_base)
    bbox = coordinate_latlon_bbox(coord, projection)
    path = join(path, 'api/0.6/map?bbox=%.6f,%.6f,%.6f,%.6f' % bbox)
    
    conn = HTTPConnection(host)
    conn.request('GET', path, headers={'Accept-Encoding': 'compress, gzip'})
    resp = conn.getresponse()
    
    assert resp.status == 200, (resp.status, resp.read())
    
    if resp.getheader('Content-Encoding') == 'gzip':
        disk = open(filename, 'w')
    else:
        raise Exception((host, path))
        disk = GzipFile(filename, 'w')

    bytes = resp.read()
    disk.write(bytes)
    disk.close()
    
    return len(bytes) / 1024.

def prepare_data(filename, tmp_prefix, dbargs, osm2pgsql, projection):
    """ Stage OSM data into a temporary set of tables using osm2pgsql.
    """
    args = osm2pgsql.split() + ['--create', '--merc', '--prefix', tmp_prefix]
    
    for (flag, key) in [('-d', 'database'), ('-U', 'user'), ('-W', 'password'), ('-H', 'host')]:
        if key in dbargs:
            args += flag, dbargs[key]
    
    args += [filename]

    create = Popen(args, stderr=PIPE, stdout=PIPE)
    create.wait()
    
    assert create.returncode == 0, \
        "It's important that osm2pgsql actually worked." + create.stderr.read()

def create_tables(db, prefix, tmp_prefix):
    """ Create permanent tables for OSM data. No-op if they already exist.
    """
    for table in ('point', 'line', 'roads', 'polygon'):
        db.execute('BEGIN')
        
        try:
            db.execute('CREATE TABLE %(prefix)s_%(table)s ( LIKE %(tmp_prefix)s_%(table)s )' % locals())

        except ProgrammingError, e:
            db.execute('ROLLBACK')

            if e.pgcode != '42P07':
                # 42P07 is a duplicate table, the only error we expect.
                raise

        else:
            db.execute("""INSERT INTO geometry_columns
                          (f_table_catalog, f_table_schema, f_table_name, f_geometry_column, coord_dimension, srid, type)
                          SELECT f_table_catalog, f_table_schema, '%(prefix)s_%(table)s', f_geometry_column, coord_dimension, srid, type
                          FROM geometry_columns WHERE f_table_name = '%(tmp_prefix)s_%(table)s'""" \
                        % locals())

            db.execute('COMMIT')

def populate_tables(db, prefix, tmp_prefix, bounds):
    """ Move prepared OSM data from temporary to permanent tables.
    
        Replace existing data and work within a single transaction.
    """
    bbox = 'ST_SetSRID(ST_MakeBox2D(ST_MakePoint(%.6f, %.6f), ST_MakePoint(%.6f, %.6f)), 900913)' % bounds
    
    db.execute('BEGIN')
    
    for table in ('point', 'line', 'roads', 'polygon'):
        db.execute('DELETE FROM %(prefix)s_%(table)s WHERE ST_Intersects(way, %(bbox)s)' % locals())

        db.execute("""INSERT INTO %(prefix)s_%(table)s
                      SELECT * FROM %(tmp_prefix)s_%(table)s
                      WHERE ST_Intersects(way, %(bbox)s)""" \
                    % locals())
    
    db.execute('COMMIT')

def clean_up_tables(db, tmp_prefix):
    """ Drop all temporary tables created by prepare_data().
    """
    db.execute('BEGIN')
    
    for table in ('point', 'line', 'roads', 'polygon'):
        db.execute('DROP TABLE %(tmp_prefix)s_%(table)s' % locals())
        db.execute("DELETE FROM geometry_columns WHERE f_table_name = '%(tmp_prefix)s_%(table)s'" % locals())
    
    db.execute('COMMIT')

class ConfirmationResponse:
    """ Wrapper class for confirmation responses.
    
        TileStache.getTile() expects to be able to save one of these to a buffer.
    """
    def __init__(self, coord, content, success):
        self.coord = coord
        self.content = content
        self.success = success
        
    def do_I_have_to_draw_you_a_picture(self):
        """ Return a little thumbs-up / thumbs-down image with text in it.
        """
        if self.success:
            bytes, color = _thumbs_up_bytes, _thumbs_up_color
        else:
            bytes, color = _thumbs_down_bytes, _thumbs_down_color
        
        thumb = Image.open(StringIO(bytes))
        image = Image.new('RGB', (256, 256), color)
        image.paste(thumb.resize((128, 128)), (64, 80))
        
        mapnik_url = 'http://tile.openstreetmap.org/%(zoom)d/%(column)d/%(row)d.png' % self.coord.__dict__
        mapnik_img = Image.open(StringIO(urlopen(mapnik_url).read()))
        mapnik_img = mapnik_img.convert('L').convert('RGB')
        image = Image.blend(image, mapnik_img, .15)
        
        draw = ImageDraw(image)
        margin, leading = 8, 12
        x, y = margin, margin
        
        for word in self.content.split():
            w, h = draw.textsize(word)
            
            if x > margin and x + w > 250:
                x, y = margin, y + leading
            
            draw.text((x, y), word, fill=(0x33, 0x33, 0x33))
            x += draw.textsize(word + ' ')[0]
        
        return image
    
    def save(self, out, format):
        if format == 'TXT':
            out.write(self.content)
        
        elif format == 'PNG':
            image = self.do_I_have_to_draw_you_a_picture()
            image.save(out, format)

        else:
            raise KnownUnknown('MirrorOSM only saves .txt and .png tiles, not "%s"' % format)

class Provider:
    """
    """
    def __init__(self, layer, database, username, password=None, hostname=None, table_prefix='mirrorosm', api_base='http://open.mapquestapi.com/xapi/', osm2pgsql='osm2pgsql --utf8-sanitize'):
        """
        """
        self.layer = layer
        self.dbkwargs = {'database': database}
        
        self.api_base = api_base
        self.prefix = table_prefix
        self.osm2pgsql = osm2pgsql
        
        if hostname:
            self.dbkwargs['host'] = hostname
        
        if username:
            self.dbkwargs['user'] = username
        
        if password:
            self.dbkwargs['password'] = password

    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.
        
            This only accepts "txt".
        """
        if extension.lower() == 'txt':
            return 'text/plain', 'TXT'
        
        elif extension.lower() == 'png':
            return 'image/png', 'PNG'
        
        else:
            raise KnownUnknown('MirrorOSM only makes .txt and .png tiles, not "%s"' % extension)

    def renderTile(self, width, height, srs, coord):
        """ Render a single tile, return a ConfirmationResponse instance.
        """
        if coord.zoom < 12:
            raise KnownUnknown('MirrorOSM provider only handles data at zoom 12 or higher, not %d.' % coord.zoom)
        
        start = time()
        garbage = []
        
        handle, filename = mkstemp(prefix='mirrorosm-', suffix='.tablename')
        tmp_prefix = 'mirrorosm_' + b16encode(basename(filename)[10:-10]).lower()
        garbage.append(filename)
        close(handle)
        
        handle, filename = mkstemp(prefix='mirrorosm-', suffix='.osm.gz')
        garbage.append(filename)
        close(handle)
        
        try:
            length = download_api_data(filename, coord, self.api_base, self.layer.projection)
            prepare_data(filename, tmp_prefix, self.dbkwargs, self.osm2pgsql, self.layer.projection)
    
            db = _connect(**self.dbkwargs).cursor()
            
            ul = self.layer.projection.coordinateProj(coord)
            lr = self.layer.projection.coordinateProj(coord.down().right())
            
            create_tables(db, self.prefix, tmp_prefix)
            populate_tables(db, self.prefix, tmp_prefix, (ul.x, ul.y, lr.x, lr.y))
            clean_up_tables(db, tmp_prefix)
            
            db.close()
            
            message = 'Retrieved %dK of OpenStreetMap data for tile %d/%d/%d in %.2fsec from %s (%s).\n' \
                    % (length, coord.zoom, coord.column, coord.row,
                       (time() - start), self.api_base, datetime.now())

            return ConfirmationResponse(coord, message, True)
        
        except Exception, e:
            message = 'Error in tile %d/%d/%d: %s' % (coord.zoom, coord.column, coord.row, e)
            
            raise NoTileLeftBehind(ConfirmationResponse(coord, message, False))
        
        finally:
            for filename in garbage:
                unlink(filename)
