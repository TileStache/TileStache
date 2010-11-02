import sys

from urlparse import urlparse
from httplib import HTTPConnection
from StringIO import StringIO

import PIL.Image
import TileStache

class ArcRest:

    def __init__(self, layer, url, layers):
        self.url = url
        self.layers = layers

    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom):
        s, host, path, p, query, f = urlparse(self.url)

        conn = HTTPConnection(host, 80)
        conn.request('GET', path+"?bbox=%f,%f,%f,%f&bboxSR=102113&layers=%s&size=%d,%d&imageSR=102113&format=png24&transparent=true&f=image" % (xmin, ymin, xmax, ymax, self.layers, height, width))

        body = conn.getresponse().read()
        tile = PIL.Image.open(StringIO(body)).convert('RGBA')

        return tile
