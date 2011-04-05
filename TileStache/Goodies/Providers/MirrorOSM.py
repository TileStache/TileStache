from sys import stderr
from os import write, close, unlink
from tempfile import mkstemp
from subprocess import Popen, PIPE
from httplib import HTTPConnection
from StringIO import StringIO
from datetime import datetime
from os.path import basename
from base64 import b16encode
from gzip import GzipFile
from time import time

from TileStache.Core import KnownUnknown
from TileStache.Geography import getProjectionByName

try:
    from psycopg2 import connect as _connect, ProgrammingError
except ImportError:
    # well it won't work but we can still make the documentation.
    pass

def coordinate_latlon_bbox(coord, projection):
    """
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

def download_api_data(filename, coord, projection):
    """
    """
    bbox = coordinate_latlon_bbox(coord, projection)
    path = '/api/0.6/map?bbox=%.6f,%.6f,%.6f,%.6f' % bbox

    conn = HTTPConnection('api.openstreetmap.org')
    conn.request('GET', path, headers={'Accept-Encoding': 'compress, gzip'})
    resp = conn.getresponse()
    
    assert resp.status == 200
    
    if resp.getheader('Content-Encoding') == 'gzip':
        disk = open(filename, 'w')
    else:
        disk = GzipFile(filename, 'w')

    bytes = resp.read()
    disk.write(bytes)
    disk.close()
    
    return len(bytes) / 1024.

def prepare_data(filename, prefix, dbargs, projection):
    """
    """
    osm2pgsql = 'osm2pgsql --create --merc --utf8-sanitize'.split()
    osm2pgsql += ['--prefix', prefix]
    
    for (flag, key) in [('-d', 'database'), ('-U', 'user'), ('-W', 'password'), ('-H', 'host')]:
        if key in dbargs:
            osm2pgsql += flag, dbargs[key]
    
    osm2pgsql += [filename]

    create = Popen(osm2pgsql, stderr=PIPE, stdout=PIPE)
    create.wait()
    
    assert create.returncode == 0, \
        "It's important that osm2pgsql actually worked." + create.stderr.read()

def create_tables(db, prefix):
    """
    """
    for table in ('point', 'line', 'roads', 'polygon'):
        db.execute('BEGIN')
        
        try:
            db.execute('CREATE TABLE mirrorosm_%(table)s ( LIKE %(prefix)s_%(table)s )' % locals())

        except ProgrammingError, e:
            db.execute('ROLLBACK')

            if e.pgcode != '42P07':
                # 42P07 is a duplicate table, the only error we expect.
                raise

        else:
            db.execute("""INSERT INTO geometry_columns
                          (f_table_catalog, f_table_schema, f_table_name, f_geometry_column, coord_dimension, srid, type)
                          SELECT f_table_catalog, f_table_schema, 'mirrorosm_%(table)s', f_geometry_column, coord_dimension, srid, type
                          FROM geometry_columns WHERE f_table_name = '%(prefix)s_%(table)s'""" \
                        % locals())

            db.execute('COMMIT')

def populate_tables(db, prefix, bounds):
    """
    """
    bbox = 'ST_SetSRID(ST_MakeBox2D(ST_MakePoint(%.6f, %.6f), ST_MakePoint(%.6f, %.6f)), 900913)' % bounds
    
    db.execute('BEGIN')
    
    for table in ('point', 'line', 'roads', 'polygon'):
        db.execute('DELETE FROM mirrorosm_%(table)s WHERE ST_Intersects(way, %(bbox)s)' % locals())

        db.execute("""INSERT INTO mirrorosm_%(table)s
                      SELECT * FROM %(prefix)s_%(table)s
                      WHERE ST_Intersects(way, %(bbox)s)""" \
                    % locals())
    
    db.execute('COMMIT')

def clean_up_tables(db, prefix):
    """
    """
    db.execute('BEGIN')
    
    for table in ('point', 'line', 'roads', 'polygon'):
        db.execute('DROP TABLE %(prefix)s_%(table)s' % locals())
        db.execute("DELETE FROM geometry_columns WHERE f_table_name = '%(prefix)s_%(table)s'" % locals())
    
    db.execute('COMMIT')

class ConfirmationResponse:
    """ Wrapper class for JSON response that makes it behave like a PIL.Image object.
    
        TileStache.getTile() expects to be able to save one of these to a buffer.
    """
    def __init__(self, content):
        self.content = content
        
    def save(self, out, format):
        if format != 'TXT':
            raise KnownUnknown('MirrorOSM only saves .txt tiles, not "%s"' % format)

        out.write(self.content)

class Provider:
    """
    """
    
    def __init__(self, layer, database=None, username=None, password=None, hostname=None):
        """
        """
        self.layer = layer
        self.dbkwargs = {}
        
        if hostname:
            self.dbkwargs['host'] = hostname
        
        if username:
            self.dbkwargs['user'] = username
        
        if database:
            self.dbkwargs['database'] = database
        
        if password:
            self.dbkwargs['password'] = password

    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.
        
            This only accepts "txt".
        """
        if extension.lower() != 'txt':
            raise KnownUnknown('MirrorOSM only makes .txt tiles, not "%s"' % extension)
    
        return 'text/plain', 'TXT'

    def renderTile(self, width, height, srs, coord):
        """ Render a single tile, return a ConfirmationResponse instance.
        """
        start = time()
        garbage = []
        
        handle, filename = mkstemp(prefix='mirrorosm-', suffix='.tablename')
        prefix = 'mirrorosm_' + b16encode(basename(filename)[10:-10]).lower()
        garbage.append(filename)
        close(handle)
        
        handle, filename = mkstemp(prefix='mirrorosm-', suffix='.osm.gz')
        garbage.append(filename)
        close(handle)
        
        try:
            length = download_api_data(filename, coord, self.layer.projection)
            prepare_data(filename, prefix, self.dbkwargs, self.layer.projection)
    
            db = _connect(**self.dbkwargs).cursor()
            
            ul = self.layer.projection.coordinateProj(coord)
            lr = self.layer.projection.coordinateProj(coord.down().right())
            
            create_tables(db, prefix)
            populate_tables(db, prefix, (ul.x, ul.y, lr.x, lr.y))
            clean_up_tables(db, prefix)
            
            db.close()
            
            message = 'Retrieved %dK of OpenStreetMap data in %.2fsec (%s).\n' \
                    % (length, (time() - start), datetime.now())

            return ConfirmationResponse(message)
        
        finally:
            for filename in garbage:
                unlink(filename)
