"""地理运算(基于 shapely / pyproj)。

功能:
    - 要素 <-> shapely 几何互转
    - 裁剪(clip)、缓冲(buffer)、相交(intersect)、融合(union)
    - 坐标投影(project)

依赖为可选:`pip install shapely pyproj`
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

try:
    from shapely.geometry import (LineString, MultiLineString, MultiPolygon, Point,
                                  Polygon, mapping, shape)
    from shapely.ops import transform as _shp_transform
    from shapely.ops import unary_union
except ImportError as exc:  # pragma: no cover
    raise ImportError("需要 shapely:pip install shapely") from exc

try:
    from pyproj import CRS, Transformer
except ImportError:  # pragma: no cover
    CRS = None
    Transformer = None


class OpsError(RuntimeError):
    """地理运算异常。"""


def feature_to_geometry(feature: dict, kind: str):
    """把内部要素结构转成 shapely 几何(多部分会合并)。"""
    parts = [p for p in (feature.get("parts") or []) if p]
    if not parts:
        raise OpsError("空几何")
    if kind == "Point":
        return MultiPointOrPoint([Point(x, y) for x, y in parts[0]])
    if kind == "Line":
        lines = [LineString(p) for p in parts]
        return lines[0] if len(lines) == 1 else MultiLineString(lines)
    polys = []
    for ring in parts:
        # 自闭合
        pts = list(ring)
        if pts[0] != pts[-1]:
            pts.append(pts[0])
        polys.append(Polygon(pts))
    return polys[0] if len(polys) == 1 else MultiPolygon(polys)


def MultiPointOrPoint(points):
    from shapely.geometry import MultiPoint
    return points[0] if len(points) == 1 else MultiPoint(points)


def geometry_to_features(geom, attrs: Optional[dict] = None,
                         kind: Optional[str] = None) -> List[dict]:
    """把 shapely 几何拆成内部要素结构(每个环/线/点一个要素)。"""
    attrs = attrs or {}
    if geom.is_empty:
        return []
    gtype = geom.geom_type
    if gtype == "Point":
        return [{"parts": [[(geom.x, geom.y)]], "attrs": attrs}]
    if gtype == "MultiPoint":
        return [{"parts": [[(g.x, g.y)]], "attrs": attrs} for g in geom.geoms]
    if gtype == "LineString":
        return [{"parts": [list(geom.coords)], "attrs": attrs}]
    if gtype == "MultiLineString":
        return [{"parts": [list(g.coords)], "attrs": attrs} for g in geom.geoms]
    if gtype == "Polygon":
        return [{"parts": [list(geom.exterior.coords)], "attrs": attrs}]
    if gtype == "MultiPolygon":
        return [{"parts": [list(g.exterior.coords)], "attrs": attrs}
                for g in geom.geoms]
    if gtype == "GeometryCollection":
        out = []
        for g in geom.geoms:
            out.extend(geometry_to_features(g, attrs, kind))
        return out
    raise OpsError("不支持的几何类型: %s" % gtype)


def clip(features: Sequence[dict], kind: str,
         mask_features: Sequence[dict], mask_kind: str = "Region") -> List[dict]:
    """用一个面(或一组面)裁剪要素。"""
    mask = unary_union([feature_to_geometry(m, mask_kind) for m in mask_features])
    out: List[dict] = []
    for f in features:
        g = feature_to_geometry(f, kind).intersection(mask)
        out.extend(geometry_to_features(g, f.get("attrs") or {}, kind))
    return out


def buffer_features(features: Sequence[dict], kind: str,
                    distance: float) -> List[dict]:
    """对要素做缓冲,结果是面。"""
    out: List[dict] = []
    for f in features:
        g = feature_to_geometry(f, kind).buffer(distance)
        out.extend(geometry_to_features(g, f.get("attrs") or {}, "Region"))
    return out


def intersect(a: Sequence[dict], a_kind: str,
              b: Sequence[dict], b_kind: str) -> List[dict]:
    """两组要素求交。"""
    ga = unary_union([feature_to_geometry(f, a_kind) for f in a])
    gb = unary_union([feature_to_geometry(f, b_kind) for f in b])
    return geometry_to_features(ga.intersection(gb), {}, "Region")


def dissolve(features: Sequence[dict], kind: str) -> List[dict]:
    """融合为一个几何。"""
    g = unary_union([feature_to_geometry(f, kind) for f in features])
    return geometry_to_features(g, {}, kind)


def project(features: Sequence[dict], src_crs: str, dst_crs: str) -> List[dict]:
    """坐标投影;``src_crs`` / ``dst_crs`` 可为 EPSG 号或 WKT。"""
    if Transformer is None:
        raise OpsError("需要 pyproj:pip install pyproj")
    tr = Transformer.from_crs(src_crs, dst_crs, always_xy=True)

    def _fn(x, y):
        nx, ny = tr.transform(x, y)
        return nx, ny

    out = []
    for f in features:
        out.append({
            "parts": [[_fn(x, y) for x, y in ring] for ring in f.get("parts") or []],
            "attrs": f.get("attrs") or {},
        })
    return out


def project_extent(bbox: Sequence[float], src_crs: str, dst_crs: str) -> List[float]:
    """投影范围 ``[xmin, ymin, xmax, ymax]``。"""
    if Transformer is None:
        raise OpsError("需要 pyproj:pip install pyproj")
    tr = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    xs, ys = [], []
    for x, y in ((bbox[0], bbox[1]), (bbox[2], bbox[3]),
                 (bbox[0], bbox[3]), (bbox[2], bbox[1])):
        nx, ny = tr.transform(x, y)
        xs.append(nx)
        ys.append(ny)
    return [min(xs), min(ys), max(xs), max(ys)]
