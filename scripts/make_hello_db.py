import sqlite3
from pathlib import Path

d = Path("backend/data")
d.mkdir(parents=True, exist_ok=True)
con = sqlite3.connect(d / "hello.sqlite")
con.execute("DROP TABLE IF EXISTS t")
con.execute("CREATE TABLE t (x INTEGER)")
con.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(10)])
con.commit()
con.close()