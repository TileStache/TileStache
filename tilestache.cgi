#!/usr/bin/env python

import os
import TileStache

if __name__ == '__main__':
    TileStache.cgiHandler(os.environ, 'examples/composite/composite.cfg', debug=True)
