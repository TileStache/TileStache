import sys

from urlparse import urlparse
from httplib import HTTPConnection
from StringIO import StringIO

import PIL.Image
import TileStache

class WMS:

    def __init__(self, layer, url, layers):
        self.url = url
        self.layers = layers

    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom):
        s, host, path, p, query, f = urlparse(self.url)

        # http://geoint.lmic.state.mn.us/cgi-bin/wmsll?VERSION=1.1.1&SERVICE=WMS&REQUEST=GetMap&layers=msp2006&bbox=-93.2492355,44.9784920,-93.2457346,44.9809684&srs=EPSG:4326&width=500&height=500
        conn = HTTPConnection(host, 80)
        fullpath = path+"?VERSION=1.1.1&SERVICE=WMS&REQUEST=GetMap&layers=%s&bbox=%f,%f,%f,%f&srs=EPSG:4326&height=%d&width=%d" % (self.layers, xmin, ymin, xmax, ymax, height, width)
        conn.request('GET', fullpath)

        response = conn.getresponse()
        if response.status != 200:
            raise Exception("Error %d on URL http://%s/%s" % (response.status, host, fullpath))
        body = response.read()
        tile = PIL.Image.open(StringIO(body)).convert('RGBA')

        return tile
