"""
"""

from sqlite3 import connect, OperationalError, IntegrityError

class Cache:

    def __init__(self):
        self.dbpath = '/tmp/stache.db'

        db = connect(self.dbpath).cursor()

        try:
            db.execute("""
                CREATE TABLE locks (
                    row     INTEGER,
                    column  INTEGER,
                    zoom    INTEGER,
                    format  TEXT,
                    
                    PRIMARY KEY (row, column, zoom, format)
                )
                """)
        except OperationalError:
            pass

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
