from unittest import TestCase
from math import hypot
import json

from osgeo import ogr
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, asShape

from . import utils

# Note these tests rely on the fact that Travis CI created a postgis db.
# If you want to run them locally, create a similar PostGIS database.
# Look at .travis.yml for details.

def get_topo_transform(topojson):
    '''
    '''
    def xform((x, y)):
        lon = topojson['transform']['scale'][0] * x + topojson['transform']['translate'][0]
        lat = topojson['transform']['scale'][1] * y + topojson['transform']['translate'][1]
        
        return lon, lat
    
    return xform

def topojson_dediff(points):
    '''
    '''
    out = [points[0]]
    
    for (x, y) in points[1:]:
        out.append((out[-1][0] + x, out[-1][1] + y))
    
    return out

class PostGISVectorTestBase(object):
    '''
    Base Class for VecTiles tests. Has methods to:

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

    def defineGeometry(self, geom_type, geom_name = '__geometry__', srid=900913):
        self.srid = srid
        self.geom_name = geom_name
        
        sql = "SELECT AddGeometryColumn('public', '%s', '%s', %s, '%s', 2)" % \
        (self.testTableName, geom_name, srid, geom_type)

        self.conn.ExecuteSQL(sql)

    def insertTestRow(self, wkt, name=''):
        sql = "INSERT INTO %s (%s, name) VALUES(ST_Transform(ST_GeomFromText('%s', 4326), %s), '%s')" % \
        (self.testTableName, self.geom_name, wkt, self.srid, name)

        self.conn.ExecuteSQL(sql)

    def cleanTestTable(self):
        self.conn.ExecuteSQL('DROP TABLE if exists %s' % (self.testTableName,))


class VectorProviderTest(PostGISVectorTestBase, TestCase):
    '''Various vectiles tests on top of PostGIS'''

    def setUp(self):
        self.initTestTable('dummy_table')

        self.config_file_content = '''
        {
           "layers":{
              "vectile_test":
              {
                 "provider":
                 {
                     "class": "TileStache.Goodies.VecTiles:Provider",
                     "kwargs":
                     {
                         "clip": false,
                         "dbinfo":
                         {
                             "user": "postgres",
                             "password": "",
                             "database": "test_tilestache"
                         },
                         "queries":
                         [
                             "SELECT * FROM dummy_table"
                         ]
                     }
                 }
              },
              "vectile_copy":
              {
                 "provider":
                 {
                     "class": "TileStache.Goodies.VecTiles:Provider",
                     "kwargs":
                     {
                         "dbinfo":
                         {
                             "user": "postgres",
                             "password": "",
                             "database": "test_tilestache"
                         },
                         "queries":
                         [
                             "SELECT * FROM dummy_table"
                         ]
                     }
                 }
              },
              "vectile_multi":
              {
                 "provider":
                 {
                     "class": "TileStache.Goodies.VecTiles:MultiProvider",
                     "kwargs": { "names": [ "vectile_test", "vectile_copy" ] }
                 }
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
        2 points should be returned in western hemisphere and 1 on eastern at zoom level 1
        (clip on)
        '''
        
        self.defineGeometry('POINT')

        point_sf = Point(-122.42, 37.78)
        point_berlin = Point(13.41, 52.52)
        point_lima = Point(-77.03, 12.04)

        self.insertTestRow(point_sf.wkt, 'San Francisco')
        self.insertTestRow(point_berlin.wkt, 'Berlin')
        self.insertTestRow(point_lima.wkt, 'Lima')

        ########
        # northwest quadrant should return San Francisco and Lima

        tile_mimetype, tile_content = utils.request(self.config_file_content, "vectile_test", "json", 0, 0, 1)
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
        # northeast quadrant should return Berlin

        tile_mimetype, tile_content = utils.request(self.config_file_content, "vectile_test", "json", 0, 1, 1)
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

        tile_mimetype, tile_content = utils.request(self.config_file_content, "vectile_test", "json", 0, 0, 0)
        self.assertTrue(tile_mimetype.endswith('/json'))
        geojson_result = json.loads(tile_content)
        west_hemisphere_geometry = asShape(geojson_result['features'][0]['geometry'])
        expected_geometry = LineString([(-180, 32), (180, 32)])
        self.assertTrue(expected_geometry.almost_equals(west_hemisphere_geometry))


    def test_polygon_geojson(self):
        '''
        Create a polygon to cover the world and make sure it is "similar" (clip on)
        '''
        
        self.defineGeometry('POLYGON')

        geom = Polygon( [(-180, -85.05),
                         ( 180, -85.05),
                         ( 180, 85.05), 
                         (-180, 85.05), 
                         (-180, -85.05)])

        self.insertTestRow(geom.wkt)
        
        tile_mimetype, tile_content = utils.request(self.config_file_content, "vectile_test", "json", 0, 0, 0)
        self.assertTrue(tile_mimetype.endswith('/json'))
        geojson_result = json.loads(tile_content)
        
        result_geom = asShape(geojson_result['features'][0]['geometry'])
        expected_geom = Polygon( [(-180, -85.05), (180, -85.05), (180, 85.05), (-180, 85.05), (-180, -85.05)])

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
    

    def test_linestring_multi_geojson(self):
        '''Create a line that goes from west to east (clip on), and test it in MultiProvider'''
        
        self.defineGeometry('LINESTRING')

        geom = LineString( [(-180, 32), (180, 32)] )

        self.insertTestRow(geom.wkt)

        # we should have a line that clips at 0...

        tile_mimetype, tile_content = utils.request(self.config_file_content, "vectile_multi", "json", 0, 0, 0)
        self.assertTrue(tile_mimetype.endswith('/json'))
        geojson_result = json.loads(tile_content)
        
        feature1, feature2 = geojson_result['vectile_test'], geojson_result['vectile_copy']
        self.assertEqual(feature1['type'], 'FeatureCollection')
        self.assertEqual(feature2['type'], 'FeatureCollection')
        self.assertEqual(feature1['features'][0]['type'], 'Feature')
        self.assertEqual(feature2['features'][0]['type'], 'Feature')
        self.assertEqual(feature1['features'][0]['geometry']['type'], 'LineString')
        self.assertEqual(feature2['features'][0]['geometry']['type'], 'LineString')
        self.assertEqual(feature1['features'][0]['id'], feature2['features'][0]['id'])
        
        self.assertTrue('clipped' not in feature1['features'][0])
        self.assertTrue(feature2['features'][0]['clipped'])


    def test_points_topojson(self):
        '''
        Create 3 points (2 on west, 1 on east hemisphere) and retrieve as topojson.
        2 points should be returned in western hemisphere and 1 on eastern at zoom level 1
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
        # northwest quadrant should return San Francisco and Lima

        tile_mimetype, tile_content = utils.request(self.config_file_content, "vectile_test", "topojson", 0, 0, 1)
        topojson_result = json.loads(tile_content)

        self.assertTrue(tile_mimetype.endswith('/json'))
        print topojson_result
        self.assertEqual(topojson_result['type'], 'Topology')
        self.assertEqual(len(topojson_result['objects']['vectile']['geometries']), 2)

        cities = []

        # Make sure that the right cities have been returned and that the geometries match
        
        topojson_xform = get_topo_transform(topojson_result)

        for feature in topojson_result['objects']['vectile']['geometries']:
            lon, lat = topojson_xform(feature['coordinates'])
            
            if feature['properties']['name'] == 'San Francisco':
                cities.append(feature['properties']['name'])
                self.assertTrue(hypot(point_sf.x - lon, point_sf.y - lat) < 1)

            elif feature['properties']['name'] == 'Lima':
                cities.append(feature['properties']['name'])
                print feature['coordinates']
                self.assertTrue(hypot(point_lima.x - lon, point_lima.y - lat) < 1)

        self.assertTrue('San Francisco' in cities)
        self.assertTrue('Lima' in cities)

        ##########
        # northeast quadrant should return Berlin

        tile_mimetype, tile_content = utils.request(self.config_file_content, "vectile_test", "topojson", 0, 1, 1)
        topojson_result = json.loads(tile_content)

        self.assertTrue(tile_mimetype.endswith('/json'))
        self.assertEqual(topojson_result['type'], 'Topology')
        self.assertEqual(len(topojson_result['objects']['vectile']['geometries']), 1)
        self.assertTrue('Berlin' in topojson_result['objects']['vectile']['geometries'][0]['properties']['name'])


    def test_linestring_topojson(self):
        '''Create a line that goes from west to east (clip on)'''
        
        self.defineGeometry('LINESTRING')

        geom = LineString( [(-180, 32), (180, 32)] )

        self.insertTestRow(geom.wkt)

        # we should have a line that clips at 0...

        tile_mimetype, tile_content = utils.request(self.config_file_content, "vectile_test", "topojson", 0, 0, 0)
        self.assertTrue(tile_mimetype.endswith('/json'))
        topojson_result = json.loads(tile_content)
        topojson_xform = get_topo_transform(topojson_result)
        
        parts = [topojson_result['arcs'][arc] for arc in topojson_result['objects']['vectile']['geometries'][0]['arcs']]
        parts = [map(topojson_xform, topojson_dediff(part)) for part in parts]
        
        west_hemisphere_geometry = LineString(*parts)
        
        # Close enough?
        self.assertTrue(abs(west_hemisphere_geometry.coords[0][0] + 180) < 2)
        self.assertTrue(abs(west_hemisphere_geometry.coords[1][0] - 180) < 2)
        self.assertTrue(abs(west_hemisphere_geometry.coords[0][1] - 32) < 2)
        self.assertTrue(abs(west_hemisphere_geometry.coords[1][1] - 32) < 2)


    def test_polygon_topojson(self):
        '''
        Create a polygon to cover the world and make sure it is "similar" (clip on)
        '''
        
        self.defineGeometry('POLYGON')

        geom = Polygon( [(-180, -85.0511),
                         ( 180, -85.0511),
                         ( 180, 85.0511), 
                         (-180, 85.0511), 
                         (-180, -85.0511)])

        self.insertTestRow(geom.wkt)
        
        tile_mimetype, tile_content = utils.request(self.config_file_content, "vectile_test", "topojson", 0, 0, 0)
        self.assertTrue(tile_mimetype.endswith('/json'))
        topojson_result = json.loads(tile_content)
        topojson_xform = get_topo_transform(topojson_result)
        
        parts = [topojson_result['arcs'][arc[0]] for arc in topojson_result['objects']['vectile']['geometries'][0]['arcs']]
        parts = [map(topojson_xform, topojson_dediff(part)) for part in parts]
        
        result_geom = Polygon(*parts)
        expected_geom = Polygon( [(-180, -85.0511), (180, -85.0511), (180, 85.0511), (-180, 85.0511), (-180, -85.0511)])

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
        
        # Close enough?
        self.assertTrue(result_geom.difference(expected_geom.buffer(1)).is_empty)
        self.assertTrue(expected_geom.difference(result_geom.buffer(1)).is_empty)


    def test_linestring_multi_topojson(self):
        '''Create a line that goes from west to east (clip on), and test it in MultiProvider'''
        
        self.defineGeometry('LINESTRING')

        geom = LineString( [(-180, 32), (180, 32)] )

        self.insertTestRow(geom.wkt)

        # we should have a line that clips at 0...

        tile_mimetype, tile_content = utils.request(self.config_file_content, "vectile_multi", "topojson", 0, 0, 0)
        self.assertTrue(tile_mimetype.endswith('/json'))
        topojson_result = json.loads(tile_content)
        
        self.assertEqual(topojson_result['type'], 'Topology')
        self.assertEqual(topojson_result['objects']['vectile_test']['type'], 'GeometryCollection')
        self.assertEqual(topojson_result['objects']['vectile_copy']['type'], 'GeometryCollection')
        
        geom1 = topojson_result['objects']['vectile_test']['geometries'][0]
        geom2 = topojson_result['objects']['vectile_copy']['geometries'][0]
        self.assertEqual(geom1['type'], 'LineString')
        self.assertEqual(geom2['type'], 'LineString')
        self.assertEqual(geom1['id'], geom2['id'])
        
        self.assertTrue('clipped' not in geom1)
        self.assertTrue(geom2['clipped'])
