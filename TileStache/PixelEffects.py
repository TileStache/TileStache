""" Different effects that can be applied to tiles.

Options are:

- blackwhite:

    "effect":
    {
        "name": "blackwhite"
    }

- greyscale:

    "effect":
    {
        "name": "greyscale"
    }

- desaturate:
  Has an optional parameter "factor" that defines the saturation of the image.
  Defaults to 0.85.

    "effect":
    {
        "name": "desaturate",
        "factor": 0.85
    }

- pixelate:
  Has an optional parameter "reduction" that defines how pixelated the image
  will be (size of pixel). Defaults to 5.

    "effect":
    {
        "name": "pixelate",
        "factor": 5
    }

- halftone:

    "effect":
    {
        "name": "halftone"
    }

- blur:
  Has an optional parameter "radius" that defines the blurriness of an image.
  Larger radius means more blurry. Defaults to 5.

    "effect":
    {
        "name": "blur",
        "radius": 5
    }
"""

from PIL import Image, ImageFilter


def put_original_alpha(original_image, new_image):
    """ Put alpha channel of original image (if any) in the new image.
    """

    try:
        alpha_idx = original_image.mode.index('A')
        alpha_channel = original_image.split()[alpha_idx]
        new_image.putalpha(alpha_channel)
    except ValueError:
        pass
    return new_image


class PixelEffect:
    """ Base class for all pixel effects.
        Subclasses must implement method `apply_effect`.
    """

    def __init__(self):
        pass

    def apply(self, image):
        try:
            image = image.image()  # Handle Providers.Verbatim tiles
        except (AttributeError, TypeError):
            pass
        return self.apply_effect(image)

    def apply_effect(self, image):
        raise NotImplementedError(
            'PixelEffect subclasses must implement method `apply_effect`.'
        )


class Blackwhite(PixelEffect):
    """ Returns a black and white version of the original image.
    """

    def apply_effect(self, image):
        new_image = image.convert('1').convert(image.mode)
        return put_original_alpha(image, new_image)


class Greyscale(PixelEffect):
    """ Returns a grescale version of the original image.
    """

    def apply_effect(self, image):
        return image.convert('LA').convert(image.mode)


class Desaturate(PixelEffect):
    """ Returns a desaturated version of the original image.
        `factor` is a number between 0 and 1, where 1 results in a
        greyscale image (no color), and 0 results in the original image.
    """

    def __init__(self, factor=0.85):
        self.factor = min(max(factor, 0.0), 1.0)  # 0.0 <= factor <= 1.0

    def apply_effect(self, image):
        avg = image.convert('LA').convert(image.mode)
        return Image.blend(image, avg, self.factor)


class Pixelate(PixelEffect):
    """ Returns a pixelated version of the original image.
        `reduction` defines how pixelated the image will be (size of pixels).
    """

    def __init__(self, reduction=5):
        self.reduction = max(reduction, 1)  # 1 <= reduction

    def apply_effect(self, image):
        tmp_size = (int(image.size[0] / self.reduction),
                    int(image.size[1] / self.reduction))
        pixelated = image.resize(tmp_size, Image.NEAREST)
        return pixelated.resize(image.size, Image.NEAREST)


class Halftone(PixelEffect):
    """ Returns a halftone version of the original image.
    """

    def apply_effect(self, image):
        cmyk = []
        for band in image.convert('CMYK').split():
            cmyk.append(band.convert('1').convert('L'))
        new_image = Image.merge('CMYK', cmyk).convert(image.mode)
        return put_original_alpha(image, new_image)


class Blur(PixelEffect):
    """ Returns a blurred version of the original image.
        `radius` defines the blurriness of an image. Larger radius means more
        blurry.
    """

    def __init__(self, radius=5):
        self.radius = max(radius, 0)  # 0 <= radius

    def apply_effect(self, image):
        return image.filter(ImageFilter.GaussianBlur(self.radius))


all = {
    'blackwhite': Blackwhite,
    'greyscale': Greyscale,
    'desaturate': Desaturate,
    'pixelate': Pixelate,
    'halftone': Halftone,
    'blur': Blur,
}
