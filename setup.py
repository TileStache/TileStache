#!/usr/bin/env python

from distutils.core import setup
import pkg_resources
import sys


version = open('TileStache/VERSION', 'r').read().strip()


def is_installed(name):
    try:
        pkg_resources.get_distribution(name)
        return True
    except:
        return False


requires = ['ModestMaps >=1.3.0','simplejson', 'Werkzeug']

# Soft dependency on PIL or Pillow
if is_installed('Pillow') or sys.platform == 'win32':
    requires.append('Pillow')
else:
    requires.append('PIL')


setup(name='TileStache',
      version=version,
      description='A stylish alternative for caching your map tiles.',
      author='Michal Migurski',
      author_email='mike@stamen.com',
      url='http://tilestache.org',
      install_requires=requires,
      packages=['TileStache',
                'TileStache.Vector',
                'TileStache.Goodies',
                'TileStache.Goodies.Caches',
                'TileStache.Goodies.Providers',
                'TileStache.Goodies.VecTiles'],
      scripts=['scripts/tilestache-compose.py', 'scripts/tilestache-seed.py', 'scripts/tilestache-clean.py', 'scripts/tilestache-server.py', 'scripts/tilestache-render.py', 'scripts/tilestache-list.py'],
      data_files=[('share/tilestache', ['TileStache/Goodies/Providers/DejaVuSansMono-alphanumeric.ttf'])],
      package_data={'TileStache': ['VERSION', '../doc/*.html']},
      license='BSD')
