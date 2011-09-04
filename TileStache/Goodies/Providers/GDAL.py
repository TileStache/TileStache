""" Minimally-tested GDAL image provider.

Based on existing work in OAM (https://github.com/oam/oam), this GDAL provider
is the bare minimum necessary to do simple output of GDAL data sources.

Sample configuration:

    "provider":
    {
      "class": "TileStache.Goodies.Providers.GDAL:Provider",
      "kwargs": { "filename": "landcover-1km.tif", "resample": "linear" }
    }

Valid values for resample are "cubic", "linear", and "nearest".

With a bit more work, this provider will be ready for fully-supported inclusion
in TileStache proper. Until then, it will remain here in the Goodies package.
"""
from urlparse import urlparse, urljoin

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

resamplings = {'cubic': gdal.GRA_Cubic, 'linear': gdal.GRA_Bilinear, 'nearest': gdal.GRA_NearestNeighbour}

class Provider:

    def __init__(self, layer, filename, resample='cubic'):
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
    
    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom):
        """
        """
        src_ds = gdal.Open(str(self.filename))
        driver = gdal.GetDriverByName('GTiff')
        
        grayscale_src = (src_ds.RasterCount == 1)

        try:
            # Prepare output gdal datasource -----------------------------------
            
            area_ds = driver.Create('/vsimem/output', width, height, 3)
            
            if area_ds is None:
                raise Exception('uh oh.')
            
            merc = osr.SpatialReference()
            merc.ImportFromProj4(srs)
            area_ds.SetProjection(merc.ExportToWkt())
    
            # note that 900913 points north and east
            x, y = xmin, ymax
            w, h = xmax - xmin, ymin - ymax
            
            gtx = [x, w/width, 0, y, 0, h/height]
            area_ds.SetGeoTransform(gtx)
            
            # Create rendered area ---------------------------------------------
            
            gdal.ReprojectImage(src_ds, area_ds, src_ds.GetProjection(), area_ds.GetProjection(), self.resample)
            
            channel = grayscale_src and (1, 1, 1) or (1, 2, 3)
            r, g, b = [area_ds.GetRasterBand(i).ReadRaster(0, 0, width, height) for i in channel]
            data = ''.join([''.join(pixel) for pixel in zip(r, g, b)])
            area = Image.fromstring('RGB', (width, height), data)

        finally:
            driver.Delete('/vsimem/output')
        
        return area
