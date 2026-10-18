"""ESRI Shapefile 读写(纯标准库,不依赖 GDAL/pyshp)。

支持:
    - 读取 Point(1) / PolyLine(3) / Polygon(5)
    - 写入 Point(1) / PolyLine(3) / Polygon(5)
    - 读取/写入配套 .dbf(字段名与文本按 GBK 编解码)

``read_shp`` 返回的要素结构::

    {"parts": [[(x, y), ...], ...], "attrs": {"字段": "值"}}

点要素的 ``parts`` 只有一个仅含一个点的列表。
"""

from __future__ import annotations

import os
import struct
from typing import Dict, List, Mapping, Sequence, Tuple

SHAPE_NULL = 0
SHAPE_POINT = 1
SHAPE_POLYLINE = 3
SHAPE_POLYGON = 5

SHAPE_NAME = {SHAPE_POINT: "Point", SHAPE_POLYLINE: "PolyLine", SHAPE_POLYGON: "Polygon"}
SHAPE_BY_KIND = {"Point": SHAPE_POINT, "Line": SHAPE_POLYLINE, "Region": SHAPE_POLYGON}


class ShapefileError(ValueError):
    """Shapefile 读写异常。"""


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("gbk").strip()
    except UnicodeDecodeError:
        return raw.decode("utf-8", "replace").strip()


def _encode(text: str) -> bytes:
    try:
        return text.encode("gbk")
    except UnicodeEncodeError:
        return text.encode("utf-8")


# ---------------------------------------------------------------------------
# DBF
# ---------------------------------------------------------------------------

def read_dbf(path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """读取 .dbf,返回 ``(字段名列表, 记录列表)``。"""
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 32:
        return [], []
    n_rec = struct.unpack("<I", data[4:8])[0]
    hdr_len = struct.unpack("<H", data[8:10])[0]
    rec_len = struct.unpack("<H", data[10:12])[0]

    fields: List[Tuple[str, int]] = []
    off = 32
    while off < hdr_len - 1 and data[off] != 0x0D:
        raw = data[off:off + 32]
        name = _decode(raw[:11].split(b"\x00")[0])
        fields.append((name, raw[16]))
        off += 32

    rows: List[Dict[str, str]] = []
    pos = hdr_len
    for _ in range(n_rec):
        if pos + rec_len > len(data):
            break
        rec = data[pos:pos + rec_len]
        pos += rec_len
        if rec[:1] == b"*":  # 逻辑删除
            continue
        row: Dict[str, str] = {}
        p = 1
        for name, flen in fields:
            row[name] = _decode(rec[p:p + flen])
            p += flen
        rows.append(row)
    return [f[0] for f in fields], rows


def write_dbf(path: str, fields: Sequence[str], rows: Sequence[Mapping[str, object]],
              text_len: int = 60) -> None:
    """写 .dbf;所有字段按文本存储(长度 ``text_len``)。"""
    n = len(rows)
    rec_len = 1 + len(fields) * text_len
    hdr_len = 32 + 32 * len(fields) + 1
    buf = bytearray()
    buf += struct.pack("<BBBBIHH", 0x03, 126, 1, 1, n, hdr_len, rec_len)
    buf += b"\x00" * 20
    for name in fields:
        nb = _encode(name)[:10].ljust(11, b"\x00")
        buf += nb + b"C" + b"\x00" * 4 + bytes([text_len, 0]) + b"\x00" * 14
    buf.append(0x0D)
    for row in rows:
        buf.append(0x20)
        for name in fields:
            val = row.get(name, "")
            text = "" if val is None else str(val)
            buf += _encode(text)[:text_len].ljust(text_len, b" ")
    buf.append(0x1A)
    with open(path, "wb") as f:
        f.write(bytes(buf))


# ---------------------------------------------------------------------------
# SHP / SHX
# ---------------------------------------------------------------------------

def read_shp(path: str, dbf_path: str | None = None):
    """读取 shapefile,返回 ``(shape_type, features)``。"""
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 100 or struct.unpack(">i", data[0:4])[0] != 9994:
        raise ShapefileError("不是有效的 shapefile: %s" % path)
    shape_type = struct.unpack("<i", data[32:36])[0]

    attrs: List[Dict[str, str]] = []
    db = dbf_path or os.path.splitext(path)[0] + ".dbf"
    if os.path.exists(db):
        _fields, attrs = read_dbf(db)

    feats: List[dict] = []
    pos = 100
    idx = 0
    while pos + 8 <= len(data):
        _recno, clen = struct.unpack(">2i", data[pos:pos + 8])
        pos += 8
        content = data[pos:pos + clen * 2]
        pos += clen * 2
        if len(content) < 4:
            break
        t = struct.unpack("<i", content[0:4])[0]
        a = attrs[idx] if idx < len(attrs) else {}
        idx += 1
        if t == SHAPE_NULL:
            continue
        if t == SHAPE_POINT:
            x, y = struct.unpack("<2d", content[4:20])
            feats.append({"parts": [[(x, y)]], "attrs": a})
        elif t in (SHAPE_POLYLINE, SHAPE_POLYGON):
            n_parts, n_pts = struct.unpack("<2i", content[36:44])
            parts = struct.unpack("<%di" % n_parts, content[44:44 + n_parts * 4])
            poff = 44 + n_parts * 4
            pts = struct.unpack("<%dd" % (n_pts * 2), content[poff:poff + n_pts * 16])
            rings = []
            for i, start in enumerate(parts):
                end = parts[i + 1] if i + 1 < len(parts) else n_pts
                rings.append([(pts[j * 2], pts[j * 2 + 1]) for j in range(start, end)])
            feats.append({"parts": rings, "attrs": a})
        else:
            continue
    return shape_type, feats


def write_shp(path: str, shape_type: int, features: Sequence[dict],
              fields: Sequence[str] | None = None, prj_wkt: str | None = None) -> None:
    """写 shapefile(.shp/.shx/.dbf/.prj)。

    ``features`` 结构同 :func:`read_shp` 的返回值。
    """
    if shape_type not in SHAPE_NAME:
        raise ShapefileError("不支持的 shape type: %r" % shape_type)

    # 计算范围
    xs: List[float] = []
    ys: List[float] = []
    for f in features:
        for ring in f["parts"]:
            for x, y in ring:
                xs.append(x)
                ys.append(y)
    if xs:
        xmin, ymin, xmax, ymax = min(xs), min(ys), max(xs), max(ys)
    else:
        xmin = ymin = xmax = ymax = 0.0

    records: List[bytes] = []
    for f in features:
        parts = f["parts"]
        if shape_type == SHAPE_POINT:
            x, y = parts[0][0]
            records.append(struct.pack("<i2d", SHAPE_POINT, x, y))
            continue
        n_parts = len(parts)
        n_pts = sum(len(r) for r in parts)
        content = bytearray()
        content += struct.pack("<i4d2i", shape_type, xmin, ymin, xmax, ymax,
                               n_parts, n_pts)
        start = 0
        for ring in parts:
            content += struct.pack("<i", start)
            start += len(ring)
        for ring in parts:
            for x, y in ring:
                content += struct.pack("<2d", x, y)
        records.append(bytes(content))

    # .shp
    total_words = 50 + sum((8 + len(r)) // 2 for r in records)
    shp = bytearray()
    shp += struct.pack(">i", 9994) + b"\x00" * 20 + struct.pack(">i", total_words)
    shp += struct.pack("<2i", 1000, shape_type)
    shp += struct.pack("<4d", xmin, ymin, xmax, ymax)
    shp += struct.pack("<4d", 0.0, 0.0, 0.0, 0.0)
    offset_words = 50
    shx_records = bytearray()
    for i, rec in enumerate(records, 1):
        clen = len(rec) // 2
        shp += struct.pack(">2i", i, clen) + rec
        shx_records += struct.pack(">2i", offset_words, clen)
        offset_words += 4 + clen
    shx = bytearray()
    shx += struct.pack(">i", 9994) + b"\x00" * 20 + struct.pack(">i", 50 + len(shx_records) // 2)
    shx += struct.pack("<2i", 1000, shape_type)
    shx += struct.pack("<4d", xmin, ymin, xmax, ymax)
    shx += struct.pack("<4d", 0.0, 0.0, 0.0, 0.0)
    shx += shx_records
    with open(path, "wb") as f:
        f.write(bytes(shp))
    base = os.path.splitext(path)[0]
    with open(base + ".shx", "wb") as f:
        f.write(bytes(shx))

    # .dbf
    fields = list(fields or [])
    if not fields:
        keys: List[str] = []
        for f in features:
            for k in f.get("attrs", {}):
                if k not in keys:
                    keys.append(k)
        fields = keys
    write_dbf(base + ".dbf", fields, [f.get("attrs", {}) for f in features])

    if prj_wkt:
        with open(base + ".prj", "w", encoding="utf-8") as f:
            f.write(prj_wkt)
