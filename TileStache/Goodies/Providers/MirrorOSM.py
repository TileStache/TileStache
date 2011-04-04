from sys import stderr
from os import write, close, unlink
from re import search
from tempfile import mkstemp
from xml.dom.minidom import parse
from subprocess import Popen, PIPE
from httplib import HTTPConnection
from urlparse import urlparse
from StringIO import StringIO
from gzip import GzipFile

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

def _download_api_data(coord, handle, projection):
    """
    """
    bbox = coordinate_latlon_bbox(coord, projection)
    path = '/api/0.6/map?bbox=%.6f,%.6f,%.6f,%.6f' % bbox

    conn = HTTPConnection('api.openstreetmap.org')
    conn.request('GET', path, headers={'Accept-Encoding': 'compress, gzip'})
    resp = conn.getresponse()
    
    assert resp.status == 200
    
    if resp.getheader('Content-Encoding') == 'gzip':
        buff = StringIO(resp.read())
        data = GzipFile(fileobj=buff, mode='r')
    else:
        data = resp

    write(handle, data.read())

def clean_existing_rows(db, prefix, coord):
    """ Remove all geometries inside the tile bounds from each table.
    """
    projection = getProjectionByName('spherical mercator')
    
    ul = projection.coordinateProj(coord)
    lr = projection.coordinateProj(coord.down().right())
    
    bbox = 'ST_SetSRID(ST_MakeBox2D(ST_MakePoint(%.7f, %.7f), ST_MakePoint(%.7f, %.7f)), 900913)' % (ul.x, ul.y, lr.x, lr.y)
    
    for table in ('point', 'line', 'polygon', 'roads'):
        db.execute('DELETE FROM %(prefix)s_%(table)s WHERE way && %(bbox)s' % locals())

class SaveableResponse:
    """ Wrapper class for JSON response that makes it behave like a PIL.Image object.
    
        TileStache.getTile() expects to be able to save one of these to a buffer.
    """
    def __init__(self, content):
        self.content = content
        
    def save(self, out, format):
        if format != 'XML':
            raise KnownUnknown('MirrorOSM only saves .xml tiles, not "%s"' % format)

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
        
            This only accepts "xml".
        """
        if extension.lower() != 'xml':
            raise KnownUnknown('MirrorOSM only makes .xml tiles, not "%s"' % extension)
    
        return 'text/xml', 'XML'

    def renderTile(self, width, height, srs, coord):
        """ Render a single tile, return a SaveableResponse instance.
        """
        handle, filename = mkstemp(prefix='mirrorosm-', suffix='.osm')
        _download_api_data(coord, handle, self.layer.projection)
        close(handle)
        
        osm2pgsql = 'osm2pgsql --append --merc --utf8-sanitize --prefix mirrorosm'.split()
        
        for (flag, key) in [('-d', 'database'), ('-U', 'user')]:
            if key in self.dbkwargs:
                osm2pgsql += flag, self.dbkwargs[key]
        
        ne = self.layer.projection.coordinateLocation(coord.right())
        sw = self.layer.projection.coordinateLocation(coord.down())
        
        osm2pgsql += ['--bbox', ','.join(['%.6f' % n for n in (sw.lon, sw.lat, ne.lon, ne.lat)])]
        osm2pgsql += [filename]
        
        db = _connect(**self.dbkwargs).cursor()
        
        try:
            # Start by attempting to remove existing
            # data from this tile in the database.

            db.execute('BEGIN')
            clean_existing_rows(db, 'mirrorosm', coord)

        except ProgrammingError, e:
            # If something went wrong, check whether
            # it's that the tables don't yet exist.
        
            if not search(r'relation "\w+" does not exist', str(e)):
                # it's because of something other than a missing table
                raise e
    
                # Connection to database failed: FATAL:  database "gis" does not exist
                # Connection to database failed: FATAL:  role "www-data" does not exist
                # Error, failed to query table mirrorosm_point

            db.execute('ROLLBACK')
            db.close()
    
            osm2pgsql[1] = '--create'
            
            create = Popen(osm2pgsql, stderr=PIPE, stdout=PIPE)
            create.wait()
            
            returncode = create.returncode

        else:
            # If nothing went wrong, we're probably in good shape to append data.

            db.execute('COMMIT')
            db.close()
    
            append = Popen(osm2pgsql, stderr=PIPE, stdout=PIPE)
            append.wait()
            
            returncode = append.returncode

        unlink(filename)
        
        assert returncode == 0, "It's important that osm2pgsql actually worked."
        
        return SaveableResponse('<res>OK</res>' + '\n')
