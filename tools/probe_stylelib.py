# -*- coding: utf-8 -*-
"""探查 styleLib.sty(SQLite)——系统样式库,可能含颜色表。"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

BASE = os.path.join(os.environ.get("MAPGIS_HOME", r"D:\Program Files\MapGIS 10"),
                    "Program", "Config", "DefaultSystemLib", "Slib")
PATH = os.path.join(BASE, "styleLib.sty")


def main() -> None:
    con = sqlite3.connect(Path(PATH).as_uri() + "?mode=ro&immutable=1", uri=True)
    cur = con.cursor()
    rows = cur.execute(
        "select type, name, sql from sqlite_master order by type, name").fetchall()
    print("对象数:", len(rows))
    for typ, name, sql in rows:
        print("=" * 60)
        print(typ, name)
        print((sql or "")[:600])
        if typ == "table":
            try:
                n = cur.execute('select count(*) from "%s"' % name).fetchone()[0]
                print("  rows:", n)
                for r in cur.execute('select * from "%s" limit 3' % name):
                    print("   ", [x[:40] if isinstance(x, (bytes, bytearray)) else x for x in r])
            except Exception as exc:
                print("  读取失败:", exc)
    con.close()


if __name__ == "__main__":
    main()
