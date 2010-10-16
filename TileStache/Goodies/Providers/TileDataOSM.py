from sys import stderr
from time import strftime, gmtime
from xml.dom.minidom import getDOMImplementation

from TileStache.Core import KnownUnknown

try:
    from psycopg2 import connect as _connect, ProgrammingError
except ImportError:
    # well it won't work but we can still make the documentation.
    pass

class Node:
    def __init__(self, id, version, timestamp, uid, user, changeset, lat, lon):
        self.id = id
        self.version = version
        self.timestamp = timestamp
        self.uid = uid
        self.user = user
        self.changeset = changeset
        self.lat = lat
        self.lon = lon
        
        self._tags = {}

    def tag(self, k, v):
        self._tags[k] = v

    def tags(self):
        return sorted(self._tags.items())

class Way:
    def __init__(self, id, version, timestamp, uid, user, changeset):
        self.id = id
        self.version = version
        self.timestamp = timestamp
        self.uid = uid
        self.user = user
        self.changeset = changeset
        
        self._nodes = []
        self._tags = {}

    def node(self, id):
        self._nodes.append(id)

    def nodes(self):
        return self._nodes[:]

    def tag(self, k, v):
        self._tags[k] = v

    def tags(self):
        return sorted(self._tags.items())

def coordinate_bbox(coord, projection):
    """
    """
    ul = projection.coordinateLocation(coord)
    ur = projection.coordinateLocation(coord.right())
    ll = projection.coordinateLocation(coord.down())
    lr = projection.coordinateLocation(coord.down().right())
    
    n = max(ul.lat, ur.lat, ll.lat, lr.lat)
    s = min(ul.lat, ur.lat, ll.lat, lr.lat)
    e = max(ul.lon, ur.lon, ll.lon, lr.lon)
    w = min(ul.lon, ur.lon, ll.lon, lr.lon)
    
    return n, s, e, w

class SaveableResponse:
    """ Wrapper class for XML response that makes it behave like a PIL.Image object.
    
        TileStache.getTile() expects to be able to save one of these to a buffer.
    """
    def __init__(self, nodes, ways):
        self.nodes = nodes
        self.ways = ways
        
    def save(self, out, format):
        if format != 'XML':
            raise KnownUnknown('TileDataOSM only saves .xml tiles, not "%s"' % format)

        imp = getDOMImplementation()
        doc = imp.createDocument(None, 'osm', None)
        
        osm_el = doc.documentElement
        osm_el.setAttribute('version', '0.6')
        osm_el.setAttribute('generator', 'TileDataOSM (TileStache.org)')
        
        for node in self.nodes:
            # <node id="53037501" version="6" timestamp="2010-09-06T23:16:03Z" uid="14293" user="dahveed76" changeset="5703401" lat="37.8024307" lon="-122.2634983"/>
        
            node_el = doc.createElement('node')
            
            node_el.setAttribute('id', '%d' % node.id)
            node_el.setAttribute('version', '%d' % node.version)
            node_el.setAttribute('timestamp', strftime('%Y-%m-%dT%H:%M:%SZ', gmtime(node.timestamp)))
            node_el.setAttribute('uid', '%d' % node.uid)
            node_el.setAttribute('user', node.user.encode('utf-8'))
            node_el.setAttribute('changeset', '%d' % node.changeset)
            node_el.setAttribute('lat', '%.7f' % node.lat)
            node_el.setAttribute('lon', '%.7f' % node.lon)
            
            for (key, value) in node.tags():
                tag_el = doc.createElement('tag')
                
                tag_el.setAttribute('k', key.encode('utf-8'))
                tag_el.setAttribute('v', value.encode('utf-8'))
                
                node_el.appendChild(tag_el)
            
            osm_el.appendChild(node_el)
        
        for way in self.ways:
            # <way id="6332386" version="2" timestamp="2010-03-27T09:42:04Z" uid="20587" user="balrog-kun" changeset="4244079">
        
            way_el = doc.createElement('way')
            
            way_el.setAttribute('id', '%d' % way.id)
            way_el.setAttribute('version', '%d' % way.version)
            way_el.setAttribute('timestamp', strftime('%Y-%m-%dT%H:%M:%SZ', gmtime(way.timestamp)))
            way_el.setAttribute('uid', '%d' % way.uid)
            way_el.setAttribute('user', way.user.encode('utf-8'))
            way_el.setAttribute('changeset', '%d' % way.changeset)
            
            for (node_id) in way.nodes():
                nd_el = doc.createElement('nd')
                nd_el.setAttribute('ref', '%d' % node_id)
                way_el.appendChild(nd_el)
            
            for (key, value) in way.tags():
                tag_el = doc.createElement('tag')
                tag_el.setAttribute('k', key.encode('utf-8'))
                tag_el.setAttribute('v', value.encode('utf-8'))
                way_el.appendChild(tag_el)
            
            osm_el.appendChild(way_el)
        
        out.write(doc.toxml('UTF-8'))

def prepare_database(db, coord, projection):
    """
    """
    db.execute('CREATE TEMPORARY TABLE box_node_list (id bigint PRIMARY KEY) ON COMMIT DROP')
    db.execute('CREATE TEMPORARY TABLE box_way_list (id bigint PRIMARY KEY) ON COMMIT DROP')
    db.execute('CREATE TEMPORARY TABLE box_relation_list (id bigint PRIMARY KEY) ON COMMIT DROP')
    
    n, s, e, w = coordinate_bbox(coord, projection)
    
    bbox = 'ST_SetSRID(ST_MakeBox2D(ST_MakePoint(%.7f, %.7f), ST_MakePoint(%.7f, %.7f)), 4326)' % (w, s, e, n)

    # Collect all node ids inside bounding box.

    db.execute("""INSERT INTO box_node_list
                  SELECT id
                  FROM nodes
                  WHERE (geom && %(bbox)s)""" \
                % locals())

    # Collect all way ids inside bounding box using already selected nodes.

    db.execute("""INSERT INTO box_way_list
                  SELECT wn.way_id
                  FROM way_nodes wn
                  INNER JOIN box_node_list n
                  ON wn.node_id = n.id
                  GROUP BY wn.way_id""")

    # Collect all relation ids containing selected nodes or ways.

    db.execute("""INSERT INTO box_relation_list
                  (
                    SELECT rm.relation_id AS relation_id
                    FROM relation_members rm
                    INNER JOIN box_node_list n
                    ON rm.member_id = n.id
                    WHERE rm.member_type = 'N'
                  UNION
                    SELECT rm.relation_id AS relation_id
                    FROM relation_members rm
                    INNER JOIN box_way_list w
                    ON rm.member_id = w.id
                    WHERE rm.member_type = 'W'
                  )""")

    # Collect parent relations of selected relations.

    db.execute("""INSERT INTO box_relation_list
                  SELECT rm.relation_id AS relation_id
                  FROM relation_members rm
                  INNER JOIN box_relation_list r
                  ON rm.member_id = r.id
                  WHERE rm.member_type = 'R'
                  EXCEPT
                  SELECT id AS relation_id
                  FROM box_relation_list""")

    db.execute('ANALYZE box_node_list')
    db.execute('ANALYZE box_way_list')
    db.execute('ANALYZE box_relation_list')

class Provider:
    """
    """
    
    def __init__(self, layer, database=None, username=None, password=None, hostname=None):
        """
        """
        self.layer = layer
        self.dbkwargs = {}
        
        if hostname:
            self.dbkwargs['host'] = hostname
        
        if username:
            self.dbkwargs['user'] = username
        
        if database:
            self.dbkwargs['database'] = database
        
        if password:
            self.dbkwargs['password'] = password

    def getTypeByExtension(self, extension):
        """ Get mime-type and format by file extension.
        
            This only accepts "xml".
        """
        if extension.lower() != 'xml':
            raise KnownUnknown('TileDataOSM only makes .xml tiles, not "%s"' % extension)
    
        return 'text/xml', 'XML'

    def renderTile(self, width, height, srs, coord):
        """ Render a single tile, return a SaveableResponse instance.
        """
        db = _connect(**self.dbkwargs).cursor()
        
        prepare_database(db, coord, self.layer.projection)
        
        counts = []
        
        # Select core node information

        db.execute("""SELECT n.id, n.version, EXTRACT(epoch FROM n.tstamp),
                             u.id, u.name, n.changeset_id,
                             ST_Y(n.geom), ST_X(n.geom)
                      FROM nodes n
                      LEFT OUTER JOIN users u
                        ON n.user_id = u.id
                      INNER JOIN box_node_list b
                        ON b.id = n.id
                      ORDER BY n.id""")

        nodes = [Node(*row) for row in db.fetchall()]
        nodes_dict = dict([(node.id, node) for node in nodes])
        
        # Select all node tags

        db.execute("""SELECT n.id, t.k, t.v
                      FROM node_tags t
                      INNER JOIN box_node_list n
                        ON n.id = t.node_id
                      ORDER BY n.id""")

        for (node_id, key, value) in db.fetchall():
            nodes_dict[node_id].tag(key, value)
        
        # Select core way information

        db.execute("""SELECT w.id, w.version, EXTRACT(epoch FROM w.tstamp),
                             u.id, u.name, w.changeset_id
                      FROM ways w
                      LEFT OUTER JOIN users u
                        ON w.user_id = u.id
                      INNER JOIN box_way_list b
                        ON b.id = w.id
                      ORDER BY w.id""")

        ways = [Way(*row) for row in db.fetchall()]
        ways_dict = dict([(way.id, way) for way in ways])

        # Select all way tags

        db.execute("""SELECT w.id, t.k, t.v
                      FROM way_tags t
                      INNER JOIN box_way_list w
                        ON w.id = t.way_id
                      ORDER BY w.id""")

        for (way_id, key, value) in db.fetchall():
            ways_dict[way_id].tag(key, value)

        # Select all way nodes in order

        db.execute("""SELECT w.id, n.node_id, n.sequence_id
                      FROM way_nodes n
                      INNER JOIN box_way_list w
                      ON n.way_id = w.id
                      ORDER BY w.id, n.sequence_id""")

        for (way_id, node_id, sequence_id) in db.fetchall():
            ways_dict[way_id].node(node_id)

        # Looks like: select core relation information

        db.execute("""SELECT e.id, e.version, e.user_id, u.name AS user_name, e.tstamp, e.changeset_id
                      FROM relations e
                      LEFT OUTER JOIN users u
                      ON e.user_id = u.id
                      INNER JOIN box_relation_list c
                      ON e.id = c.id
                      ORDER BY e.id""")

        counts.append(len(db.fetchall()))

        # Looks like: select all relation tags

        db.execute("""SELECT relation_id AS entity_id, k, v
                      FROM relation_tags f
                      INNER JOIN box_relation_list c
                      ON f.relation_id = c.id
                      ORDER BY entity_id""")

        counts.append(len(db.fetchall()))

        # Looks like: select all relation members in order

        db.execute("""SELECT relation_id AS entity_id, member_id, member_type, member_role, sequence_id
                      FROM relation_members f
                      INNER JOIN box_relation_list c
                      ON f.relation_id = c.id
                      ORDER BY entity_id, sequence_id""")

        counts.append(len(db.fetchall()))
        
        return SaveableResponse(nodes, ways)
        
        raise Exception(counts)
