''' Cascadenik Provider.

Simple wrapper for TileStache Mapnik provider that parses Cascadenik MML files
directly, skipping the typical compilation to XML step.

More information on Cascadenik:
- https://github.com/mapnik/Cascadenik/wiki/Cascadenik

Requires Cascadenik 2.x+.
'''
from tempfile import gettempdir

try:
    from ...Mapnik import ImageProvider, mapnik
    from cascadenik import load_map
except ImportError:
    # can still build documentation
    pass

class Provider (ImageProvider):
    """ Renders map images from Cascadenik MML files.
    
        Arguments:
        
        - mapfile (required)
            Local file path to Mapnik XML file.
    
        - fonts (optional)
            Local directory path to *.ttf font files.
    
        - workdir (optional)
            Directory path for working files, tempfile.gettempdir() by default.
    """
    def __init__(self, layer, mapfile, fonts=None, workdir=None):
        """ Initialize Cascadenik provider with layer and mapfile.
        """
        self.workdir = workdir or gettempdir()
        self.mapnik = None

        ImageProvider.__init__(self, layer, mapfile, fonts)

    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom):
        """ Mostly hand off functionality to Mapnik.ImageProvider.renderArea()
        """
        if self.mapnik is None:
            self.mapnik = mapnik.Map(0, 0)
            load_map(self.mapnik, str(self.mapfile), self.workdir, cache_dir=self.workdir)
        
        return ImageProvider.renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom)
