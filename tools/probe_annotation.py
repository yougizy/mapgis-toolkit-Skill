# -*- coding: utf-8 -*-
"""dump 注记类 mpa41 与三维类 mpf27 的结构与样本。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

MAPGIS_HOME = __import__("os").environ.get(
    "MAPGIS_HOME", r"D:\Program Files\MapGIS 10")
SAMPLE = MAPGIS_HOME + r"\Sample\sample.hdb"
DEMO = MAPGIS_HOME + r"\Sample\示例数据.hdb"


def hexdump(blob, n=96):
    return bytes(blob)[:n].hex()


def dump(path: str, tables) -> None:
    con = sqlite3.connect(Path(path).as_uri() + "?mode=ro&immutable=1", uri=True)
    cur = con.cursor()
    print("#" * 70)
    print(path)
    for table in tables:
        print("=" * 70)
        print("表", table)
        sql = cur.execute("select sql from sqlite_master where name=?", (table,)).fetchone()
        if not sql:
            print("  不存在")
            continue
        print("  schema:", sql[0])
        cols = [r[1] for r in cur.execute("PRAGMA table_info(%s)" % table)]
        print("  列:", cols)
        rows = cur.execute("select * from %s limit 3" % table).fetchall()
        for row in rows:
            info = {}
            for name, val in zip(cols, row):
                if isinstance(val, (bytes, bytearray)):
                    info[name] = "BLOB(%d) %s" % (len(val), hexdump(val))
                else:
                    info[name] = val
            print("  行:", info)
        try:
            print("  mptype 分布:",
                  cur.execute("select mptype, count(*) from %s group by mptype" % table).fetchall())
        except Exception as exc:
            print("  mptype 查询失败:", exc)
    con.close()


def main() -> None:
    dump(SAMPLE, ("mpa41",))
    dump(DEMO, ("mpf27",))
    con = sqlite3.connect(Path(DEMO).as_uri() + "?mode=ro&immutable=1", uri=True)
    cur = con.cursor()
    print("=" * 70)
    print("示例数据 mpf27 元数据")
    for cid in (27,):
        print("  item:", cur.execute("select * from mpdb_item where id=?", (cid,)).fetchone())
        print("  sfcls:", cur.execute("select * from mpdb_sfcls where id=?", (cid,)).fetchone())
        print("  fldinf:", cur.execute("select * from mpdb_fldinf where clsid=?", (cid,)).fetchall())
    con.close()


if __name__ == "__main__":
    main()
