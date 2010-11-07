import sys

import urllib
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

        body = urllib.urlopen(url).read()
        tile = PIL.Image.open(StringIO(body)).convert('RGBA')

        return tile
