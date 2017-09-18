import abc
import json
try:
    from io import BytesIO
except ImportError:
    # Python 2
    from StringIO import StringIO as BytesIO

try:
    from PIL import Image
except ImportError:
    # On some systems, PIL.Image is known as Image.
    import Image

from TileStache.Core import KnownUnknown


class SaveableResponse(object):
    """
    TileStache.getTile() expects to be able to save one of these to a buffer.
    """

    @abc.abstractmethod
    def save(self, output, format_):
        pass


class ImageSaveableResponse:
    """
    Wrapper for PIL.Image that saves raw input bytes if modes and formats
    match.
    """
    def __init__(self, bytes_):
        self.buffer = BytesIO(bytes_)
        self.format = None
        self._image = None

        #
        # Guess image format based on magic number, if possible.
        # http://www.astro.keele.ac.uk/oldusers/rno/Computing/File_magic.html
        #
        magic = {
            '\x89\x50\x4e\x47': 'PNG',
            '\xff\xd8\xff\xe0': 'JPEG',
            '\x47\x49\x46\x38': 'GIF',
            '\x4d\x4d\x00\x2a': 'TIFF',
            '\x49\x49\x2a\x00': 'TIFF'
        }

        if bytes_[:4] in magic:
            self.format = magic[bytes_[:4]]

        else:
            self.format = self.image().format

    def image(self):
        """Return a guaranteed instance of PIL.Image."""
        if self._image is None:
            self._image = Image.open(self.buffer)

        return self._image

    def convert(self, mode):
        if mode == self.image().mode:
            return self
        else:
            return self.image().convert(mode)

    def crop(self, bbox):
        return self.image().crop(bbox)

    def save(self, output, format_):
        if format_ == self.format:
            output.write(self.buffer.getvalue())
        else:
            self.image().save(output, format_)


class GridSaveableResponse(SaveableResponse):
    """
    Wrapper for an UTFgrid that makes it behave like PIL.Image.
    """

    def __init__(self, content, scale=4):
        self.content = content
        self.scale = scale

    def save(self, out, format_):
        if format_ != 'JSON':
            raise KnownUnknown('MapnikGrid only saves .json tiles, not "%s"' %
                               format_)

        bytes_ = json.dumps(self.content, ensure_ascii=False).encode('utf-8')
        out.write(bytes_)

    def crop(self, bbox):
        """ Return a cropped grid response.
        """
        minchar, minrow, maxchar, maxrow = [v/self.scale for v in bbox]

        keys, data = self.content['keys'], self.content.get('data', None)
        grid = [row[minchar:maxchar]
                for row in self.content['grid'][minrow:maxrow]]

        cropped = dict(keys=keys, data=data, grid=grid)
        return GridSaveableResponse(cropped, self.scale)

