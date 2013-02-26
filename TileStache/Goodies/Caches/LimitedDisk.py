""" Cache that stores a limited amount of data.

This is an example cache that uses a SQLite database to track sizes and last-read
times for cached tiles, and removes least-recently-used tiles whenever the total
size of the cache exceeds a set limit.

Example TileStache cache configuration, with a 16MB limit:

"cache":
{
    "class": "TileStache.Goodies.Caches.LimitedDisk.Cache",
    "kwargs": {
        "path": "/tmp/limited-cache",
        "limit": 16777216
    }
}
"""

import os
import sys
import time

from math import ceil as _ceil
from tempfile import mkstemp
from os.path import isdir, exists, dirname, basename, join as pathjoin
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
        path    TEXT PRIMARY KEY,
        used    INTEGER,
        size    INTEGER
    )
    """, """
    CREATE INDEX IF NOT EXISTS tiles_used ON tiles (used)
    """

class Cache:

    def __init__(self, path, limit, umask=0022):
        self.cachepath = path
        self.dbpath = pathjoin(self.cachepath, 'stache.db')
        self.umask = umask
        self.limit = limit

        db = connect(self.dbpath).cursor()
        
        for create_table in _create_tables:
            db.execute(create_table)

        db.connection.close()

    def _filepath(self, layer, coord, format):
        """
        """
        l = layer.name()
        z = '%d' % coord.zoom
        e = format.lower()
        
        x = '%06d' % coord.column
        y = '%06d' % coord.row

        x1, x2 = x[:3], x[3:]
        y1, y2 = y[:3], y[3:]
        
        filepath = os.sep.join( (l, z, x1, x2, y1, y2 + '.' + e) )

        return filepath

    def lock(self, layer, coord, format):
        """ Acquire a cache lock for this tile.
        
            Returns nothing, but (TODO) blocks until the lock has been acquired.
            Lock is implemented as a row in the "locks" table.
        """
        sys.stderr.write('lock %d/%d/%d, %s' % (coord.zoom, coord.column, coord.row, format))

        due = time.time() + layer.stale_lock_timeout
        
        while True:
            if time.time() > due:
                # someone left the door locked.
                sys.stderr.write('...force %d/%d/%d, %s' % (coord.zoom, coord.column, coord.row, format))
                self.unlock(layer, coord, format)
            
            # try to acquire a lock, repeating if necessary.
            db = connect(self.dbpath, isolation_level='EXCLUSIVE').cursor()

            try:
                db.execute("""INSERT INTO locks
                              (row, column, zoom, format)
                              VALUES (?, ?, ?, ?)""",
                           (coord.row, coord.column, coord.zoom, format))
            except IntegrityError:
                db.connection.close()
                time.sleep(.2)
                continue
            else:
                db.connection.commit()
                db.connection.close()
                break

    def unlock(self, layer, coord, format):
        """ Release a cache lock for this tile.

            Lock is implemented as a row in the "locks" table.
        """
        sys.stderr.write('unlock %d/%d/%d, %s' % (coord.zoom, coord.column, coord.row, format))

        db = connect(self.dbpath, isolation_level='EXCLUSIVE').cursor()
        db.execute("""DELETE FROM locks
                      WHERE row=? AND column=? AND zoom=? AND format=?""",
                   (coord.row, coord.column, coord.zoom, format))
        db.connection.commit()
        db.connection.close()
        
    def remove(self, layer, coord, format):
        """ Remove a cached tile.
        """
        # TODO: write me
        raise NotImplementedError('LimitedDisk Cache does not yet implement the .remove() method.')
        
    def read(self, layer, coord, format):
        """ Read a cached tile.
        
            If found, update the used column in the tiles table with current time.
        """
        sys.stderr.write('read %d/%d/%d, %s' % (coord.zoom, coord.column, coord.row, format))

        path = self._filepath(layer, coord, format)
        fullpath = pathjoin(self.cachepath, path)
        
        if exists(fullpath):
            body = open(fullpath, 'r').read()

            sys.stderr.write('...hit %s, set used=%d' % (path, time.time()))

            db = connect(self.dbpath).cursor()
            db.execute("""UPDATE tiles
                          SET used=?
                          WHERE path=?""",
                       (int(time.time()), path))
            db.connection.commit()
            db.connection.close()
        
        else:
            sys.stderr.write('...miss')
            body = None

        return body

    def _write(self, body, path, format):
        """ Actually write the file to the cache directory, return its size.
        
            If filesystem block size is known, try to return actual disk space used.
        """
        fullpath = pathjoin(self.cachepath, path)

        try:
            umask_old = os.umask(self.umask)
            os.makedirs(dirname(fullpath), 0777&~self.umask)
        except OSError, e:
            if e.errno != 17:
                raise
        finally:
            os.umask(umask_old)

        fh, tmp_path = mkstemp(dir=self.cachepath, suffix='.' + format.lower())
        os.write(fh, body)
        os.close(fh)
        
        try:
            os.rename(tmp_path, fullpath)
        except OSError:
            os.unlink(fullpath)
            os.rename(tmp_path, fullpath)

        os.chmod(fullpath, 0666&~self.umask)
        
        stat = os.stat(fullpath)
        size = stat.st_size
        
        if hasattr(stat, 'st_blksize'):
            blocks = _ceil(size / float(stat.st_blksize))
            size = int(blocks * stat.st_blksize)

        return size

    def _remove(self, path):
        """
        """
        fullpath = pathjoin(self.cachepath, path)

        os.unlink(fullpath)
    
    def save(self, body, layer, coord, format):
        """
        """
        sys.stderr.write('save %d/%d/%d, %s' % (coord.zoom, coord.column, coord.row, format))
        
        path = self._filepath(layer, coord, format)
        size = self._write(body, path, format)

        db = connect(self.dbpath).cursor()
        
        try:
            db.execute("""INSERT INTO tiles
                          (size, used, path)
                          VALUES (?, ?, ?)""",
                       (size, int(time.time()), path))
        except IntegrityError:
            db.execute("""UPDATE tiles
                          SET size=?, used=?
                          WHERE path=?""",
                       (size, int(time.time()), path))
        
        row = db.execute('SELECT SUM(size) FROM tiles').fetchone()
        
        if row and (row[0] > self.limit):
            over = row[0] - self.limit
            
            while over > 0:
                row = db.execute('SELECT path, size FROM tiles ORDER BY used ASC LIMIT 1').fetchone()
                
                if row is None:
                    break

                path, size = row
                db.execute('DELETE FROM tiles WHERE path=?', (path, ))
                self._remove(path)
                over -= size
                sys.stderr.write('delete ' + path)
        
        db.connection.commit()
        db.connection.close()
