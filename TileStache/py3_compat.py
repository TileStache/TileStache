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
    import urllib.request as urllib2
    import http.client as httplib
    from urllib.parse import urlparse, urljoin, parse_qsl
    from urllib.request import urlopen
    from cgi import parse_qs
    from _thread import allocate_lock
except ImportError:
    # Python 2
    import httplib
    import urllib2
    from urlparse import urlparse, urljoin, parse_qs, parse_qsl
    from urllib import urlopen
    from thread import allocate_lock
