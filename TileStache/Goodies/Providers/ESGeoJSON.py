""" Provider that returns GeoJSON data responses from Elastic Search queries.

This is an example of a provider that does not return an image, but rather
queries a Elastic Search instance for raw data and replies with a string of GeoJSON.

Read more about the GeoJSON spec at: http://geojson.org/geojson-spec.html

Caveats:

Example TileStache provider configuration:

"ES": {
    "provider": {"class": "TileStache.Goodies.Providers.ESGeoJSON.Provider",
                 "kwargs": {
                    "es_endpoint": "http://localhost:9200",
                    "es_index":"my_index",
                    "es_record": "place.location"
                 }}
}

"""

from math import pi, atan, pow, e

from re import compile
from json import JSONEncoder

from TileStache.Core import KnownUnknown
from TileStache.Geography import getProjectionByName

try:
    from elasticsearch import Elasticsearch
except ImportError:
    # well it won't work but we can still make the documentation.
    pass


class SaveableResponse:
    """ Wrapper class for JSON response that makes it behave like a PIL.Image object.

        TileStache.getTile() expects to be able to save one of these to a buffer.
    """

    def __init__(self, content):
        self.content = content


    def save(self, out, format):
        if format != 'JSON':
            raise KnownUnknown('ESGeoJSON only saves .json tiles, not "%s"' % format)

        encoded = JSONEncoder(indent=2).iterencode(self.content)
        float_pat = compile(r'^-?\d+\.\d+$')

        for atom in encoded:
            if float_pat.match(atom):
                out.write('%.6f' % float(atom))
            else:
                out.write(atom)


class Provider:
    """
    """

    def __init__(self, layer, es_endpoint, es_index, es_record, **kwargs):
        self.projection = getProjectionByName('spherical mercator')
        self.layer = layer

        self.endpoint = str(es_endpoint)
        self.index = str(es_index)
        self.index = str(es_record)

        self.es = Elasticsearch()

        self.lat_field = kwargs.get('latitude_column', 'latitude')
        self.lon_field = kwargs.get('longitude_column', 'longitude')
        self.id_field = kwargs.get('id_column', '')


    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.

            This only accepts "json".
        """
        if extension.lower() != 'json':
            raise KnownUnknown('ESGeoJSON only makes .json tiles, not "%s"' % extension)

        return 'application/json', 'JSON'

    def unproject(self, x, y):
        x, y = x / 6378137, y / 6378137  # dimensions of the earth
        lat, lon = 2 * atan(pow(e, y)) - .5 * pi, x  # basic spherical mercator
        lat, lon = lat * 180 / pi, lon * 180 / pi  # radians to degrees
        return lat, lon

    def renderTile(self, width, height, srs, coord):
        """ Render a single tile, return a SaveableResponse instance.
        """
        minx, miny, maxx, maxy = self.layer.envelope(coord)

        sw_lat, sw_lon = self.unproject(minx, miny)
        ne_lat, ne_lon = self.unproject(maxx, maxy)

        response = {'type': 'FeatureCollection', 'features': []}

        rsp = self.es.search(
            index="places",
            size=100,
            body={
                "query": {
                    "filtered": {
                        "query": {
                            "match_all": {}
                        },
                        "filter": {"geo_bounding_box": {
                            "place.location": {"top":ne_lat,"left":sw_lon,"bottom":sw_lat,"right":-ne_lon}
                        }}
                    }
                }
            }
        )

        if int(rsp['hits']['total']) > 0:
            for hit in rsp['hits']['hits']:
                feature = hit["_source"]
                row = {
                  "type": "Feature",
                  "geometry": {
                    "type": "Point",
                    "coordinates": [feature["location"]["lon"], feature["location"]["lat"]]
                  }
                }
                response['features'].append(row)

        return SaveableResponse(response)

# -*- indent-tabs-mode:nil tab-width:4 -*-
