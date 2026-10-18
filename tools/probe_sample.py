# -*- coding: utf-8 -*-
"""探查 MapGIS 自带库里的注记类(acls)与三维类(3dfcls)样本。"""
from __future__ import annotations

import os
import sqlite3
import sys

MAPGIS_HOME = os.environ.get("MAPGIS_HOME", r"D:\Program Files\MapGIS 10")

CANDIDATES = [
    os.path.join(MAPGIS_HOME, "Sample", "sample.hdb"),
    os.path.join(MAPGIS_HOME, "Sample", u"示例数据.hdb"),
]


def probe(path: str) -> None:
    print("=" * 70)
    print(path, os.path.getsize(path), "字节")
    from pathlib import Path
    con = sqlite3.connect(Path(path).as_uri() + "?mode=ro&immutable=1", uri=True)
    cur = con.cursor()
    try:
        rows = cur.execute(
            "select id,name,physical_name,type,subtype,objcnt from mpdb_item order by id").fetchall()
    except Exception as exc:
        print("  mpdb_item 读取失败:", exc)
        return
    print("  mpdb_item %d 条:" % len(rows))
    for r in rows:
        print("    id=%-4s type=%-4s subtype=%-4s objcnt=%-6s %-20s %s"
              % (r[0], r[3], r[4], r[5], r[1], r[2]))

    # 分类统计 type
    types = {}
    for r in rows:
        types[r[3]] = types.get(r[3], 0) + 1
    print("  type 分布:", types)

    # 表名规律
    tables = [r[0] for r in cur.execute(
        "select name from sqlite_master where type='table' and name not like '%_rtree%' "
        "and name not like '%_node%' and name not like '%_parent%' and name not like '%_rowid%' "
        "order by name")]
    prefixes = {}
    for t in tables:
        p = "".join(ch for ch in t if not ch.isdigit())
        prefixes[p] = prefixes.get(p, 0) + 1
    print("  表名前缀分布:", prefixes)

    # 找可能的注记/三维表
    for t in tables:
        if t.startswith(("ann", "acls", "3d", "mp3", "mpa")):
            sql = cur.execute("select sql from sqlite_master where name=?", (t,)).fetchone()
            print("  候选表 %s: %s" % (t, (sql[0] if sql else "")[:220]))
    con.close()


if __name__ == "__main__":
    for p in CANDIDATES:
        if os.path.exists(p):
            probe(p)
        else:
            print("缺失:", p)
