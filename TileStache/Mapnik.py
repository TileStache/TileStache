""" Mapnik Providers.

ImageProvider is known as "mapnik" in TileStache config, GridProvider is
known as "mapnik grid". Both require Mapnik to be installed; Grid requires
Mapnik 2.0.0 and above.
"""
from __future__ import absolute_import
from time import time
from os.path import exists
from itertools import count
from glob import glob
from tempfile import mkstemp

import os
import logging
import json

from .py3_compat import reduce, urlopen, urljoin, urlparse, allocate_lock
from .py3_compat import unichr

# We enabled absolute_import because case insensitive filesystems
# cause this file to be loaded twice (the name of this file
# conflicts with the name of the module we want to import).
# Forcing absolute imports fixes the issue.

try:
    import mapnik
except ImportError:
    # can still build documentation
    pass

from TileStache.Core import KnownUnknown
from TileStache.Geography import getProjectionByName

try:
    from PIL import Image
except ImportError:
    # On some systems, PIL.Image is known as Image.
    import Image

if 'mapnik' in locals():
    _version = hasattr(mapnik, 'mapnik_version') and mapnik.mapnik_version() or 701

    if _version >= 20000:
        Box2d = mapnik.Box2d
    else:
        Box2d = mapnik.Envelope

global_mapnik_lock = allocate_lock()

class ImageProvider:
    """ Built-in Mapnik provider. Renders map images from Mapnik XML files.

        This provider is identified by the name "mapnik" in the TileStache config.

        Arguments:

        - mapfile (required)
            Local file path to Mapnik XML file.

        - fonts (optional)
            Local directory path to *.ttf font files.

        - "scale factor" (optional)
            Scale multiplier used for Mapnik rendering pipeline. Used for
            supporting retina resolution.

            For more information about the scale factor, see:
            https://github.com/mapnik/mapnik/wiki/Scale-factor

        More information on Mapnik and Mapnik XML:
        - http://mapnik.org
        - http://trac.mapnik.org/wiki/XMLGettingStarted
        - http://trac.mapnik.org/wiki/XMLConfigReference
    """

    def __init__(self, layer, mapfile, fonts=None, scale_factor=None):
        """ Initialize Mapnik provider with layer and mapfile.

            XML mapfile keyword arg comes from TileStache config,
            and is an absolute path by the time it gets here.
        """
        maphref = urljoin(layer.config.dirpath, mapfile)
        scheme, h, path, q, p, f = urlparse(maphref)

        if scheme in ('file', ''):
            self.mapfile = path
        else:
            self.mapfile = maphref

        self.layer = layer
        self.mapnik = None

        # Maintain compatiblity between old and new Mapnik FontEngine API
        try:
            engine = mapnik.FontEngine.instance()
        except AttributeError:
            engine = mapnik.FontEngine

        if fonts:
            fontshref = urljoin(layer.config.dirpath, fonts)
            scheme, h, path, q, p, f = urlparse(fontshref)

            if scheme not in ('file', ''):
                raise Exception('Fonts from "%s" can\'t be used by Mapnik' % fontshref)

            for font in glob(path.rstrip('/') + '/*.ttf'):
                engine.register_font(str(font))

        self.scale_factor = scale_factor

    @staticmethod
    def prepareKeywordArgs(config_dict):
        """ Convert configured parameters to keyword args for __init__().
        """
        kwargs = {'mapfile': config_dict['mapfile']}

        if 'fonts' in config_dict:
            kwargs['fonts'] = config_dict['fonts']

        if 'scale factor' in config_dict:
            kwargs['scale_factor'] = int(config_dict['scale factor'])

        return kwargs

    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom):
        """
        """
        start_time = time()

        #
        # Mapnik can behave strangely when run in threads, so place a lock on the instance.
        #
        if global_mapnik_lock.acquire():
            try:
                if self.mapnik is None:
                    self.mapnik = get_mapnikMap(self.mapfile)
                    logging.debug('TileStache.Mapnik.ImageProvider.renderArea() %.3f to load %s', time() - start_time, self.mapfile)

                self.mapnik.width = width
                self.mapnik.height = height
                self.mapnik.zoom_to_box(Box2d(xmin, ymin, xmax, ymax))

                img = mapnik.Image(width, height)
                # Don't even call render with scale factor if it's not
                # defined. Plays safe with older versions.
                if self.scale_factor is None:
                    mapnik.render(self.mapnik, img)
                else:
                    mapnik.render(self.mapnik, img, self.scale_factor)
            except:
                self.mapnik = None
                raise
            finally:
                # always release the lock
                global_mapnik_lock.release()

        if hasattr(Image, 'frombytes'):
            # Image.fromstring is deprecated past Pillow 2.0
            img = Image.frombytes('RGBA', (width, height), img.tostring())
        else:
            # PIL still uses Image.fromstring
            img = Image.fromstring('RGBA', (width, height), img.tostring())

        logging.debug('TileStache.Mapnik.ImageProvider.renderArea() %dx%d in %.3f from %s', width, height, time() - start_time, self.mapfile)

        return img

class GridProvider:
    """ Built-in UTF Grid provider. Renders JSON raster objects from Mapnik.

        This provider is identified by the name "mapnik grid" in the
        Tilestache config, and uses Mapnik 2.0 (and above) to generate
        JSON UTF grid responses.

        Sample configuration for a single grid layer:

          "provider":
          {
            "name": "mapnik grid",
            "mapfile": "world_merc.xml",
            "fields": ["NAME", "POP2005"]
          }

        Sample configuration for multiple overlaid grid layers:

          "provider":
          {
            "name": "mapnik grid",
            "mapfile": "world_merc.xml",
            "layers":
            [
              [1, ["NAME"]],
              [0, ["NAME", "POP2005"]],
              [0, null],
              [0, []]
            ]
          }

        Arguments:

        - mapfile (required)
          Local file path to Mapnik XML file.

        - fields (optional)
          Array of field names to return in the response, defaults to all.
          An empty list will return no field names, while a value of null is
          equivalent to all.

        - layer_index (optional)
          Which layer from the mapfile to render, defaults to 0 (first layer).

        - layers (optional)
          Ordered list of (layer_index, fields) to combine; if provided
          layers overrides both layer_index and fields arguments.
          An empty fields list will return no field names, while a value of null
          is equivalent to all fields.

        - scale (optional)
          Scale factor of output raster, defaults to 4 (64x64).

        - layer_id_key (optional)
          If set, each item in the 'data' property will have its source mapnik
          layer name added, keyed by this value. Useful for distingushing
          between data items.

        Information and examples for UTF Grid:
        - https://github.com/mapbox/utfgrid-spec/blob/master/1.2/utfgrid.md
        - http://mapbox.github.com/wax/interaction-leaf.html
    """
    def __init__(self, layer, mapfile, fields=None, layers=None, layer_index=0, scale=4, layer_id_key=None):
        """ Initialize Mapnik grid provider with layer and mapfile.

            XML mapfile keyword arg comes from TileStache config,
            and is an absolute path by the time it gets here.
        """
        self.mapnik = None
        self.layer = layer

        maphref = urljoin(layer.config.dirpath, mapfile)
        scheme, h, path, q, p, f = urlparse(maphref)

        if scheme in ('file', ''):
            self.mapfile = path
        else:
            self.mapfile = maphref

        self.scale = scale
        self.layer_id_key = layer_id_key

        if layers:
            self.layers = layers
        else:
            self.layers = [[layer_index or 0, fields]]

    @staticmethod
    def prepareKeywordArgs(config_dict):
        """ Convert configured parameters to keyword args for __init__().
        """
        kwargs = {'mapfile': config_dict['mapfile']}

        for key in ('fields', 'layers', 'layer_index', 'scale', 'layer_id_key'):
            if key in config_dict:
                kwargs[key] = config_dict[key]

        return kwargs

    def renderArea(self, width, height, srs, xmin, ymin, xmax, ymax, zoom):
        """
        """
        start_time = time()

        #
        # Mapnik can behave strangely when run in threads, so place a lock on the instance.
        #
        if global_mapnik_lock.acquire():
            try:
                if self.mapnik is None:
                    self.mapnik = get_mapnikMap(self.mapfile)
                    logging.debug('TileStache.Mapnik.GridProvider.renderArea() %.3f to load %s', time() - start_time, self.mapfile)

                self.mapnik.width = width
                self.mapnik.height = height
                self.mapnik.zoom_to_box(Box2d(xmin, ymin, xmax, ymax))

                if self.layer_id_key is not None:
                    grids = []

                    for (index, fields) in self.layers:
                        datasource = self.mapnik.layers[index].datasource
                        if isinstance(fields, list):
                            fields = [str(f) for f in fields]
                        else:
                            fields = datasource.fields()
                        grid = mapnik.Grid(width, height)
                        mapnik.render_layer(self.mapnik, grid, layer=index, fields=fields)
                        grid = grid.encode('utf', resolution=self.scale, features=True)

                        for key in grid['data']:
                            grid['data'][key][self.layer_id_key] = self.mapnik.layers[index].name

                        grids.append(grid)

                    # global_mapnik_lock.release()
                    outgrid = reduce(merge_grids, grids)

                else:
                    grid = mapnik.Grid(width, height)

                    for (index, fields) in self.layers:
                        datasource = self.mapnik.layers[index].datasource
                        fields = (type(fields) is list) and map(str, fields) or datasource.fields()

                        mapnik.render_layer(self.mapnik, grid, layer=index, fields=fields)

                    # global_mapnik_lock.release()
                    outgrid = grid.encode('utf', resolution=self.scale, features=True)
            except:
                self.mapnik = None
                raise
            finally:
                global_mapnik_lock.release()

        logging.debug('TileStache.Mapnik.GridProvider.renderArea() %dx%d at %d in %.3f from %s', width, height, self.scale, time() - start_time, self.mapfile)

        return SaveableResponse(outgrid, self.scale)

    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.

            This only accepts "json".
        """
        if extension.lower() != 'json':
            raise KnownUnknown('MapnikGrid only makes .json tiles, not "%s"' % extension)

        return 'application/json; charset=utf-8', 'JSON'

class SaveableResponse:
    """ Wrapper class for JSON response that makes it behave like a PIL.Image object.

        TileStache.getTile() expects to be able to save one of these to a buffer.
    """
    def __init__(self, content, scale):
        self.content = content
        self.scale = scale

    def save(self, out, format):
        if format != 'JSON':
            raise KnownUnknown('MapnikGrid only saves .json tiles, not "%s"' % format)

        bytes_ = json.dumps(self.content, ensure_ascii=False).encode('utf-8')
        out.write(bytes_)

    def crop(self, bbox):
        """ Return a cropped grid response.
        """
        minchar, minrow, maxchar, maxrow = [v/self.scale for v in bbox]

        keys, data = self.content['keys'], self.content.get('data', None)
        grid = [row[minchar:maxchar] for row in self.content['grid'][minrow:maxrow]]

        cropped = dict(keys=keys, data=data, grid=grid)
        return SaveableResponse(cropped, self.scale)

def merge_grids(grid1, grid2):
    """ Merge two UTF Grid objects.
    """
    #
    # Concatenate keys and data, assigning new indexes along the way.
    #

    keygen, outkeys, outdata = count(1), [], dict()

    for ingrid in [grid1, grid2]:
        for (index, key) in enumerate(ingrid['keys']):
            if key not in ingrid['data']:
                outkeys.append('')
                continue

            outkey = '%d' % keygen.next()
            outkeys.append(outkey)

            datum = ingrid['data'][key]
            outdata[outkey] = datum

    #
    # Merge the two grids, one on top of the other.
    #

    offset, outgrid = len(grid1['keys']), []

    def newchar(char1, char2):
        """ Return a new encoded character based on two inputs.
        """
        id1, id2 = decode_char(char1), decode_char(char2)

        if grid2['keys'][id2] == '':
            # transparent pixel, use the bottom character
            return encode_id(id1)

        else:
            # opaque pixel, use the top character
            return encode_id(id2 + offset)

    for (row1, row2) in zip(grid1['grid'], grid2['grid']):
        outrow = [newchar(c1, c2) for (c1, c2) in zip(row1, row2)]
        outgrid.append(''.join(outrow))

    return dict(keys=outkeys, data=outdata, grid=outgrid)

def encode_id(id):
    id += 32
    if id >= 34:
        id = id + 1
    if id >= 92:
        id = id + 1
    if id > 127:
        return unichr(id)
    return chr(id)

def decode_char(char):
    id = ord(char)
    if id >= 93:
        id = id - 1
    if id >= 35:
        id = id - 1
    return id - 32

def get_mapnikMap(mapfile):
    """ Get a new mapnik.Map instance for a mapfile
    """
    mmap = mapnik.Map(0, 0)

    if exists(mapfile):
        mapnik.load_map(mmap, str(mapfile))

    else:
        handle, filename = mkstemp()
        os.write(handle, urlopen(mapfile).read())
        os.close(handle)

        mapnik.load_map(mmap, filename)
        os.unlink(filename)

    return mmap
