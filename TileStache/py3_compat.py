# python3 compatibity while retaining checking
# for both str and unicode in python2
try:
    unicode = unicode
except NameError:
    unicode = str

try:
    # python3
    from functools import reduce
except NameError:
    pass
reduce = reduce

try:
    from urllib.parse import urlparse, urljoin, parse_qsl
    from urllib.request import urlopen
    import urllib.request as urllib2
    from cgi import parse_qs
    import http.client as httplib
except ImportError:
    # Python 2
    from urlparse import urlparse, urljoin, parse_qs, parse_qsl
    from urllib import urlopen
    import httplib
    import urllib2
