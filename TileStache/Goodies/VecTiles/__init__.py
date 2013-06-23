''' VecTiles implements client and server support for efficient vector tiles.

VecTiles implements a TileStache Provider that returns tiles with contents
simplified, precision reduced and often clipped. The MVT format in particular
is designed for use in Mapnik with the VecTiles Datasource, which can read
binary MVT tiles.

VecTiles generates tiles in two JSON formats, GeoJSON and TopoJSON.

VecTiles also provides Mapnik with a Datasource that can read remote tiles of
vector data in spherical mercator projection, providing for rendering of data
without the use of a local PostGIS database.

Sample usage in Mapnik configuration XML:
    
 <Layer name="test" srs="+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +no_defs">
     <StyleName>...</StyleName>
     <Datasource>
         <Parameter name="type">python</Parameter>
         <Parameter name="factory">TileStache.Goodies.VecTiles:Datasource</Parameter>
         <Parameter name="template">http://example.com/{z}/{x}/{y}.mvt</Parameter>
     </Datasource>
 </Layer>

Sample usage in a TileStache configuration, for a layer with no results at
zooms 0-9, basic selection of lines with names and highway tags for zoom 10,
a remote URL containing a query for zoom 11, and a local file for zooms 12+:

  "provider":
  {
    "class": "TileStache.Goodies.VecTiles:Provider",
    "kwargs":
    {
      "dbinfo":
      {
        "host": "localhost",
        "user": "gis",
        "password": "gis",
        "database": "gis"
      },
      "queries":
      [
        null, null, null, null, null,
        null, null, null, null, null,
        "SELECT way AS geometry, highway, name FROM planet_osm_line -- zoom 10+ ",
        "http://example.com/query-z11.pgsql",
        "query-z12-plus.pgsql"
      ]
    }
  }
'''

from .server import Provider, MultiProvider
from .client import Datasource
