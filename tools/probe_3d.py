# -*- coding: utf-8 -*-
"""解析 mpf27(mptype 8/9)的三维几何 BLOB 结构。"""
from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

MAPGIS_HOME = __import__("os").environ.get(
    "MAPGIS_HOME", r"D:\Program Files\MapGIS 10")
DEMO = MAPGIS_HOME + r"\Sample\示例数据.hdb"


def dump(blob: bytes, limit: int = 120) -> None:
    n = len(blob)
    print("  BLOB %d 字节,前 %d:" % (n, min(n, limit)))
    print("   ", blob[:limit].hex())
    pos = 0
    depth = 0
    while pos + 4 <= n and depth < 40:
        (v,) = struct.unpack_from("<i", blob, pos)
        if v in (-22, -21, -20, -23, -24):
            print("   [%4d] marker %d" % (pos, v))
            pos += 4
            if pos + 4 <= n:
                (cnt,) = struct.unpack_from("<i", blob, pos)
                print("   [%4d] count %d" % (pos, cnt))
                pos += 4
                if 0 <= cnt < 500 and pos + cnt * 24 <= n:
                    # 后续是否像坐标
                    pts = struct.unpack_from("<%dd" % (cnt * 3), blob, pos) if cnt else ()
                    if pts:
                        print("         首点 (%.3f, %.3f, %.3f)" % pts[:3])
                        print("         末点 (%.3f, %.3f, %.3f)" % pts[-3:])
                    pos += cnt * 24
                    depth += 1
                    continue
        print("   [%4d] 未知值 %d" % (pos, v))
        break
    print("   解析到偏移 %d / %d" % (pos, n))


def main() -> None:
    con = sqlite3.connect(Path(DEMO).as_uri() + "?mode=ro&immutable=1", uri=True)
    for oid, mptype, blob in con.execute(
            "select mpoid, mptype, mpshape from mpf27 order by mpoid limit 4"):
        print("==", oid, "mptype", mptype)
        dump(bytes(blob))
    con.close()


if __name__ == "__main__":
    main()
