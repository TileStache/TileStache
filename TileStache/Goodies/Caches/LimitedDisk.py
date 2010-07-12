"""
"""

import os
import sys

from math import ceil
from time import time, sleep
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

    def __init__(self):
        self.cachepath = '/tmp/limited'
        self.dbpath = pathjoin(self.cachepath, 'stache.db')
        self.umask = 0022

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

        due = time() + layer.stale_lock_timeout
        
        while True:
            if time() > due:
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
                sleep(.2)
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

    def read(self, layer, coord, format):
        """ Read a cached tile.
        
            If found, update the used column in the tiles table with current time.
        """
        sys.stderr.write('read %d/%d/%d, %s' % (coord.zoom, coord.column, coord.row, format))

        path = self._filepath(layer, coord, format)
        fullpath = pathjoin(self.cachepath, path)
        
        if exists(fullpath):
            body = open(fullpath, 'r').read()

            sys.stderr.write('...hit %s, set used=%d' % (path, time()))

            db = connect(self.dbpath).cursor()
            db.execute("""UPDATE tiles
                          SET used=?
                          WHERE path=?""",
                       (int(time()), path))
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
            blocks = ceil(size / float(stat.st_blksize))
            size = int(blocks * stat.st_blksize)

        return size
    
    def save(self, body, layer, coord, format):
        """
        """
        sys.stderr.write('save %d/%d/%d, %s' % (coord.zoom, coord.column, coord.row, format))
        
        path = self._filepath(layer, coord, format)
        size = self._write(body, path, format)

        db = connect(self.dbpath).cursor()
        
        db.execute("""INSERT INTO tiles
                      (path, size, used)
                      VALUES (?, ?, ?)""",
                   (path, size, int(time())))
        
        db.connection.commit()
        db.connection.close()
