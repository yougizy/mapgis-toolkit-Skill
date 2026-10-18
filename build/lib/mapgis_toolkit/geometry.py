"""MapGIS 10 几何二进制编解码(mpshape)。

逆向自 MapGIS 10.8 自带示例库 ``Sample/示例数据.hdb``,并做过字节级 roundtrip 验证:

===========  =========  ============================================================
几何类型      mptype     二进制结构(小端)
===========  =========  ============================================================
点           1          ``<I 1>`` + ``<3d x, y, z>``(共 28 字节)
线           4          ``b"\\x00\\x02"`` + ``<B 点数>`` + ``b"\\x00\\x00\\x00"``
                        + ``<2d x, y> * 点数``
区           8          ``b"\\x01\\x00\\x00\\x00\\x01\\x00\\x00\\x00\\x07\\x00\\x02"``
                        + ``<I 点数>`` + ``<2d x, y> * 点数``
===========  =========  ============================================================

验证结果:线 49/49、区 19/19、点 485/485 解析后重新序列化与原字节完全一致。
"""

from __future__ import annotations

import struct
from typing import Iterable, List, Sequence, Tuple

#: mptype 取值
MPTYPE_POINT = 1
MPTYPE_LINE = 4
MPTYPE_REGION = 8

MPTYPE_BY_KIND = {"Point": MPTYPE_POINT, "Line": MPTYPE_LINE, "Region": MPTYPE_REGION}
KIND_BY_MPTYPE = {v: k for k, v in MPTYPE_BY_KIND.items()}

#: 线的点数用 1 字节存储,超过需拆分
MAX_LINE_POINTS = 255

_HEAD_POINT = struct.pack("<I", 1)
_HEAD_LINE = b"\x00\x02"
_HEAD_LINE_TAIL = b"\x00\x00\x00"
_HEAD_REGION = b"\x01\x00\x00\x00\x01\x00\x00\x00\x07\x00\x02"

Point = Tuple[float, float]


class GeometryError(ValueError):
    """几何数据不合法。"""


def encode_point(x: float, y: float, z: float = 0.0) -> bytes:
    """编码点几何。"""
    return _HEAD_POINT + struct.pack("<3d", x, y, z)


def encode_line(points: Sequence[Point]) -> bytes:
    """编码线几何;点数须在 1..255,超长请先 :func:`split_line`。"""
    n = len(points)
    if not 0 < n <= MAX_LINE_POINTS:
        raise GeometryError("线的点数必须在 1..255,当前 %d" % n)
    buf = bytearray(_HEAD_LINE)
    buf.append(n)
    buf += _HEAD_LINE_TAIL
    for x, y in points:
        buf += struct.pack("<2d", x, y)
    return bytes(buf)


def encode_region(points: Sequence[Point]) -> bytes:
    """编码区几何;首尾点应闭合。"""
    buf = bytearray(_HEAD_REGION)
    buf += struct.pack("<I", len(points))
    for x, y in points:
        buf += struct.pack("<2d", x, y)
    return bytes(buf)


def decode_point(blob: bytes) -> Tuple[float, float, float]:
    """解码点几何,返回 ``(x, y, z)``。"""
    if len(blob) < 28:
        raise GeometryError("点几何长度不足: %d" % len(blob))
    return struct.unpack("<3d", blob[4:28])


def decode_line(blob: bytes) -> List[Point]:
    """解码线几何,返回点列表。"""
    if len(blob) < 6 or (len(blob) - 6) % 16:
        raise GeometryError("线几何长度不合法: %d" % len(blob))
    vals = struct.unpack("<%dd" % ((len(blob) - 6) // 8), blob[6:])
    return [(vals[i], vals[i + 1]) for i in range(0, len(vals), 2)]


def decode_region(blob: bytes) -> List[Point]:
    """解码区几何,返回点列表。"""
    if len(blob) < 15:
        raise GeometryError("区几何长度不足: %d" % len(blob))
    n = struct.unpack("<I", blob[11:15])[0]
    if 15 + n * 16 > len(blob):
        raise GeometryError("区几何点数与长度不符: n=%d len=%d" % (n, len(blob)))
    vals = struct.unpack("<%dd" % (n * 2), blob[15:15 + n * 16])
    return [(vals[i], vals[i + 1]) for i in range(0, len(vals), 2)]


def decode(blob: bytes, mptype: int) -> List[Point]:
    """按 mptype 解码,统一返回点列表。"""
    if mptype == MPTYPE_POINT:
        x, y, _z = decode_point(blob)
        return [(x, y)]
    if mptype == MPTYPE_LINE:
        return decode_line(blob)
    if mptype == MPTYPE_REGION:
        return decode_region(blob)
    raise GeometryError("不支持的 mptype: %r" % (mptype,))


def split_line(points: Sequence[Point], max_points: int = MAX_LINE_POINTS):
    """把长折线拆成多段(相邻段共享端点),返回列表的列表。"""
    if len(points) <= max_points:
        return [list(points)]
    if max_points < 2:
        raise GeometryError("max_points 至少为 2")
    out: List[List[Point]] = []
    i = 0
    while i < len(points) - 1:
        out.append(list(points[i:i + max_points]))
        i += max_points - 1
    return out


def bbox(points: Iterable[Point]) -> Tuple[float, float, float, float]:
    """返回 ``(xmin, ymin, xmax, ymax)``。"""
    pts = list(points)
    if not pts:
        raise GeometryError("空几何无法计算范围")
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def ring_area(points: Sequence[Point]) -> float:
    """环的面积(带符号,逆时针为正)。"""
    a = 0.0
    n = len(points)
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def ring_perimeter(points: Sequence[Point]) -> float:
    """环的周长(闭合统计)。"""
    p = 0.0
    n = len(points)
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        p += ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    return p


def centroid(points: Sequence[Point]) -> Point:
    """多边形环的面积质心;退化时退化为顶点平均。"""
    a = cx = cy = 0.0
    n = len(points)
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    a *= 0.5
    if abs(a) < 1e-12:
        return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)
    return cx / (6 * a), cy / (6 * a)


def _point_segment_distance(p: Point, a: Point, b: Point) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj = (ax + t * dx, ay + t * dy)
    return ((px - proj[0]) ** 2 + (py - proj[1]) ** 2) ** 0.5


def simplify(points: Sequence[Point], tolerance: float) -> List[Point]:
    """Douglas-Peucker 线抽稀(保留首尾点)。"""
    if tolerance <= 0 or len(points) <= 2:
        return list(points)
    first, last = points[0], points[-1]
    max_d = -1.0
    index = 0
    for i in range(1, len(points) - 1):
        d = _point_segment_distance(points[i], first, last)
        if d > max_d:
            max_d, index = d, i
    if max_d > tolerance:
        left = simplify(points[:index + 1], tolerance)
        right = simplify(points[index:], tolerance)
        return left[:-1] + right
    return [first, last]


def densify_ring(points: Sequence[Point]) -> List[Point]:
    """确保环闭合(首尾相同)。"""
    pts = list(points)
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts
