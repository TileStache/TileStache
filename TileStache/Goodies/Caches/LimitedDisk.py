"""
"""

from sqlite3 import connect, OperationalError, IntegrityError

_create_tables = """
    CREATE TABLE IF NOT EXISTS locks (
        row     INTEGER,
        column  INTEGER,
        zoom    INTEGER,
        format  TEXT,
        
        PRIMARY KEY (row, column, zoom, format)
    )
    """, """
    CREATE TABLE IF NOT EXISTS tiles (
        row     INTEGER,
        column  INTEGER,
        zoom    INTEGER,
        format  TEXT,
        
        used    INTEGER,
        path    TEXT,
        
        PRIMARY KEY (row, column, zoom, format)
    )
    """, """
    CREATE INDEX IF NOT EXISTS tiles_used ON tiles (used)
    """

class Cache:

    def __init__(self):
        self.dbpath = '/tmp/stache.db'

        db = connect(self.dbpath).cursor()
        
        for create_table in _create_tables:
            db.execute(create_table)

        db.close()

    def lock(self, layer, coord, format):
        """ Acquire a cache lock for this tile.
        
            Returns nothing, but (TODO) blocks until the lock has been acquired.
            Lock is implemented as a row in the "locks" table.
        """
        db = connect(self.dbpath, isolation_level='EXCLUSIVE').cursor()
        
        try:
            db.execute("""INSERT INTO locks
                          (row, column, zoom, format) VALUES (?, ?, ?, ?)""",
                       (coord.row, coord.column, coord.zoom, format))
        except IntegrityError:
            # yikes, locked. deal with this later.
            pass
        else:
            db.connection.commit()

        db.close()

    def unlock(self, layer, coord, format):
        """ Release a cache lock for this tile.

            Lock is implemented as a row in the "locks" table.
        """
        db = connect(self.dbpath, isolation_level='EXCLUSIVE').cursor()
        db.execute("""DELETE FROM locks
                      WHERE row=? AND column=? AND zoom=? AND format=?""",
                   (coord.row, coord.column, coord.zoom, format))
        db.connection.commit()
        db.close()

    def read(self, layer, coord, format):
        pass

    def save(self, body, layer, coord, format):
        pass
