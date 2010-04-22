#!/usr/bin/env python

from distutils.core import setup

setup(name='TileStache',
      version='0.1.6',
      description='A stylish alternative for caching your map tiles.',
      author='Michal Migurski',
      author_email='mike@stamen.com',
      url='http://tilestache.org',
      requires=['ModestMaps'],
      packages=['TileStache',
                'TileStache.Goodies',
                'TileStache.Goodies.Providers'],
      download_url='http://tilestache.org/dist/TileStache-0.1.5.tar.gz',
      license='BSD')
