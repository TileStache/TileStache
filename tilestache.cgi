#!/usr/bin/env python

import os
import TileStache

if __name__ == '__main__':
    TileStache.cgiHandler(os.environ, 'http://10.211.55.4/~migurski/TileStache/tilestache.cfg', debug=True)
