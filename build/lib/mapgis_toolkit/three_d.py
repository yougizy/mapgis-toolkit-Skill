"""MapGIS 三维面几何(mptype 8/9)编解码。

实测结构(来自 `示例数据.hdb` 的 `mpf27`)::

    int32 -22          # 三维标记
    int32 parts        # 部件数
    重复 parts 次:
        int32 -21      # 部件标记
        int32 n        # 顶点数
        n × (x, y, z)  # float64

文件尾可能还有若干 int32 索引,解码时忽略。
"""

from __future__ import annotations

import struct
from typing import List, Sequence

MARK_3D = -22
MARK_PART = -21


class ThreeDError(RuntimeError):
    """三维几何异常。"""


def decode_shape3d(blob: bytes) -> List[List[tuple]]:
    """解析三维面,返回 ``[[(x, y, z), ...], ...]``。"""
    data = bytes(blob)
    if len(data) < 8:
        raise ThreeDError("三维几何过短: %d" % len(data))
    marker, parts = struct.unpack_from("<2i", data, 0)
    if marker != MARK_3D:
        raise ThreeDError("缺少三维标记(-22),实际 %d" % marker)
    if parts < 0 or parts > 100000:
        raise ThreeDError("部件数异常: %d" % parts)

    out: List[List[tuple]] = []
    pos = 8
    for _ in range(parts):
        if pos + 8 > len(data):
            break
        mark, n = struct.unpack_from("<2i", data, pos)
        if mark != MARK_PART:
            # 结构不完全一致时,向后找下一个 -21
            idx = data.find(struct.pack("<i", MARK_PART), pos)
            if idx < 0:
                break
            pos = idx
            mark, n = struct.unpack_from("<2i", data, pos)
        if n < 0 or n > 1000000:
            break
        pos += 8
        need = n * 24
        if pos + need > len(data):
            break
        pts = [struct.unpack_from("<3d", data, pos + i * 24) for i in range(n)]
        out.append(pts)
        pos += need
    return out


def encode_shape3d(parts: Sequence[Sequence[Sequence[float]]]) -> bytes:
    """编码三维面:``[[(x, y, z), ...], ...]``。"""
    buf = bytearray()
    buf += struct.pack("<2i", MARK_3D, len(parts))
    for ring in parts:
        buf += struct.pack("<2i", MARK_PART, len(ring))
        for p in ring:
            x, y, z = (list(p) + [0.0, 0.0, 0.0])[:3]
            buf += struct.pack("<3d", float(x), float(y), float(z))
    # 尾部两个索引(与样本一致:部件数, 部件数)
    buf += struct.pack("<2i", len(parts), len(parts))
    return bytes(buf)


def bbox3d(parts: Sequence[Sequence[Sequence[float]]]):
    xs = [p[0] for ring in parts for p in ring]
    ys = [p[1] for ring in parts for p in ring]
    zs = [p[2] for ring in parts for p in ring]
    return min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)
