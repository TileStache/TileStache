#!/usr/bin/env python
"""tilestache-flushurl.py will flush your cache for given URLs.

Eg.:

    tilestache-flushurl.py -c ./config.json http://a.tiles.fluv.io/openriverboatmap/9/260/172.png /openriverboatmap/9/260/173.png

See `tilestache-flushurl.py --help` for more information.
"""
import logging

from optparse import OptionParser
from urlparse import urlparse

from TileStache import parseConfigfile, splitPathInfo
from TileStache.Core import KnownUnknown

log = logging.getLogger(__name__)


class FlushCommand(object):

    def __init__(self, config, verbose=False):
        self.config = config
        self.verbose = verbose

    def split_url(self, url):
        """
        Return layer_name, coords, extension from an URL or a path.
        """
        parsed = urlparse(url)
        layer_name, coords, extension = splitPathInfo(parsed.path)
        return layer_name, coords, extension

    def flush(self, url):
        layer_name, coords, extension = self.split_url(url)
        layer = self.config.layers[layer_name]
        mimetype, format = layer.getTypeByExtension(extension)
        if self.verbose:
            print "Flushing url %s" % url
        self.config.cache.remove(layer, coords, format)

if __name__ == '__main__':

    parser = OptionParser(usage="""%prog [options] [url url...]\n""" + __doc__)

    parser.add_option(
        '-c',
        '--config',
        dest='config',
        help='Path to configuration file.'
    )

    parser.add_option(
        '-q',
        action='store_false',
        dest='verbose',
        default=True,
        help='Suppress chatty output'
    )
    options, urls = parser.parse_args()

    if not options.config:
        raise KnownUnknown('Missing required configuration (--config) parameter.')
    config = parseConfigfile(options.config)
    flusher = FlushCommand(config, options.verbose)

    for url in urls:
        flusher.flush(url)
