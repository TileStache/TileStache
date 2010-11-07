import sys

from urlparse import urlparse
from httplib import HTTPConnection
from StringIO import StringIO
from string import Template

import PIL.Image
import TileStache

class UrlTemplate:

    def __init__(self, layer, template):
        self.template = template

    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom):
        url = Template(self.template).safe_substitute(width=width,
                                                      height=height,
                                                      srs=srs,
                                                      xmin=xmin,
                                                      ymin=ymin,
                                                      xmax=xmax,
                                                      ymax=ymax,
                                                      zoom=zoom)

        s, host, path, p, query, f = urlparse(url)

        conn = HTTPConnection(host, 80)
        conn.request('GET', path)
        #conn.request('GET', path+"?bbox=%f,%f,%f,%f&bboxSR=102113&layers=%s&size=%d,%d&imageSR=102113&format=png24&transparent=true&f=image" % (xmin, ymin, xmax, ymax, self.layers, height, width))

        body = conn.getresponse().read()
        tile = PIL.Image.open(StringIO(body)).convert('RGBA')

        return tile
