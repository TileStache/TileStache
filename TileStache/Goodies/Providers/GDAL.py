""" Minimally-tested GDAL image provider.

Based on existing work in OAM (https://github.com/oam/oam), this GDAL provider
is the bare minimum necessary to do simple output of GDAL data sources.

Sample configuration:

    "provider":
    {
      "class": "TileStache.Goodies.Providers.GDAL:Provider",
      "kwargs": { "filename": "landcover-1km.tif", "resample": "linear", "maskband": 2 }
    }

Valid values for resample are "cubic", "cubicspline", "linear", and "nearest".

The maskband argument is optional. If present and greater than 0, it specifies
the GDAL dataset band whose mask should be used as an alpha channel. If maskband
is 0 (the default), do not create an alpha channel.

With a bit more work, this provider will be ready for fully-supported inclusion
in TileStache proper. Until then, it will remain here in the Goodies package.
"""
import struct

try:
    from urllib.parse import urljoin, urlparse
except ImportError:
    # Python 2
    from urlparse import urljoin, urlparse
try:
    from PIL import Image
except ImportError:
    import Image

try:
    from osgeo import gdal
    from osgeo import osr
except ImportError:
    # well it won't work but we can still make the documentation.
    pass

resamplings = {'cubic': gdal.GRA_Cubic, 'cubicspline': gdal.GRA_CubicSpline, 'linear': gdal.GRA_Bilinear, 'nearest': gdal.GRA_NearestNeighbour}

class Provider:

    def __init__(self, layer, filename, resample='cubic', maskband=0):
        """
        """
        self.layer = layer

        fileurl = urljoin(layer.config.dirpath, filename)
        scheme, h, file_path, p, q, f = urlparse(fileurl)

        if scheme not in ('', 'file'):
            raise Exception('GDAL file must be on the local filesystem, not: '+fileurl)

        if resample not in resamplings:
            raise Exception('Resample must be "cubic", "linear", or "nearest", not: '+resample)

        self.filename = file_path
        self.resample = resamplings[resample]
        self.maskband = maskband

    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom):
        """
        """
        src_ds = gdal.Open(str(self.filename))
        driver = gdal.GetDriverByName('GTiff')

        if src_ds.GetGCPs():
            src_ds.SetProjection(src_ds.GetGCPProjection())

        grayscale_src = (src_ds.RasterCount == 1)

        try:
            # Prepare output gdal datasource -----------------------------------

            area_ds = driver.Create('/vsimem/output', width, height, 3)

            if area_ds is None:
                raise Exception('uh oh.')

            # If we are using a mask band, create a data set which possesses a 'NoData' value enabling us to create a
            # mask for validity.
            mask_ds = None
            if self.maskband > 0:
                # We have to create a mask dataset with the same number of bands as the input since there isn't an
                # efficient way to extract a single band from a dataset which doesn't risk attempting to copy the entire
                # dataset.
                mask_ds = driver.Create('/vsimem/alpha', width, height, src_ds.RasterCount, gdal.GDT_Float32)

                if mask_ds is None:
                    raise Exception('Failed to create dataset mask.')

                [mask_ds.GetRasterBand(i).SetNoDataValue(float('nan')) for i in xrange(1, src_ds.RasterCount+1)]

            merc = osr.SpatialReference()
            merc.ImportFromProj4(srs)
            area_ds.SetProjection(merc.ExportToWkt())
            if mask_ds is not None:
                mask_ds.SetProjection(merc.ExportToWkt())

            # note that 900913 points north and east
            x, y = xmin, ymax
            w, h = xmax - xmin, ymin - ymax

            gtx = [x, w/width, 0, y, 0, h/height]
            area_ds.SetGeoTransform(gtx)
            if mask_ds is not None:
                mask_ds.SetGeoTransform(gtx)

            # Adjust resampling method -----------------------------------------

            resample = self.resample

            if resample == gdal.GRA_CubicSpline:
                #
                # I've found through testing that when ReprojectImage is used
                # on two same-scaled datasources, GDAL will visibly darken the
                # output and the results look terrible. Switching resampling
                # from cubic spline to bicubic in these cases fixes the output.
                #
                xscale = area_ds.GetGeoTransform()[1] / src_ds.GetGeoTransform()[1]
                yscale = area_ds.GetGeoTransform()[5] / src_ds.GetGeoTransform()[5]
                diff = max(abs(xscale - 1), abs(yscale - 1))

                if diff < .001:
                    resample = gdal.GRA_Cubic

            # Create rendered area ---------------------------------------------

            src_sref = osr.SpatialReference()
            src_sref.ImportFromWkt(src_ds.GetProjection())

            gdal.ReprojectImage(src_ds, area_ds, src_ds.GetProjection(), area_ds.GetProjection(), resample)
            if mask_ds is not None:
                # Interpolating validity makes no sense and so we can use nearest neighbour resampling here no matter
                # what is requested.
                gdal.ReprojectImage(src_ds, mask_ds, src_ds.GetProjection(), mask_ds.GetProjection(), gdal.GRA_NearestNeighbour)

            channel = grayscale_src and (1, 1, 1) or (1, 2, 3)
            r, g, b = [area_ds.GetRasterBand(i).ReadRaster(0, 0, width, height) for i in channel]

            if mask_ds is None:
                data = b''.join([struct.pack('BBB', *pixel) for pixel in zip(r, g, b)])
                area = Image.frombytes('RGB', (width, height), data)
            else:
                a = mask_ds.GetRasterBand(self.maskband).GetMaskBand().ReadRaster(0, 0, width, height)
                data = b''.join([struct.pack('BBBB', *pixel) for pixel in zip(r, g, b, a)])
                area = Image.frombytes('RGBA', (width, height), data)

        finally:
            driver.Delete('/vsimem/output')
            if self.maskband > 0:
                driver.Delete('/vsimem/alpha')

        return area
