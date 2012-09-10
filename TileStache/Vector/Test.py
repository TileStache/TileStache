''' TileStache.Vector Tests

TileStache's Vector provider relies on the external OGR library to work. This
module is a small collection of tests designed to ensure that it does and output
useful errors if it doesn't. Tests assume that Python OGR bindings are installed
(available as python-gdal on Ubuntu) and that PostGIS is available.

Run it on the command line like this:

    python -m TileStache.Vector.Test

See details on every option with the `--help` flag:

    python -m TileStache.Vector.Test --help

A zip file containing test data from will be downloaded, used and discarded from:

    http://tilestache.org/oakland-osm-points.zip
'''
import logging

from os import chmod
from os.path import join
from zipfile import ZipFile
from optparse import OptionParser
from subprocess import Popen, PIPE
from tempfile import mkdtemp
from urllib import urlopen
from shutil import rmtree
from json import loads

from TileStache import getTile
from TileStache.Config import buildConfiguration
from ModestMaps.Core import Coordinate

parser = OptionParser(usage='python -m TileStache.Vector.Test [options]')

defaults = dict(verbose=None, hostname='localhost', username='postgres', password='', database='postgres')

parser.set_defaults(**defaults)

parser.add_option('-v', '--verbose', dest='verbose', action='store_true',
                  help='Set logging level to everything, including debug.')

parser.add_option('-q', '--quiet', dest='verbose', action='store_false',
                  help='Set logging level to warnings, errors, and critical.')

parser.add_option('--hostname', dest='hostname', action='store',
                  help='Postgres hostname, default "%(hostname)s".' % defaults)

parser.add_option('--username', dest='username', action='store',
                  help='Postgres username, default "%(username)s".' % defaults)

parser.add_option('--password', dest='password', action='store',
                  help='Postgres password, default "%(password)s".' % defaults)

parser.add_option('--database', dest='database', action='store',
                  help='Postgres database, default "%(database)s".' % defaults)

if __name__ == '__main__':

    opts, args = parser.parse_args()
    
    if opts.verbose is True:
        loglevel = logging.DEBUG

    elif opts.verbose is None:
        loglevel = logging.INFO
    
    elif opts.verbose is False:
        loglevel = logging.WARNING

    logging.basicConfig(level=loglevel, format='%(levelname)08s - %(message)s')

    try:
        logging.debug('Preparing test data')

        tempdir = mkdtemp(prefix='tilestache-vector-test-')
        filename = join(tempdir, 'oakland-osm-points.zip')
        
        logging.debug('Downloading http://tilestache.org/oakland-osm-points.zip to '+tempdir)

        file = open(filename, 'w')
        file.write(urlopen('http://tilestache.org/oakland-osm-points.zip').read())
        file.close()
        
        archive = ZipFile(filename, 'r')
        archive.extractall(tempdir)
        
        logging.debug('Loading Postgres')

        pgpass = open(join(tempdir, '.pgpass'), 'w')
        chmod(pgpass.name, 0600)

        pgpass.write(':'.join((opts.hostname, '*', opts.database, opts.username, opts.password)))
        pgpass.close()
        
        cmd = 'psql -h xxx -U xxx -d xxx -f oakland-osm-points-merc.pgsql'.split()
        cmd[2], cmd[4], cmd[6] = opts.hostname, opts.username, opts.database
        
        pipes = (not opts.verbose) and dict(stderr=PIPE, stdout=PIPE) or dict()
        Popen(cmd, cwd=tempdir, env=dict(PGPASSFILE='.pgpass'), **pipes).wait()
        
        logging.info('Building TileStache configuration')
    
        config_dict = {
          'cache': { 'name': 'Test' },
          'layers': 
          {
            'postgresql':
            {
                'provider': {'name': 'vector', 'driver': 'PostgreSQL', 'parameters': {'host': opts.hostname, 'user': opts.username, 'password': opts.password, 'dbname': opts.database, 'table': 'oakland_osm_points'}}
            },
            'geojson':
            {
                'provider': {'name': 'vector', 'driver': 'GeoJSON', 'parameters': {'file': join(tempdir, 'oakland-osm-points.json')}}
            },
            'shapefile':
            {
                'provider': {'name': 'vector', 'driver': 'Shapefile', 'parameters': {'file': join(tempdir, 'oakland-osm-points-merc.shp')}}
            },
            'sqlite':
            {
                'provider': {'name': 'vector', 'driver': 'Spatialite', 'parameters': {'file': join(tempdir, 'oakland-osm-points.sqlite'), 'layer': 'oakland_osm_points'}}
            }
          }
        }
        
        config = buildConfiguration(config_dict, tempdir)
        coord = Coordinate(12662, 5254, 15)
        
        for layer_name in ('postgresql', 'geojson', 'shapefile', 'sqlite'):
            driver = config_dict['layers'][layer_name]['provider']['driver']
            params = config_dict['layers'][layer_name]['provider']['parameters']
            
            if layer_name == 'postgresql':
                desc = '%(user)s@%(host)s/%(dbname)s' % params
            else:
                desc = params['file']
        
            logging.info('Checking %(driver)s layer from %(desc)s' % locals())
            
            layer = config.layers[layer_name]
        
            ll = layer.projection.coordinateLocation(coord.down())
            ur = layer.projection.coordinateLocation(coord.right())
            
            mimetype, body = getTile(layer, coord, 'geojson')
            assert mimetype.endswith('/json'), 'tile MIME-Type should end in "/json"'
            
            features = loads(body).get('features', [])
            assert len(features), 'There should be at least some features in the tile'
        
            lons = [feature.get('geometry', {}).get('coordinates', [])[0] for feature in features]
            lats = [feature.get('geometry', {}).get('coordinates', [])[1] for feature in features]
            
            minlat, minlon, maxlat, maxlon = min(lats), min(lons), max(lats), max(lons)
            
            assert minlat >= ll.lat, 'Minimum latitude should be greater than %.6f' % ll.lat
            assert minlon >= ll.lon, 'Minimum longitude should be greater than %.6f' % ll.lon
            assert maxlat <= ur.lat, 'Maximum latitude should be less than %.6f' % ur.lat
            assert maxlon <= ur.lon, 'Maximum longitude should be less than %.6f' % ur.lon
        
    finally:
        logging.info('Cleaning up %s/*' % tempdir)
        rmtree(tempdir)
