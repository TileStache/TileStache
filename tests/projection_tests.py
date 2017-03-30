# This Python file uses the following encoding: utf-8

from __future__ import print_function

from unittest import TestCase, skipIf

from TileStache.Goodies.Proj4Projection import Proj4Projection
from ModestMaps.Core import Point, Coordinate
from ModestMaps.Geo import Transformation

class ProjectionTests(TestCase):

    def assertEqualPoint(self, p1, p2):
        self.assertEqual(p1.x, p2.x)
        self.assertEqual(p1.y, p2.y)

    def assertEqualCoordinate(self, c1, c2):
        self.assertEqual(c1.column, c2.column)
        self.assertEqual(c1.row, c2.row)
        self.assertEqual(c1.zoom, c2.zoom)

    def test_projection(self):
        '''Test projection functions'''

        # Set up two WGS84 projections, whose coordinates are from -180° to 180°, and -90° to 90°.

        # The world at zoom 0 should be 512×256px
        resolutions = [180.0 / 256, 90.0 / 256, 45.0 / 256, 1.0]

        # With the identity transformation, the tiles will be centred at 0°,0° — the tile at
        # 0/0/0 will only show ¼ of the world (part of the tile is blank), and 0/-1/0 is on the
        # western hemisphere
        identity = Transformation(1, 0, 0, 0, 1, 0)

        # With a flip and translation, the tile origin will be -180°,-90°.
        # 0/0/0 and 0/1/0 cover the western and eastern hemispheres.
        translate = Transformation(1, 0, 180.0, 0, -1, 90.0)

        projCentreOrigin = Proj4Projection('+proj=longlat +ellps=WGS84 +datum=WGS84 +units=degrees',
                                           resolutions,
                                           transformation=identity)

        projCornerOrigin = Proj4Projection('+proj=longlat +ellps=WGS84 +datum=WGS84 +units=degrees',
                                           resolutions,
                                           transformation=translate)

        # Find the projected coordinates of the 0/0/0 tile.
        coord = Coordinate(0, 0, 0)
        print('Centre origin tile', coord)
        ul = projCentreOrigin.coordinateProj(coord)
        print('UL at', ul)
        self.assertEqualPoint(ul, Point(0,0))

        lr = projCentreOrigin.coordinateProj(coord.down().right())
        print('LR at', lr)
        self.assertEqualPoint(lr, Point(180,180))

        c1 = projCentreOrigin.projCoordinate(ul, 0)
        self.assertEqualCoordinate(c1, coord)

        c2 = projCentreOrigin.projCoordinate(lr, 0)
        self.assertEqualCoordinate(c2, coord.down().right())

        print('--')

        coord = Coordinate(0, 1, 0)
        print('Corner origin tile', coord, coord.column)
        print('Opposite corner tile', coord.down().right())
        ul = projCornerOrigin.coordinateProj(coord)
        print('UL at', ul)
        self.assertEqualPoint(ul, Point(0,90))

        lr = projCornerOrigin.coordinateProj(coord.down().right())
        print('LR at', lr)
        self.assertEqualPoint(lr, Point(180,-90))

        c1 = projCornerOrigin.projCoordinate(ul, 0)
        self.assertEqualCoordinate(c1, coord)

        c2 = projCornerOrigin.projCoordinate(lr, 0)
        self.assertEqualCoordinate(c2, coord.down().right())

        print('--')

        coord = Coordinate(1, 1, 2)
        print('Corner origin tile', coord)
        print('Opposite corner tile', coord.down().right())
        ul = projCornerOrigin.coordinateProj(coord)
        print('UL at', ul)
        self.assertEqualPoint(ul, Point(-135,45))

        lr = projCornerOrigin.coordinateProj(coord.down().right())
        print('LR at', lr)
        self.assertEqualPoint(lr, Point(-90,0))

        c1 = projCornerOrigin.projCoordinate(ul, 2)
        self.assertEqualCoordinate(c1, coord)

        c2 = projCornerOrigin.projCoordinate(lr, 2)
        self.assertEqualCoordinate(c2, coord.down().right())
