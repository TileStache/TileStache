import os

from osgeo import gdal
from osgeo import osr

import tornado.ioloop
import tornado.web

import TileStache
import TileStache.Tornado

def create_mapnik_config(layer_name, file_path, layer_srs):
    """ Creates a mapnik config file
    file_path is the absolute path to
    the geotiff file """

    return """
        <?xml version="1.0" encoding="utf-8"?>
        <!DOCTYPE Map[]>
        <Map srs="+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0.0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs +over" font-directory="./fonts">
        <Style name="raster-style">
          <Rule>
            <RasterSymbolizer>
              <RasterColorizer default-mode="linear" default-color="white" epsilon="0.001">
                <stop color="#a6611a" value = "0" />
                <stop color="#dfc27d" value = "25" />
                <stop color="#f5f5f5" value = "100" />
                <stop color="#80cdc1" value = "175"/>
                <stop color="#018571" value = "250"/>
              </RasterColorizer>
            </RasterSymbolizer>
          </Rule>
        </Style>
        <Layer name="{}" status="on" srs="{}">
        <StyleName>raster-style</StyleName>
        <Datasource>
            <Parameter name="type">gdal</Parameter>
            <Parameter name="file">{}</Parameter>
            <Parameter name="format">tiff</Parameter>
            <Parameter name="band">1</Parameter>
        </Datasource>
        </Layer>
        </Map>
        """.format(layer_name, layer_srs, file_path)


layer_name = "tornadotiff"
filename = "cea.tif"
file_path = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', '..',
                                                 'tests', 'data', filename))
raster = gdal.Open(file_path)
srs = osr.SpatialReference()
srs.ImportFromWkt(raster.GetProjectionRef())
layer_srs = srs.ExportToProj4()
mapnik_config = create_mapnik_config(layer_name, file_path, layer_srs)


config = {
    "cache": {
        "name": "Test",
        "path": "/tmp/stache",
        "umask": "0000"
    },
    "layers": {
        "{}".format(layer_name): {
            "provider": {"name": "mapnik", "mapconfig": mapnik_config},
               "projection": "spherical mercator"
        }
    }
}


if __name__ == "__main__":
    app = TileStache.Tornado.TornadoTileServer(config=config)
    app.listen(8080)
    tornado.ioloop.IOLoop.current().start()
