import sys

from os.path import join as pathjoin
from urlparse import urlparse
from httplib import HTTPConnection
from xml.dom.minidom import parse as parseXML
from StringIO import StringIO

import PIL.Image
import TileStache

class ArcRest:

    def __init__(self, layer, url):
        self.url = url

    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom):
        s, host, path, p, query, f = urlparse(self.url)

        #raise Exception(path+"?bbox=%f,%f,%f,%f&bboxSR=102113&layers=show:0&size=%d,%d&imageSR=102113&format=png24&transparent=true&f=image" % (xmin, ymin, xmax, ymax, height, width))

        conn = HTTPConnection(host, 80)
        conn.request('GET', path+"?bbox=%f,%f,%f,%f&bboxSR=102113&layers=show:0&size=%d,%d&imageSR=102113&format=png24&transparent=true&f=image" % (xmin, ymin, xmax, ymax, height, width))

        body = conn.getresponse().read()
        tile = PIL.Image.open(StringIO(body)).convert('RGBA')

        return tile
