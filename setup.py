#!/usr/bin/env python

from distutils.core import setup

setup(name='TileStache',
      version='0.1.4',
      description='A stylish alternative for caching your tiles.',
      author='Michal Migurski',
      author_email='mike@stamen.com',
      url='http://tilestache.org',
      requires=['ModestMaps'],
      packages=['TileStache',
                'TileStache.Goodies',
                'TileStache.Goodies.Providers'],
      download_url='http://tilestache.org/dist/TileStache-0.1.4.tar.gz',
      license='BSD')
