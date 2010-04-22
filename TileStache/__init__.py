""" A stylish alternative for caching your tiles.


"""

import re

from sys import stdout
from cgi import parse_qs
from StringIO import StringIO
from os.path import dirname, join as pathjoin, realpath

try:
    from json import load as json_load
except ImportError:
    from simplejson import load as json_load

from ModestMaps.Core import Coordinate

import Config

# regular expression for PATH_INFO
_pathinfo_pat = re.compile(r'^/?(?P<l>\w.+)/(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)\.(?P<e>\w+)$')

class KnownUnknown(Exception):
    """ There are known unknowns. That is to say, there are things that we now know we don't know.
    
        This exception gets thrown in a couple places where common mistakes are made.
    """
    pass

def handleRequest(layer, coord, extension):
    """ Get a type string and tile binary for a given request layer tile.
    
        Arguments:
        - layer: instance of Core.Layer to render.
        - coord: one ModestMaps.Core.Coordinate corresponding to a single tile.
        - extension: filename extension to choose response type, e.g. "png" or "jpg".
    
        This is the main entry point, after site configuration has been loaded
        and individual tiles need to be rendered.
    """
    mimetype, format = Config.getTypeByExtension(extension)
    cache = layer.config.cache
    
    # Start by checking for a tile in the cache.
    body = cache.read(layer, coord, format)
    
    # If no tile was found, dig deeper
    if body is None:
        try:
            # this is the coordinate that actually gets locked.
            lockCoord = layer.metatile.firstCoord(coord)
            
            # We may need to write a new tile, so acquire a lock.
            cache.lock(layer, lockCoord, format)
            
            # There's a chance that some other process has
            # written the tile while the lock was being acquired.
            body = cache.read(layer, coord, format)
    
            # If no one else wrote the tile, do it here.
            if body is None:
                buff = StringIO()
                tile = layer.render(coord, format)
                tile.save(buff, format)
                body = buff.getvalue()
                
                cache.save(body, layer, coord, format)

        finally:
            # Always clean up a lock when it's no longer being used.
            cache.unlock(layer, lockCoord, format)
    
    return mimetype, body

def parseConfigfile(configpath):
    """ Parse a configuration file and return a Configuration object.
    
        Configuration file is formatted as JSON with two sections, "cache" and "layers":
        
          {
            "cache": { ... },
            "layers": {
              "layer-1": { ... },
              "layer-2": { ... },
              ...
            }
          }
        
        The full filesystem path to the file is significant, used
        to resolve any relative paths found in the configuration.
        
        See the Caches module for more information on the "caches" section,
        and the Core and Providers modules for more information on the
        "layers" section.
    """
    config_dict = json_load(open(configpath, 'r'))
    dirpath = dirname(configpath)

    return Config.buildConfiguration(config_dict, dirpath)

def _splitPathInfo(pathinfo):
    """ Converts a PATH_INFO string to layer name, coordinate, and extension parts.
        
        Example: "/layer/0/0/0.png", leading "/" optional.
    """
    try:
        path = _pathinfo_pat.match(pathinfo)
        layer, row, column, zoom, extension = [path.group(p) for p in 'lyxze']
        coord = Coordinate(int(row), int(column), int(zoom))

    except AttributeError:
        raise KnownUnknown('Bad path: "%s". I was expecting something more like "/example/0/0/0.png"' % pathinfo)

    else:
        return layer, coord, extension

def cgiHandler(environ, config='./tilestache.cfg', debug=False):
    """ Read environment PATH_INFO, load up configuration, talk to stdout by CGI.
    """
    if debug:
        import cgitb
        cgitb.enable()
    
    try:
        if not environ.has_key('PATH_INFO'):
            raise KnownUnknown('Missing PATH_INFO in TileStache.cgiHandler().')
    
        config = parseConfigfile(config)
        layername, coord, extension = _splitPathInfo(environ['PATH_INFO'])
        
        if layername not in config.layers:
            raise KnownUnknown('"%s" is not a layer I know about. Here are some that I do know about: %s.' % (layername, ', '.join(config.layers.keys())))
        
        query = parse_qs(environ['QUERY_STRING'])
        layer = config.layers[layername]
        
        mimetype, content = handleRequest(layer, coord, extension)

    except KnownUnknown, e:
        out = StringIO()
        
        print >> out, 'Known unknown!'
        print >> out, e
        print >> out, ''
        print >> out, '\n'.join(_rummy())
        
        mimetype, content = 'text/plain', out.getvalue()

    print >> stdout, 'Content-Length: %d' % len(content)
    print >> stdout, 'Content-Type: %s\n' % mimetype
    print >> stdout, content

def modpythonHandler(request):
    """ Handle a mod_python request.
    
        Example Apache configuration for TileStache:

        <Directory /home/migurski/public_html/TileStache>
            AddHandler mod_python .py
            PythonHandler TileStache::modpythonHandler
            PythonOption config /etc/tilestache.cfg
        </Directory>
        
        Configuration options, using PythonOption directive:
        - config: path to configuration file, defaults to "tilestache.cfg",
            using request.filename as the current working directory.
    """
    from mod_python import apache
    
    try:
        config = request.get_options().get('config', 'tilestache.cfg')
        config = realpath(pathjoin(dirname(request.filename), config))
        config = parseConfigfile(config)
    
        layername, coord, extension = _splitPathInfo(request.path_info)
        
        if layername not in config.layers:
            raise KnownUnknown('"%s" is not a layer I know about. Here are some that I do know about: %s.' % (layername, ', '.join(config.layers.keys())))
        
        query = request.args
        layer = config.layers[layername]
        
        mimetype, content = handleRequest(layer, coord, extension)

    except KnownUnknown, e:
        out = StringIO()
        
        print >> out, 'Known unknown!'
        print >> out, e
        print >> out, ''
        print >> out, '\n'.join(_rummy())
        
        mimetype, content = 'text/plain', out.getvalue()

    request.status = apache.HTTP_OK
    request.content_type = mimetype
    request.set_content_length(len(content))
    request.send_http_header()

    request.write(content)

    return apache.OK

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
