""" The core class bits of TileStache.

Two important classes can be found here.

Layer represents a set of tiles in TileStache. It keeps references to
providers, projections, a Configuration instance, and other details required
for to the storage and rendering of a tile set. Layers are represented in the
configuration file as a dictionary:

    {
      "cache": ...,
      "layers": 
      {
        "example-name":
        {
            "provider": { ... },
            "metatile": { ... },
            "stale lock timeout": ...,
            "projection": ...
        }
      }
    }

- "provider" refers to a Provider, explained in detail in TileStache.Providers.
- "metatile" optionally makes it possible for multiple individual tiles to be
  rendered at one time, for greater speed and efficiency. This is commonly used
  for the Mapnik provider. See below for more information on metatiles.
- "projection" names a geographic projection, explained in TileStache.Geography.
  If omitted, defaults to spherical mercator.
- "stale lock timeout" is an optional number of seconds to wait before forcing
  a lock that might be stuck. This is defined on a per-layer basis, rather than
  for an entire cache at one time, because you may have different expectations
  for the rendering speeds of different layer configurations. Defaults to 15.

The public-facing URL of a single tile for this layer might look like this:

    http://example.com/tilestache.cgi/example-name/0/0/0.png

Metatile represents a larger area to be rendered at one time. Metatiles are
represented in the configuration file as a dictionary:

    {
        "rows": 4,
        "columns": 4,
        "buffer": 64
    }

- "rows" and "columns" are the height and width of the metatile measured in
  tiles. This example metatile is four rows tall and four columns wide, so it
  will render sixteen tiles simultaneously.
- "buffer" is a buffer area around the metatile, measured in pixels. This is
  useful for providers with labels or icons, where it's necessary to draw a
  bit extra around the edges to ensure that text is not cut off. This example
  metatile has a buffer of 64 pixels, so the resulting metatile will be 1152
  pixels square: 4 rows x 256 pixels + 2 x 64 pixel buffer.
"""

from StringIO import StringIO

from ModestMaps.Core import Coordinate

class Metatile:
    """ Some basic characteristics of a metatile.
    
        Properties:
        - rows: number of tile rows this metatile covers vertically.
        - columns: number of tile columns this metatile covers horizontally.
        - buffer: pixel width of outer edge.
    """
    def __init__(self, buffer=0, rows=1, columns=1):
        assert rows >= 1
        assert columns >= 1
        assert buffer >= 0

        self.rows = rows
        self.columns = columns
        self.buffer = buffer

    def isForReal(self):
        """ Return True if this is really a metatile with a buffer or multiple tiles.
        
            A default 1x1 metatile with buffer=0 is not for real.
        """
        return self.buffer > 0 or self.rows > 1 or self.columns > 1

    def firstCoord(self, coord):
        """ Return a new coordinate for the upper-left corner of a metatile.
        
            This is useful as a predictable way to refer to an entire metatile
            by one of its sub-tiles, currently needed to do locking correctly.
        """
        return self.allCoords(coord)[0]

    def allCoords(self, coord):
        """ Return a list of coordinates for a complete metatile.
        
            Results are guaranteed to be ordered left-to-right, top-to-bottom.
        """
        rows, columns = int(self.rows), int(self.columns)
        
        # upper-left corner of coord's metatile
        row = rows * (int(coord.row) / rows)
        column = columns * (int(coord.column) / columns)
        
        coords = []
        
        for r in range(rows):
            for c in range(columns):
                coords.append(Coordinate(row + r, column + c, coord.zoom))

        return coords

class Layer:
    """ A Layer.
    
        Attributes:

          provider:
            Render provider, see Providers module.

          config:
            Configuration instance, see Config module.

          projection:
            Geographic projection, see Geography module.

          metatile:
            Some information for drawing many tiles at once.

          stale_lock_timeout:
            Number of seconds until a cache lock is forced.
    """
    def __init__(self, config, projection, metatile, stale_lock_timeout=15):
        self.provider = None
        self.config = config
        self.projection = projection
        self.metatile = metatile
        
        self.stale_lock_timeout = stale_lock_timeout

    def name(self):
        """ Figure out what I'm called, return a name if there is one.
        
            Layer names are stored in the Configuration object, so
            config.layers must be inspected to find a matching name.
        """
        for (name, layer) in self.config.layers.items():
            if layer is self:
                return name

        return None

    def doMetatile(self):
        """ Return True if we have a real metatile and the provider is OK with it.
        """
        return self.metatile.isForReal() and hasattr(self.provider, 'renderArea')
    
    def render(self, coord, format):
        """ Render a tile for a coordinate, return PIL Image-like object.
        
            Perform metatile slicing here as well, if required, writing the
            full set of rendered tiles to cache as we go.
        """
        srs = self.projection.srs
        xmin, ymin, xmax, ymax = self.envelope(coord)
        width, height = 256, 256
        
        provider = self.provider
        metatile = self.metatile
        
        if self.doMetatile():
            # adjust render size and coverage for metatile
            xmin, ymin, xmax, ymax = self.metaEnvelope(coord)
            width, height = self.metaSize(coord)

            subtiles = self.metaSubtiles(coord)
        
        if self.doMetatile() or hasattr(provider, 'renderArea'):
            # draw an area, defined in projected coordinates
            tile = provider.renderArea(width, height, srs, xmin, ymin, xmax, ymax, coord.zoom)
        
        elif hasattr(provider, 'renderTile'):
            # draw a single tile
            width, height = 256, 256
            tile = provider.renderTile(width, height, srs, coord)

        else:
            raise KnownUnknown('Your provider lacks renderTile and renderArea methods.')

        if not hasattr(tile, 'save'):
            raise KnownUnknown('Return value of provider.renderArea() must act like an image; e.g. have a "save" method.')

        if hasattr(tile, 'size') and tile.size != (width, height):
            raise KnownUnknown('Your provider returned the wrong image size: %s.' % repr(tile.size))
        
        if self.doMetatile():
            # tile will be set again later
            tile, surtile = None, tile
            
            for (other, x, y) in subtiles:
                buff = StringIO()
                bbox = (x, y, x + 256, y + 256)
                subtile = surtile.crop(bbox)
                subtile.save(buff, format)
                body = buff.getvalue()
                
                self.config.cache.save(body, self, other, format)
                
                if other == coord:
                    # the one that actually gets returned
                    tile = subtile
        
        return tile

    def envelope(self, coord):
        """ Projected rendering envelope (xmin, ymin, xmax, ymax) for a Coordinate.
        """
        ul = self.projection.coordinateProj(coord)
        lr = self.projection.coordinateProj(coord.down().right())
        
        return min(ul.x, lr.x), min(ul.y, lr.y), max(ul.x, lr.x), max(ul.y, lr.y)
    
    def metaEnvelope(self, coord):
        """ Projected rendering envelope (xmin, ymin, xmax, ymax) for a metatile.
        """
        # size of buffer expressed as fraction of tile size
        buffer = float(self.metatile.buffer) / 256
        
        # full set of metatile coordinates
        coords = self.metatile.allCoords(coord)
        
        # upper-left and lower-right expressed as fractional coordinates
        ul = coords[0].left(buffer).up(buffer)
        lr = coords[-1].right(1 + buffer).down(1 + buffer)

        # upper-left and lower-right expressed as projected coordinates
        ul = self.projection.coordinateProj(ul)
        lr = self.projection.coordinateProj(lr)
        
        # new render area coverage in projected coordinates
        return min(ul.x, lr.x), min(ul.y, lr.y), max(ul.x, lr.x), max(ul.y, lr.y)
    
    def metaSize(self, coord):
        """ Pixel width and height of full rendered image for a metatile.
        """
        # size of buffer expressed as fraction of tile size
        buffer = float(self.metatile.buffer) / 256
        
        # new master image render size
        width = int(256 * (buffer * 2 + self.metatile.columns))
        height = int(256 * (buffer * 2 + self.metatile.rows))
        
        return width, height

    def metaSubtiles(self, coord):
        """ List of all coords in a metatile and their x, y offsets in a parent image.
        """
        subtiles = []

        coords = self.metatile.allCoords(coord)

        for other in coords:
            r = other.row - coords[0].row
            c = other.column - coords[0].column
            
            x = c * 256 + self.metatile.buffer
            y = r * 256 + self.metatile.buffer
            
            subtiles.append((other, x, y))

        return subtiles

    def getTypeByExtension(self, extension):
        """ Get mime-type and PIL format by file extension.
        """
        if hasattr(self.provider, 'getTypeByExtension'):
            return self.provider.getTypeByExtension(extension)
        
        elif extension.lower() == 'png':
            return 'image/png', 'PNG'
    
        elif extension.lower() == 'jpg':
            return 'image/jpeg', 'JPEG'
    
        else:
            raise KnownUnknown('Unknown extension in configuration: "%s"' % extension)

class KnownUnknown(Exception):
    """ There are known unknowns. That is to say, there are things that we now know we don't know.
    
        This exception gets thrown in a couple places where common mistakes are made.
    """
    pass

def _preview(layer):
    """ Get an HTML response for a given named layer.
    """
    layername = layer.name()
    
    return """<!DOCTYPE html>
<html>
<head>
	<title>TileStache Preview: %(layername)s</title>
    <script src="http://code.modestmaps.com/0.13.2/modestmaps.min.js" type="text/javascript"></script>
</head>
<body>
    <script type="text/javascript">
    <!--
    
        var template = '{Z}/{X}/{Y}.png';
        var provider = new com.modestmaps.TemplatedMapProvider(template);
        var map = new com.modestmaps.Map(document.body, provider);
        map.setCenterZoom(new com.modestmaps.Location(37.80, -122.26), 10);
        map.draw();
    
    //-->
    </script>
</body>
</html>
""" % locals()

def _rummy():
    """ Draw Him.
    """
    return ['------------------------------------------------------------------------------------------------------------',
            'MB###BHHHBBMBBBB#####MBBHHHHBBBBHHAAA&GG&AAAHB###MHAAAAAAAAAHHAGh&&&AAAAH#@As;;shM@@@@@@@@@@@@@@@@@@@@@@@@@@',
            'MGBMHAGG&&AAA&&AAM##MHAGG&GG&&GGGG93X5SS2XX9hh3255X2issii5X3h9X22555XXXX9H@A.   rA@@@@@@@@@@@@@@@@@@@@@@@@@@',
            'BAM#BAAAAAAHHAAAHM##MBHAAAAAAAAAAAAG9X2X3hGXiii5X9hG3X9Xisi29B##BA33hGGhGB@@r   ;9@@@@@@@@@@@@@@@@@@@@@@@@@@',
            'BAM#MHAAAHHHAAAAHM###BHAAAAAAAAAAAAGhXX3h2iSX&A&&AAHAGGAGs;rrri2r;rSiXGA&B@@9.  ,2#@@@@@@@@@@@@@@@@@@@@@@@@@',
            'B&B#MHAAAAHHHAAAHM##MBHAAAAAAAAAAHAG93XSrs5Xh93h3XXX93529Xr;:,,:;;s25223AB@@@;   sB@@@@@@@@@@@@@@@@@@@@@@@@@',
            'B&B#BAAAAAHHHAAAHB##MBAAAAAAAAAAAHHAh5rs2AGGAhXisiissSsr;r;::,:riiiisrr,s#@@@9.  ,2#@@@@@@@@@@@@@@@@@@@@@@@@',
            'B&B#BAAAAAAHAAAAHM###BHA&AAAAAA&AAHA2S&#@MBHGX22s;;;;r;;:,:,,:;;rrr:,,:,.X@@@@r   :9@@@@@@@@@@@@@@@@@@@@@@@@',
            'BAM#MAAAAAAAAAAAAB##MBAA&AAAAAAA&AH929AHA9XhXirrir::;r;;:::,:,,:,;rsr;,.,;2@@@#,   :G@@@@@@@@@@@@@@@@@@@@@@B',
            'B&B#MAAAAAAHAAAAABM#MHAA&&&&&&&&&H&ss3AXisisisr;;r;::;::::,..,,,,::;rir;,;,A@@@G.   ;9@@@@@@@@@@@@@@@@@@@@@#',
            'B&B#MHAAAAHHAAAAABM#MHAAA&G&A&&&AG2rr2X; .:;;;;::::::::::,,,,,:,.,;::;;,;rr:@@@@X    :2#@@@@@@@@@@@@@@@@@@@@',
            'B&B##HAAAAHHAAAAABMMMHAA&&&&&AAA&h2:r2r..:,,,,,,,,,,,,:;:,,,,,,. ,;;;::, ;2rr@@@@2    :SB@@@@@@@@@@@@@@@@@@@',
            'BGB##HAAAAAAAAAAABMMMBAA&&&&&&&&AHr ir:;;;;:,,,,,,::::,,:,:,,,,...;:;:,:,:2Xr&@@@@3.   .rG@@@@@@@@@@@@@@@@@@',
            'B&B@#B&&AAAAAA&&AHMMMBAA&&&&&&&&AH,.i;;rrr;::,,:::::::,,::::::,,..;,:;.;;iXGSs#@@@@A,    :5#@@@@@@@@@@@@@@@@',
            'B&M@@B&&AAAHAA&&AHMMMBAA&&&&&&&&AA;,;rrrrr;;::::::::::::::::::::.:;.::,:5A9r,.9@@@@@M;    .;G@@@@@@@@@@@@@@@',
            'B&M@@B&&AAHAAA&&AHMMMBAA&G&GG&&&AM3;rrr;rr;;;;;;:::::;;,:,::,,,..,:;;:,;2r:.:;r@@##@@@i     .sH@@@@@@@@@@@@@',
            'BGM@@B&&AAAHAA&&AHMMMBHAGGGG&&&&AMHs;srrr;r:;;;;::::::,..,,,,,,...,;rrrsi, . :,#@####@@A;     ,iB@@@@@@@@@@@',
            'B&#@@B&&AAAAAA&&AHMMMBAA&GGGGG&&&BHr,rirr;;;::::::::::,,,,,::,,::,.,SS;r:.;r .,A#HHMBB#@@2,     :iA@@@@@@@@@',
            'B&#@@B&&AAAAAA&&AHBMBBAAGGGGGGG&&H#2:sis;;;::,,:::r;rsrr23HMAXr:::,:;...,,,5s,,#BGGAAAAB@@#i.     ,rG@@@@@@@',
            'B&#@@BG&AAAAAA&&AHHBMHAAGGhhGGGGGA#Hrs9s;;;;r;:;s5Xrrh@@@@@@@@&5rr;. .,,;. ;;.;@Bh39hhhAM#@@Ar.     ,rG#@@@@',
            'BA#@@BG&AAAAAA&&AHBMMBA&GGGGGGGGGAM#3r5SsiSSX@@@#@@i. 2h5ir;;:;r;:...,,:,.,;,,3@HG99XX23&H#MMBAS,     .;2H@@',
            'BA#@@B&&AAAAAA&&&AHBMBAA&GGGGGGGhABMhsrirrS9#@Mh5iG&::r;..:;:,,.,...,::,,,...,A@A&h9X255XGAA93B#MX;      .:X',
            'BH@@@B&&AAAAAA&G&ABM#BHAGGGGGGGGG&HBAXiir;s2r;;:rrsi.,,.   .....,,,,::,.,,:: :2@H&Gh9X2523AG253AM@@Ai,     ,',
            'MB@@@B&&AAAAAAGGAA###@#H&GGGGGGG&AHBAXXi;,. .:,,, .;:,.,;:;..,::::;;;:,,,:,srs5@B&hhh32229AG2S29GAB#@#A2;  .',
            'MB@@@BGGAAAAA&&GAHr  ,sH#AGGhhGGG&AH&X22s:..,. .  ;S:,. .,i9r;::,,:;:::,:::,,5A#BAhhhX22X9AG2i2X9hG&AB#@@B3r',
            'MB@@@B&&AAAAAA&AM#;..   ;AAGhhGGG&AHGX2XXis::,,,,,Xi,.:.ri;Xir;:,...,:::;::,.:S9#AGh9X2229A&2i52X39hhG&AM@@&',
            'MM@@@B&GAAAHBHBhsiGhhGi. 3MGGhGGG&HH&X52GXshh2r;;rXiB25sX2r;;:ii;,...:;:;:;:.., r#G33X2223AG2i52XX3339hGAA&&',
            '#M@@@B&GAM#A3hr  .;S5;:, ;MAGhGGG&ABAX55X9rS93s::i::i52X;,::,,,;5r:,,,::;;;:,.i  @@AXX222X&G2S52XXXX3399hhh&',
            '#M@@@BAB&S;  .:, .,,;,;;. rBGhhGG&ABAXSS29G5issrrS,,,,,:,...,;i;rr:,:,,::;::,,r  #@@B25523&G2iS2XXX3X33999h&',
            '#M@@@MH;  ,. .;i::::;rr;, ,M&GGGh&AHAXSS2X3hXirss5;r;:;;;2#@@H9Ai;::,,,,:;:;::   ,@@@#Xi23&G2iS2XXX3X33339h&',
            '#M#@@#i  .:;,.,::,::;&ii;.;#AGhGG&AHAXSS2XX3&hir;;s9GG@@@@@h;,,riirr;:,.:;;;.    i@##@@AS2hh5iS222XXXX3999hG',
            '#M@@@@:.;,,:r,,;r,,..h#sr: rHAGhG&AHAXSi52X39AAir::is;::,,. .::,sssrr;,,;r:     ,@@MM#@@#HBA2iiSS5522XX39hhG',
            '#M@@@@r.sr,:rr::r;,, ,As:,  :B&hh&ABAXSiSS5229HHS3r;rSSsiiSSr;:,,,:;;r;;;       @@#BMM#@@@@@@@@#MH&93XXXXX3G',
            '#M@@@@A,:r:,:i,,rr,,. ;;;,. ;BGhhGAHAX5529hAAAM#AH#2i25Ss;;;:.....,rSi2r       M@@MMMM##@#@@@@@@@@@@@@@@#MHA',
            '#M@@@@M::rr::SS,;r;::.:;;r:rHAh9h&ABM##@@@@@@@@ABAAA25i;::;;;:,,,,:r32:       H@@#MM######@@@@@@@@@@@@@@@@@#',
            '#M@@@@@5:;sr;;9r:i;,.,sr;;iMHhGABM#####@@@@@@@BHH&H@#AXr;;r;rsr;;ssS;        H@@##########@@@##@@@@@@@@@@@@#',
            '#M@@@@##r;;s;:3&;rsSrrisr:h#AHM#######BM#@@@#HHH9hM@@@X&92XX9&&G2i,     .,:,@@@##M########@@@####@@@@@@@@@##',
            '#M#@@@M@2,:;s;;2s:rAX5SirS#BB##@@@##MAAHB#@#BBH93GA@@@2 2@@@MAAHA  .,,:,,. G@@#M#################@@@@@@#####',
            '#M#@@#M@;,;:,,,;h52iX33sX@@#@@@@@@@#Ah&&H####HhA@@@@@@@;s@@@@H5@@  .      r@@##M###########@###@@@@@@#######',
            '#M#@@@#r.:;;;;rrrrrri5iA@@#@@@@@@@@#HHAH##MBA&#@@@@@@@@3i@@@@@3:,        ,@@#M############@@###@@@@@########',
            '#M@@@@r r::::;;;;;;rirA@#@@@@@@@@@@@#MGAMMHBAB@@@@@@@@@#2@@@@#i ..       #@##M#####@###@@@@###@@@@##########',
            '#M#@@@  2;;;;;;rr;rish@@#@#@@@@@@@@@@B&hGM#MH#@@@@@@@@@@3;,h@.   ..     :@@MM#######@@@@#####@@@@###########',
            '#M@@#A  ;r;riirrrr;:2S@###@@@@@@@@@@@#AH#@#HB#@@@@@@@@@@@@2A9           @@#BMMM############@#@@@####M#######',
            '#M@MM#      ,:,:;;,5ir@B#@@@@@@@@@@@@@@@@@#MMH#@@@@@@@@@@@@r Ms        B@#MMMMMM####@###@@#@@@@#####M######@',
            '##Mh@M  .    ...:;;,:@A#@@@@@@@@@@@#@@@@@@#MMHAB@@@@#G#@@#: i@@       r@@#MMM#######@@@@#@@@@@@#####M#####@@',
            '#H3#@3. ,.    ...  :@@&@@@@@@@@@@@@@#@@#@@@MMBHGA@H&;:@@i :B@@@B     .@@#MM####@@@##@@@#@@@@@#######M##M#@@@',
            'M&AM5i;.,.   ..,,rA@@MH@@@@@@@@@@@@@##@@@@@MMMBB#@h9hH#s;3######,   .A@#MMM#####@@@@@##@@@#@@#####M#####M39B']
