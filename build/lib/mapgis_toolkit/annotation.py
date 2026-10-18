"""MapGIS 注记类(acls)读写。

表结构来自 MapGIS 自带 `sample.hdb` 的 `mpa41`(地物注记,type=5):

    mpaN(mpoid, mptype, mpshape, mpparts, mpcontent, mplocate_arr,
         mpangle_arr, mpstring_arr, mpmtime, mpheight, mpwidth, mpspace,
         mpstrangle, mpfont, mpfont1, mpstyle, mpvertical, mpcolor,
         mpchflag, mpbold, mpunderline, mphollow, mpstriklethrough,
         mpoutline, mpfillflag, mpbackexp, mpbackcolor, mpoffsetx,
         mpoffsety, mplibid, mpsymbolid, mpimage, mpfontang, mpLayer)

几何约定(实测):
    mpshape     = 4 个 float64 → (x, y, x2, y2),前两点即锚点
    mplocate_arr= <I 1> + (x, y, z) float64,共 28 字节
    mptype      = 0(点注记)

图层在 `.mapx` 里通过 `gdbp://.../acls/<名称>` 引用。
"""

from __future__ import annotations

import sqlite3
import struct
import uuid as _uuid
from typing import Iterable, List, Optional

_ANNOTATION_DEF_XML = (
    '<?xml version="1.0"?>\n'
    '<MpGDBItemDef>\n\t<Type>AnnotationCls</Type>\n\t<Content>\n\t\t'
    '<MpAnnotationClsDef version="1.0">\n\t\t\t<OIDColumnName />\n\t\t\t'
    '<OIDSequenceName />\n\t\t\t<mpSystemGUID />\n\t\t\t'
    '<RangeValid>true</RangeValid>\n\t\t</MpAnnotationClsDef>\n\t</Content>\n'
    '</MpGDBItemDef>')

ANNOTATION_SQL = """CREATE TABLE "{table}"(
    mpoid INTEGER PRIMARY KEY,
    mptype INTEGER NOT NULL,
    mpshape BLOB NOT NULL,
    mpparts INTEGER,
    mpcontent TEXT,
    mplocate_arr BLOB NOT NULL,
    mpangle_arr BLOB,
    mpstring_arr BLOB,
    mpmtime TEXT NOT NULL DEFAULT (datetime(CURRENT_TIMESTAMP,'localtime')),
    mpheight REAL, mpwidth REAL, mpspace REAL, mpstrangle REAL,
    mpfont INTEGER, mpfont1 INTEGER, mpstyle INTEGER, mpvertical INTEGER,
    mpcolor INTEGER, mpchflag INTEGER, mpbold INTEGER, mpunderline INTEGER,
    mphollow INTEGER, mpstriklethrough INTEGER, mpoutline INTEGER,
    mpfillflag INTEGER, mpbackexp REAL, mpbackcolor INTEGER,
    mpoffsetx REAL, mpoffsety REAL, mplibid INTEGER, mpsymbolid INTEGER,
    mpimage BLOB, mpfontang REAL,
    mpLayer INTEGER NOT NULL DEFAULT 0)"""


class AnnotationError(RuntimeError):
    """注记类操作异常。"""


# ---------------------------------------------------------------------------
# 几何编码
# ---------------------------------------------------------------------------

def encode_shape(x: float, y: float, x2: Optional[float] = None,
                 y2: Optional[float] = None) -> bytes:
    """mpshape:4 个 float64。默认退化为 (x, y, x, y)。"""
    return struct.pack("<4d", x, y, x if x2 is None else x2,
                       y if y2 is None else y2)


def decode_shape(blob: bytes):
    if len(blob) < 32:
        raise AnnotationError("mpshape 长度异常: %d" % len(blob))
    return struct.unpack("<4d", blob[:32])


def encode_locate(x: float, y: float, z: float = 0.0) -> bytes:
    """mplocate_arr:<I 1> + (x, y, z),28 字节。"""
    return struct.pack("<I3d", 1, x, y, z)


def decode_locate(blob: bytes):
    if len(blob) < 28:
        raise AnnotationError("mplocate_arr 长度异常: %d" % len(blob))
    n, x, y, z = struct.unpack("<I3d", blob[:28])
    return n, x, y, z


# ---------------------------------------------------------------------------
# 要素类管理
# ---------------------------------------------------------------------------

def _next_id(con: sqlite3.Connection) -> int:
    row = con.execute("select max(id) from mpdb_item").fetchone()
    return (row[0] or 0) + 1


def _annotation_id(con: sqlite3.Connection, name: str) -> int:
    row = con.execute(
        "select id from mpdb_item where name=? and type=5", (name,)).fetchone()
    if not row:
        raise AnnotationError("注记类不存在: %s" % name)
    return row[0]


def list_annotation_classes(con: sqlite3.Connection) -> List[dict]:
    rows = con.execute(
        "select id, name, physical_name, subtype, objcnt from mpdb_item "
        "where type=5 order by id").fetchall()
    return [{"id": r[0], "name": r[1], "physical_name": r[2],
             "subtype": r[3], "objcnt": r[4]} for r in rows]


def add_annotation_class(con: sqlite3.Connection, name: str,
                         items: Iterable[dict], database_name: str,
                         layer: int = 0) -> str:
    """新建注记类并写入注记。

    ``items`` 每项::

        {"x": 116.0, "y": 28.6, "text": "南昌市",
         "height": 4.0, "width": 4.0, "color": 6, "font": 5,
         "bold": 0, "angle": 0.0, "x2": None, "y2": None}
    """
    cid = _next_id(con)
    table = "mpa%d" % cid
    items = list(items)
    con.execute(
        "INSERT INTO mpdb_item(id,name,alias_name,database_name,schema,subset,"
        "physical_name,uuid,type,subtype,dwflags,definition,metadata,objcnt,loadrefcnt) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (cid, name, "", database_name, "main", 1, table,
         _uuid.uuid4().hex.upper(), 5, 0, None, _ANNOTATION_DEF_XML, None,
         len(items), 0))
    con.execute(ANNOTATION_SQL.format(table=table))
    con.execute("INSERT INTO mpdb_sequence(table_name, seq_id) VALUES (?,?)",
                (table, len(items)))

    for i, item in enumerate(items, start=1):
        x = float(item["x"])
        y = float(item["y"])
        con.execute(
            'insert into "%s"(mpoid, mptype, mpshape, mpparts, mpcontent, '
            'mplocate_arr, mpheight, mpwidth, mpfont, mpcolor, mpvertical, '
            'mpbold, mpunderline, mpoutline, mpbackexp, mpbackcolor, '
            'mpoffsetx, mpoffsety, mpfontang, mpLayer) '
            'values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)' % table,
            (i, 0, encode_shape(x, y, item.get("x2"), item.get("y2")), None,
             item.get("text", ""), encode_locate(x, y, item.get("z", 0.0)),
             float(item.get("height", 4.0)), float(item.get("width", 4.0)),
             int(item.get("font", 5)), int(item.get("color", 0)), 1,
             int(item.get("bold", 0)), 0, 0, 0.0, 0,
             0.0, 0.0, float(item.get("angle", 0.0)), layer))
    con.commit()
    return table


def read_annotations(con: sqlite3.Connection, name: str) -> List[dict]:
    """读取注记类,返回 ``[{oid, x, y, z, text, height, color, font, angle}]``。"""
    cid = _annotation_id(con, name)
    table = con.execute("select physical_name from mpdb_item where id=?",
                        (cid,)).fetchone()[0]
    out = []
    for row in con.execute(
            'select mpoid, mpcontent, mplocate_arr, mpheight, mpcolor, '
            'mpfont, mpfontang, mpLayer from "%s" order by mpoid' % table):
        try:
            _, x, y, z = decode_locate(bytes(row[2]))
        except AnnotationError:
            continue
        out.append({"oid": row[0], "text": row[1], "x": x, "y": y, "z": z,
                    "height": row[3], "color": row[4], "font": row[5],
                    "angle": row[6], "layer": row[7]})
    return out


def delete_annotation_class(con: sqlite3.Connection, name: str) -> None:
    cid = _annotation_id(con, name)
    table = con.execute("select physical_name from mpdb_item where id=?",
                        (cid,)).fetchone()[0]
    con.execute('DROP TABLE IF EXISTS "%s"' % table)
    con.execute("delete from mpdb_item where id=?", (cid,))
    con.execute("delete from mpdb_sequence where table_name=?", (table,))
    con.commit()


def _skod(name: str) -> str:
    """MapGIS 的 mskod 字段(32 位十六进制);用名称哈希保证稳定。"""
    import hashlib
    return hashlib.md5(name.encode("utf-8")).hexdigest().upper()
