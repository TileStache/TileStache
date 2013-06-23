from unittest import TestCase
import json

from osgeo import ogr
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, asShape

from . import utils


# Note these tests rely on the fact that Travis CI created a postgis db.
# If you want to run them locally, create a similar PostGIS database.
# Look at .travis.yml for details.

class PostGISVectorTestBase(object):
    '''
    Base Class for PostGIS Vector tests. Has methods to:

      - CREATE and DROP a single table (self.testTableName) that has a field called name
      - Define a geometry field
      - INSERT a record using a WKT
    '''

    def initTestTable(self, testTableName):
        self.conn = ogr.Open("PG: dbname='test_tilestache' user='postgres'")
        self.testTableName = testTableName
        
        self.cleanTestTable()

        sql = 'CREATE TABLE %s (gid serial PRIMARY KEY, name VARCHAR)' % (self.testTableName,)
        self.conn.ExecuteSQL(sql)

    def defineGeometry(self, geom_type, geom_name = 'geom', srid=4326):
        self.srid = srid
        self.geom_name = geom_name
        
        sql = "SELECT AddGeometryColumn('public', '%s', '%s', %s, '%s', 2)" % \
        (self.testTableName, geom_name, srid, geom_type)

        self.conn.ExecuteSQL(sql)

    def insertTestRow(self, wkt, name=''):
        sql = "INSERT INTO %s (%s, name) VALUES(ST_GeomFromText('%s',%s),'%s')" % \
        (self.testTableName, self.geom_name, wkt, self.srid, name)

        self.conn.ExecuteSQL(sql)

    def cleanTestTable(self):
        self.conn.ExecuteSQL('DROP TABLE if exists %s' % (self.testTableName,))


class VectorProviderTest(PostGISVectorTestBase, TestCase):
    '''Various vector tests on top of PostGIS'''

    def setUp(self):
        self.initTestTable('dummy_table')

        self.config_file_content = '''
        {
           "layers":{
              "vector_test":{
                 "provider":{
                    "name": "vector",
                    "driver" : "PostgreSQL",
                    "parameters": {
                                    "dbname": "test_tilestache", 
                                    "user": "postgres",
                                    "table": "dummy_table"
                    }                    
                 },
                 "projection" : "WGS84"
              }
            },
            "cache": {
                "name": "Test"
            }
        }
        '''

    def tearDown(self):
        self.cleanTestTable()

    def test_points_geojson(self):
        '''
        Create 3 points (2 on west, 1 on east hemisphere) and retrieve as geojson.
        2 points should be returned in western hemisphere and 1 on eastern at zoom level 0
        (clip on)
        '''
        
        self.defineGeometry('POINT')

        point_sf = Point(-122.4183, 37.7750)
        point_berlin = Point(13.4127, 52.5233)
        point_lima = Point(-77.0283, 12.0433)

        self.insertTestRow(point_sf.wkt, 'San Francisco')
        self.insertTestRow(point_berlin.wkt, 'Berlin')
        self.insertTestRow(point_lima.wkt, 'Lima')

        ########
        # western hemisphere should return San Francisco and Lima

        tile_mimetype, tile_content = utils.request(self.config_file_content, "vector_test", "geojson", 0, 0, 0)
        geojson_result = json.loads(tile_content)

        self.assertTrue(tile_mimetype.endswith('/json'))
        self.assertEqual(geojson_result['type'], 'FeatureCollection')
        self.assertEqual(len(geojson_result['features']), 2)

        cities = []

        # Make sure that the right cities have been returned and that the geometries match

        for feature in geojson_result['features']:
            if feature['properties']['name'] == 'San Francisco':
                cities.append(feature['properties']['name'])
                self.assertTrue(point_sf.almost_equals(asShape(feature['geometry'])))

            elif feature['properties']['name'] == 'Lima':
                cities.append(feature['properties']['name'])
                self.assertTrue(point_lima.almost_equals(asShape(feature['geometry'])))

        self.assertTrue('San Francisco' in cities)
        self.assertTrue('Lima' in cities)

        ##########
        # eastern hemisphere should return Berlin

        tile_mimetype, tile_content = utils.request(self.config_file_content, "vector_test", "geojson", 0, 1, 0)
        geojson_result = json.loads(tile_content)

        self.assertTrue(tile_mimetype.endswith('/json'))
        self.assertEqual(geojson_result['type'], 'FeatureCollection')
        self.assertEqual(len(geojson_result['features']), 1)
        self.assertTrue('Berlin' in geojson_result['features'][0]['properties']['name'])


    def test_linestring_geojson(self):
        '''Create a line that goes from west to east (clip on)'''
        
        self.defineGeometry('LINESTRING')

        geom = LineString( [(-180, 32), (180, 32)] )

        self.insertTestRow(geom.wkt)

        # we should have a line that clips at 0...

        # for western hemisphere....
        tile_mimetype, tile_content = utils.request(self.config_file_content, "vector_test", "geojson", 0, 0, 0)
        self.assertTrue(tile_mimetype.endswith('/json'))
        geojson_result = json.loads(tile_content)
        west_hemisphere_geometry = asShape(geojson_result['features'][0]['geometry'])
        expected_geometry = LineString([(-180, 32), (0, 32)])
        self.assertTrue(expected_geometry.almost_equals(west_hemisphere_geometry))

        # for eastern hemisphere....
        tile_mimetype, tile_content = utils.request(self.config_file_content, "vector_test", "geojson", 0, 1, 0)
        self.assertTrue(tile_mimetype.endswith('/json'))
        geojson_result = json.loads(tile_content)
        east_hemisphere_geometry = asShape(geojson_result['features'][0]['geometry'])
        expected_geometry = LineString([(0, 32), (180, 32)])
        self.assertTrue(expected_geometry.almost_equals(east_hemisphere_geometry))


    def test_polygon_geojson(self):
        '''
        Create a polygon to cover the world and make sure it is "similar" (clip on)
        '''
        
        self.defineGeometry('POLYGON')

        geom = Polygon( [(-180, -90),
                         ( 180, -90),
                         ( 180, 90), 
                         (-180, 90), 
                         (-180, -90)])

        self.insertTestRow(geom.wkt)
        
        tile_mimetype, tile_content = utils.request(self.config_file_content, "vector_test", "geojson", 0, 0, 0)
        self.assertTrue(tile_mimetype.endswith('/json'))
        geojson_result = json.loads(tile_content)
        
        result_geom = asShape(geojson_result['features'][0]['geometry'])
        expected_geom = Polygon( [(-180, -90), (0, -90), (0, 90), (-180, 90), (-180, -90)])

        # What is going on here is a bit unorthodox, but let me explain. The clipping
        # code inside TileStache relies on GEOS Intersection alongside some TileStache code
        # that creates a clipping geometry based on the tile perimeter. The tile perimeter
        # is made out of 17 (x,y) coordinates and not a box. Hence, the GEOS::Intersection
        # os that perimeter with the geometry of the vector we get back from the data provider
        # can end with extra vertices. Although it is the right shape, we cannot do a straight
        # comparisson because the expected geometry and the returned geometry *may* have extra
        # vertices. Simplify() will not do much because the distance of the vertices can clearly
        # be bigger than the tolerance. 
        #
        # To add to this, because of double precision, the vertices may not be exact.
        # An optional way to find out if two shapes are close enough, is to buffer the two features
        # by just a little bit and then subtract each other like so:
        #
        #             geometry1.difference(geometry2) == empty set?
        #             geometry2.difference(geometry1) == empty set?
        # 
        # If both geometries are empty, then they are similar. Hence what you see below
        
        self.assertTrue(result_geom.difference(expected_geom.buffer(0.001)).is_empty)
        self.assertTrue(expected_geom.difference(result_geom.buffer(0.001)).is_empty)


