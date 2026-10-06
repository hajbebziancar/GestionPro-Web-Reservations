"""Persistent authentication attempt limits shared across server workers."""
import sqlite3,time,hashlib
from pathlib import Path
class AttemptLimiter:
    def __init__(self,path):self.path=Path(path)
    def attempt(self,key,limit=10,window=900):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        key=hashlib.sha256(key.encode()).hexdigest();now=time.time()
        with sqlite3.connect(self.path,timeout=10) as c:
            c.execute('CREATE TABLE IF NOT EXISTS attempts(key TEXT PRIMARY KEY,start REAL,count INTEGER)')
            c.execute('BEGIN IMMEDIATE')
            c.execute('DELETE FROM attempts WHERE start<?',(now-window,))
            row=c.execute('SELECT count FROM attempts WHERE key=?',(key,)).fetchone()
            if row and row[0]>=limit:return False
            c.execute('INSERT INTO attempts VALUES(?,?,1) ON CONFLICT(key) DO UPDATE SET count=count+1',(key,now))
        return True
    def blocked(self,key,limit=10,window=900):
        key=hashlib.sha256(key.encode()).hexdigest()
        if not self.path.exists():return False
        with sqlite3.connect(self.path,timeout=10) as c:
            row=c.execute('SELECT start,count FROM attempts WHERE key=?',(key,)).fetchone()
        return bool(row and row[0]>time.time()-window and row[1]>=limit)
