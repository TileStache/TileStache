import numpy
import Image

class Layer:
    """
    """
    def __init__(self, input):
        """
        """
        if input.__class__ is Image.Image:
            self._rgba = _img2rgba(input)
        elif type(input) is list and len(input) == 4:
            self._rgba = input
        else:
            raise TypeError("Layer wants an Image or four channel arrays, not %s" % repr(input.__class__))

    def size(self):
        return self._rgba[0].shape
    
    def rgba(self, width, height):
        """
        """
        w, h = self.size()
        
        if w == width and h == height:
            return self._rgba

        #
        # In theory, this should bring back a right-sized image.
        #
        r, g, b, a = [numpy.zeros((width, height), dtype=float) for i in '1234']

        w = min(w, width)
        h = min(h, height)
        
        r[:w,:h] = self._rgba[0]
        g[:w,:h] = self._rgba[1]
        b[:w,:h] = self._rgba[2]
        a[:w,:h] = self._rgba[3]
        
        return r, g, b, a
    
    def image(self):
        """
        """
        return _rgba2img(self._rgba)
    
    def add(self, other, mask=None):
        """ Return a new Layer, 
        """
        #
        # Choose an output size based on the first input that has one.
        #
        if self.size():
            dim = self.size()
        elif other.size():
            dim = other.size()
        elif mask and mask.size():
            dim = mask.size()
        else:
            dim = 1, 1
        
        bottom_rgba = self.rgba(*dim)
        alpha_chan = other.rgba(*dim)[3]
        top_rgb = other.rgba(*dim)[0:3]
        
        if mask is not None:
            #
            # Use the RGB information from the supplied mask,
            # but convert it to a single channel as in YUV:
            # http://en.wikipedia.org/wiki/YUV#Conversion_to.2Ffrom_RGB
            #
            mask_r, mask_g, mask_b = mask.rgba(*dim)[0:3]
            mask_lum = 0.299 * mask_r + 0.587 * mask_g + 0.114 * mask_b
            alpha_chan *= mask_lum
        
        output_rgba = blend_images(bottom_rgba, top_rgb, alpha_chan, 1, None)
        
        return Layer(output_rgba)

class Color (Layer):
    """
    """
    def __init__(self, red, green, blue):
        self._rgb = red / 255., green / 255., blue / 255.
    
    def size(self):
        return None
    
    def rgba(self, width, height):
        """
        """
        r = numpy.ones((width, height)) * self._rgb[0]
        g = numpy.ones((width, height)) * self._rgb[1]
        b = numpy.ones((width, height)) * self._rgb[2]
        a = numpy.ones((width, height))
        
        return r, g, b, a

def blend_images(bottom_rgba, top_rgb, mask_chan, opacity, blendmode):
    """ Blend images using a given mask, opacity, and blend mode.
    
        Working blend modes:
        None for plain pass-through, "screen", "multiply", "linear light", and "hard light".
    """
    if opacity == 0 or not mask_chan.any():
        # no-op for zero opacity or empty mask
        return [numpy.copy(chan) for chan in bottom_rgba]
    
    # prepare unitialized output arrays
    output_rgba = [numpy.empty_like(chan) for chan in bottom_rgba]
    
    if not blendmode:
        # plain old paste
        output_rgba[:3] = [numpy.copy(chan) for chan in top_rgb]

    else:
        blend_functions = {'screen': blend_channels_screen,
                           'multiply': blend_channels_multiply,
                           'linear light': blend_channels_linear_light,
                           'hard light': blend_channels_hard_light}

        if blendmode in blend_functions:
            for c in (0, 1, 2):
                blend_function = blend_functions[blendmode]
                output_rgba[c] = blend_function(bottom_rgba[c], top_rgb[c])
        
        else:
            raise KnownUnknown('Unrecognized blend mode: "%s"' % blendmode)
    
    # comined effective mask channel
    if opacity < 1:
        mask_chan = mask_chan * opacity

    # pixels from mask that aren't full-white
    gr = mask_chan < 1
    
    if gr.any():
        # we have some shades of gray to take care of
        for c in (0, 1, 2):
            #
            # Math borrowed from Wikipedia; C0 is the variable alpha_denom:
            # http://en.wikipedia.org/wiki/Alpha_compositing#Analytical_derivation_of_the_over_operator
            #
            
            alpha_denom = 1 - (1 - mask_chan) * (1 - bottom_rgba[3])
            nz = alpha_denom > 0 # non-zero alpha denominator
            
            alpha_ratio = mask_chan[nz] / alpha_denom[nz]
            
            output_rgba[c][nz] = output_rgba[c][nz] * alpha_ratio \
                               + bottom_rgba[c][nz] * (1 - alpha_ratio)
            
            # let the zeros perish
            output_rgba[c][~nz] = 0
    
    # output mask is the screen of the existing and overlaid alphas
    output_rgba[3] = blend_channels_screen(bottom_rgba[3], mask_chan)

    return output_rgba

def blend_channels_screen(bottom_chan, top_chan):
    """ Return combination of bottom and top channels.
    
        Math from http://illusions.hu/effectwiki/doku.php?id=screen_blending
    """
    return 1 - (1 - bottom_chan[:,:]) * (1 - top_chan[:,:])

def _arr2img(ar):
    """ Convert Numeric array to PIL Image.
    """
    return Image.fromstring('L', (ar.shape[1], ar.shape[0]), ar.astype(numpy.ubyte).tostring())

def _img2arr(im):
    """ Convert PIL Image to Numeric array.
    """
    assert im.mode == 'L'
    return numpy.reshape(numpy.fromstring(im.tostring(), numpy.ubyte), (im.size[1], im.size[0]))

def _rgba2img(rgba):
    """ Convert four Numeric array objects to PIL Image.
    """
    assert type(rgba) is list
    return Image.merge('RGBA', [_arr2img(numpy.round(band * 255.0).astype(numpy.ubyte)) for band in rgba])

def _img2rgba(im):
    """ Convert PIL Image to four Numeric array objects.
    """
    assert im.mode == 'RGBA'
    return [_img2arr(band).astype(numpy.float32) / 255.0 for band in im.split()]

if __name__ == '__main__':

    import unittest
    
    def _str2img(str):
        """
        """
        return Image.fromstring('RGBA', (3, 3), str)
    
    class Tests(unittest.TestCase):
    
        def setUp(self):
            """
            """
            # Sort of a sw/ne diagonal street, with a top-left corner halo:
            # 
            # +------+   +------+   +------+   +------+   +------+
            # |\\\\\\|   |++++--|   |  ////|   |    ''|   |\\//''|
            # |\\\\\\| + |++++--| + |//////| + |  ''  | > |//''\\|
            # |\\\\\\|   |------|   |////  |   |''    |   |''\\\\|
            # +------+   +------+   +------+   +------+   +------+
            # base       halos      outlines   streets    output
            #
            # Just trust the tests.
            #
            _fff, _ccc, _999, _000, _nil = '\xFF\xFF\xFF\xFF', '\xCC\xCC\xCC\xFF', '\x99\x99\x99\xFF', '\x00\x00\x00\xFF', '\x00\x00\x00\x00'
            
            self.base = Layer(_str2img(_ccc * 9))
            self.halos = Layer(_str2img(_fff + _fff + _000 + _fff + _fff + (_000 * 4)))
            self.outlines = Layer(_str2img(_nil + (_999 * 7) + _nil))
            self.streets = Layer(_str2img(_nil + _nil + _fff + _nil + _fff + _nil + _fff + _nil + _nil))
        
        def test0(self):
        
            out = self.base
            out = out.add(self.outlines)
            out = out.add(self.streets)
            
            img = out.image()
    
            assert img.getpixel((0, 0)) == (0xCC, 0xCC, 0xCC, 0xFF), 'top left pixel'
            assert img.getpixel((1, 0)) == (0x99, 0x99, 0x99, 0xFF), 'top center pixel'
            assert img.getpixel((2, 0)) == (0xFF, 0xFF, 0xFF, 0xFF), 'top right pixel'
            assert img.getpixel((0, 1)) == (0x99, 0x99, 0x99, 0xFF), 'center left pixel'
            assert img.getpixel((1, 1)) == (0xFF, 0xFF, 0xFF, 0xFF), 'middle pixel'
            assert img.getpixel((2, 1)) == (0x99, 0x99, 0x99, 0xFF), 'center right pixel'
            assert img.getpixel((0, 2)) == (0xFF, 0xFF, 0xFF, 0xFF), 'bottom left pixel'
            assert img.getpixel((1, 2)) == (0x99, 0x99, 0x99, 0xFF), 'bottom center pixel'
            assert img.getpixel((2, 2)) == (0xCC, 0xCC, 0xCC, 0xFF), 'bottom right pixel'
        
        def test1(self):
    
            out = self.base
            out = out.add(self.outlines, self.halos)
            out = out.add(self.streets)
            
            img = out.image()
    
            assert img.getpixel((0, 0)) == (0xCC, 0xCC, 0xCC, 0xFF), 'top left pixel'
            assert img.getpixel((1, 0)) == (0x99, 0x99, 0x99, 0xFF), 'top center pixel' + repr(img.getpixel((1, 0)))
            assert img.getpixel((2, 0)) == (0xFF, 0xFF, 0xFF, 0xFF), 'top right pixel'
            assert img.getpixel((0, 1)) == (0x99, 0x99, 0x99, 0xFF), 'center left pixel'
            assert img.getpixel((1, 1)) == (0xFF, 0xFF, 0xFF, 0xFF), 'middle pixel'
            assert img.getpixel((2, 1)) == (0xCC, 0xCC, 0xCC, 0xFF), 'center right pixel'
            assert img.getpixel((0, 2)) == (0xFF, 0xFF, 0xFF, 0xFF), 'bottom left pixel'
            assert img.getpixel((1, 2)) == (0xCC, 0xCC, 0xCC, 0xFF), 'bottom center pixel'
            assert img.getpixel((2, 2)) == (0xCC, 0xCC, 0xCC, 0xFF), 'bottom right pixel'
        
        def test2(self):
        
            out = Color(0xcc, 0xcc, 0xcc)
            out = out.add(self.outlines, self.halos)
            out = out.add(self.streets)
            
            img = out.image()
            
            assert img.getpixel((0, 0)) == (0xCC, 0xCC, 0xCC, 0xFF), 'top left pixel'
            assert img.getpixel((1, 0)) == (0x99, 0x99, 0x99, 0xFF), 'top center pixel'
            assert img.getpixel((2, 0)) == (0xFF, 0xFF, 0xFF, 0xFF), 'top right pixel'
            assert img.getpixel((0, 1)) == (0x99, 0x99, 0x99, 0xFF), 'center left pixel'
            assert img.getpixel((1, 1)) == (0xFF, 0xFF, 0xFF, 0xFF), 'middle pixel'
            assert img.getpixel((2, 1)) == (0xCC, 0xCC, 0xCC, 0xFF), 'center right pixel'
            assert img.getpixel((0, 2)) == (0xFF, 0xFF, 0xFF, 0xFF), 'bottom left pixel'
            assert img.getpixel((1, 2)) == (0xCC, 0xCC, 0xCC, 0xFF), 'bottom center pixel'
            assert img.getpixel((2, 2)) == (0xCC, 0xCC, 0xCC, 0xFF), 'bottom right pixel'
        
        def test3(self):
            
            out = Color(0xcc, 0xcc, 0xcc)
            out = out.add(Color(0x99, 0x99, 0x99), self.halos)
            out = out.add(self.streets)
            
            img = out.image()
            
            assert img.getpixel((0, 0)) == (0x99, 0x99, 0x99, 0xFF), 'top left pixel'
            assert img.getpixel((1, 0)) == (0x99, 0x99, 0x99, 0xFF), 'top center pixel'
            assert img.getpixel((2, 0)) == (0xFF, 0xFF, 0xFF, 0xFF), 'top right pixel'
            assert img.getpixel((0, 1)) == (0x99, 0x99, 0x99, 0xFF), 'center left pixel'
            assert img.getpixel((1, 1)) == (0xFF, 0xFF, 0xFF, 0xFF), 'middle pixel'
            assert img.getpixel((2, 1)) == (0xCC, 0xCC, 0xCC, 0xFF), 'center right pixel'
            assert img.getpixel((0, 2)) == (0xFF, 0xFF, 0xFF, 0xFF), 'bottom left pixel'
            assert img.getpixel((1, 2)) == (0xCC, 0xCC, 0xCC, 0xFF), 'bottom center pixel'
            assert img.getpixel((2, 2)) == (0xCC, 0xCC, 0xCC, 0xFF), 'bottom right pixel'
    
    unittest.main()
