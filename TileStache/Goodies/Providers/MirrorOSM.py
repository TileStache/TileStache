from sys import stderr
from os import write, close, unlink
from re import search
from urllib import urlopen
from tempfile import mkstemp
from xml.dom.minidom import parse
from subprocess import Popen, PIPE

from TileStache.Core import KnownUnknown
from TileStache.Geography import getProjectionByName

try:
    from psycopg2 import connect as _connect, ProgrammingError
except ImportError:
    # well it won't work but we can still make the documentation.
    pass

def coordinate_api_url(coord, projection):
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
    
    url = 'http://api.openstreetmap.org/api/0.6/map?bbox=%(w).6f,%(s).6f,%(e).6f,%(n).6f' % locals()
    
    return url

def clean_database_bbox(db, prefix, coord):
    """
    """
    projection = getProjectionByName('spherical mercator')
    
    ul = projection.coordinateProj(coord)
    lr = projection.coordinateProj(coord.right().down())
    
    bbox = 'ST_SetSRID(ST_MakeBox2D(ST_MakePoint(%.6f, %.6f), ST_MakePoint(%.6f, %.6f)), 900913)' % (ul.x, ul.y, lr.x, lr.y)
    
    for table in ('point', 'line', 'polygon', 'roads'):
        print >> stderr, 'DELETE FROM %(prefix)s_%(table)s WHERE way && %(bbox)s' % locals()

        db.execute("""DELETE FROM %(prefix)s_%(table)s
                      WHERE way && %(bbox)s""" % locals())

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
        
        print >> stderr, 'Zoinks'
        
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
        url = coordinate_api_url(coord, self.layer.projection)
        doc = parse(urlopen(url))
        raw = doc.toxml('utf-8')
        
        handle, filename = mkstemp(dir='/tmp', prefix='mirrorosm-', suffix='.osm')
        write(handle, raw)
        close(handle)
        
        db = _connect(**self.dbkwargs).cursor()
        
        osm2pgsql = 'osm2pgsql --append --merc --utf8-sanitize --prefix mirrorosm'.split()
        
        for (flag, key) in [('-d', 'database'), ('-U', 'user')]:
            if key in self.dbkwargs:
                osm2pgsql += flag, self.dbkwargs[key]
        
        osm2pgsql += [filename]

        try:
            clean_database_bbox(db, 'mirrorosm', coord)

        except ProgrammingError, e:
            if not search(r'relation "\w+" does not exist', str(e)):
                # it's because of something other than a missing table
                raise e

            db.execute('ROLLBACK')
            db.close()
            print >> stderr, 'ROLLBACK'
    
            osm2pgsql[1] = '--create'
            
            print >> stderr, ' '.join(osm2pgsql)
            create = Popen(osm2pgsql, stderr=PIPE, stdout=PIPE)
            create.wait()

        else:
            db.execute('COMMIT')
            db.close()
            print >> stderr, 'COMMIT'
    
            print >> stderr, ' '.join(osm2pgsql)
            append = Popen(osm2pgsql, stderr=PIPE, stdout=PIPE)
            append.wait()

            assert append.returncode == 0, 'Shit.'
        
        unlink(filename)
        
        # Connection to database failed: FATAL:  database "gis" does not exist
        # Connection to database failed: FATAL:  role "www-data" does not exist
        # Error, failed to query table mirrorosm_point

        return SaveableResponse(raw + '\n')
