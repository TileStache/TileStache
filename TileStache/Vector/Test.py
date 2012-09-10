import logging

from os.path import join
from zipfile import ZipFile
from optparse import OptionParser
from tempfile import mkdtemp
from urllib import urlopen
from shutil import rmtree
from json import loads

from TileStache import getTile
from TileStache.Config import buildConfiguration
from ModestMaps.Core import Coordinate

parser = OptionParser()

parser.set_defaults(verbose=None)

parser.add_option('-v', '--verbose', dest='verbose', action='store_true',
                  help='Set logging level to everything, including debug.')

parser.add_option('-q', '--quiet', dest='verbose', action='store_false',
                  help='Set logging level to warnings, errors, and critical.')

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
        tempdir = mkdtemp(prefix='tilestache-vector-test-')
        filename = join(tempdir, 'oakland-osm-points.zip')
        
        logging.debug('Downloading http://tilestache.org/oakland-osm-points.zip to '+tempdir)

        file = open(filename, 'w')
        file.write(urlopen('http://tilestache.org/oakland-osm-points.zip').read())
        file.close()
        
        archive = ZipFile(filename, 'r')
        archive.extractall(tempdir)
        
        logging.info('Building TileStache configuration')
    
        config_dict = {
          'cache': { 'name': 'Test' },
          'layers': 
          {
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
        
        for layer_name in ('geojson', 'shapefile', 'sqlite'):
            layer_driver = config_dict['layers'][layer_name]['provider']['driver']
            layer_file = config_dict['layers'][layer_name]['provider']['parameters']['file']
        
            logging.info('Checking %(layer_driver)s layer from %(layer_file)s' % locals())
            
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
