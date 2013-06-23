""" Provider that returns GeoJSON data responses from Solr spatial queries.

This is an example of a provider that does not return an image, but rather
queries a Solr instance for raw data and replies with a string of GeoJSON.

Read more about the GeoJSON spec at: http://geojson.org/geojson-spec.html

Caveats:

Example TileStache provider configuration:

"solr": {
    "provider": {"class": "TileStache.Goodies.Providers.SolrGeoJSON.Provider",
                 "kwargs": {
                    "solr_endpoint": "http://localhost:8983/solr/example",
                    "solr_query": "*:*",
                 }}
}

The following optional parameters are also supported:

latitude_field: The name of the latitude field associated with your query parser;
the default is 'latitude'

longitude_field: The name of the longitude field associated with your query
parser, default is 'longitude

response_fields: A comma-separated list of fields with which to filter the Solr
response; the default is '' (or: include all fields)

id_field: The name name of your Solr instance's unique ID field; the default is ''.

By default queries are scoped to the bounding box of a given tile. Radial queries
are also supported if you supply a 'radius' kwarg to your provider and have installed
the JTeam spatial plugin: http://www.jteam.nl/news/spatialsolr.html.

For example:

"solr": {
    "provider": {"class": "TileStache.Goodies.Providers.SolrGeoJSON.Provider",
                 "kwargs": {
                    "solr_endpoint": "http://localhost:8983/solr/example",
                    "solr_query": 'foo:bar',
                    "radius": "1",
                 }}
}

Radial queries are begin at the center of the tile being rendered and distances are
measured in kilometers.

The following optional parameters are also supported for radial queries:

query_parser: The name of the Solr query parser associated with your spatial
plugin; the default is 'spatial'.

"""

from math import log, tan, pi, atan, pow, e

from re import compile
from json import JSONEncoder

from TileStache.Core import KnownUnknown
from TileStache.Geography import getProjectionByName

try:
    import pysolr
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
            raise KnownUnknown('SolrGeoJSON only saves .json tiles, not "%s"' % format)

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
    def __init__(self, layer, solr_endpoint, solr_query, **kwargs):
        self.projection = getProjectionByName('spherical mercator')
        self.layer = layer

        self.endpoint = str(solr_endpoint)
        self.query = solr_query

        self.solr = pysolr.Solr(self.endpoint)

        self.query_parser = kwargs.get('query_parser', 'spatial')
        self.lat_field = kwargs.get('latitude_column', 'latitude')
        self.lon_field = kwargs.get('longitude_column', 'longitude')
        self.id_field = kwargs.get('id_column', '')

        self.solr_radius = kwargs.get('radius', None)
        self.solr_fields = kwargs.get('response_fields', None)

    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.

            This only accepts "json".
        """
        if extension.lower() != 'json':
            raise KnownUnknown('PostGeoJSON only makes .json tiles, not "%s"' % extension)

        return 'application/json', 'JSON'

    def unproject(self, x, y):
        x, y = x / 6378137, y / 6378137 # dimensions of the earth
        lat, lon = 2 * atan(pow(e, y)) - .5 * pi, x # basic spherical mercator
        lat, lon = lat * 180/pi, lon * 180/pi # radians to degrees
        return lat, lon

    def renderTile(self, width, height, srs, coord):
        """ Render a single tile, return a SaveableResponse instance.
        """

        minx, miny, maxx, maxy = self.layer.envelope(coord)

        y = miny + ((maxy - miny) / 2)
        x = minx + ((maxx - minx) / 2)

        sw_lat, sw_lon = self.unproject(minx, miny)
        ne_lat, ne_lon = self.unproject(maxx, maxy)
        center_lat, center_lon = self.unproject(x, y)

        bbox = "%s:[%s TO %s] AND %s:[%s TO %s]" % (self.lon_field, sw_lon, ne_lon, self.lat_field, sw_lat, ne_lat)
        query = bbox

        # for example:
        # {!spatial lat=51.500152 long=-0.126236 radius=10 calc=arc unit=km}*:*

        if self.solr_radius:
            query = "{!%s lat=%s long=%s radius=%s calc=arc unit=km}%s" % (self.query_parser, center_lat, center_lon, self.solr_radius, bbox)

        kwargs = {}

        if self.query != '*:*':
            kwargs['fq'] = self.query

        kwargs['omitHeader'] = 'true'
        rsp_fields = []

        if self.solr_fields:

            rsp_fields = self.solr_fields.split(',')

            if not self.lat_field in rsp_fields:
                rsp_fields.append(self.lat_field)

            if not self.lon_field in rsp_fields:
                rsp_fields.append(self.lon_field)

            kwargs['fl'] = ','.join(rsp_fields)

        response = {'type': 'FeatureCollection', 'features': []}

        total = None
        start = 0
        rows = 1000

        while not total or start < total:

            kwargs['start'] = start
            kwargs['rows'] = rows

            rsp = self.solr.search(query, **kwargs)

            if not total:
                total = rsp.hits

            if total == 0:
                break

            for row in rsp:

                # hack until I figure out why passing &fl in a JSON
                # context does not actually limit the fields returned

                if len(rsp_fields):
                    for key, ignore in row.items():
                        if not key in rsp_fields:
                            del(row[key])

                row['geometry'] = {
                    'type': 'Point',
                    'coordinates': (row[ self.lon_field ], row[ self.lat_field ])
                    }

                del(row[ self.lat_field ])
                del(row[ self.lon_field ])

                if self.id_field != '':
                    row['id'] = row[ self.id_field ]

                response['features'].append(row)

            start += rows

        return SaveableResponse(response)

# -*- indent-tabs-mode:nil tab-width:4 -*-
