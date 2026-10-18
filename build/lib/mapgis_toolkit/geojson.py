"""GeoJSON 读写(纯标准库)。

支持 Point / LineString / Polygon / MultiPolygon 与 FeatureCollection。

内部几何结构与 :mod:`mapgis_toolkit.shp` 一致::

    {"parts": [[(x, y), ...], ...], "attrs": {"字段": 值}}
"""

from __future__ import annotations

import json
from typing import Dict, List, Sequence

GEOM_TO_KIND = {"Point": "Point", "LineString": "Line", "Polygon": "Region",
                "MultiPolygon": "Region", "MultiLineString": "Line"}


class GeoJsonError(ValueError):
    """GeoJSON 读写异常。"""


def _ring(coords: Sequence) -> List[tuple]:
    return [(float(p[0]), float(p[1])) for p in coords]


def read_geojson(path: str) -> List[dict]:
    """读取 GeoJSON,返回要素列表(``parts`` + ``attrs``)。"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("type") == "FeatureCollection":
        feats = data.get("features", [])
    elif data.get("type") == "Feature":
        feats = [data]
    else:
        # 裸几何
        feats = [{"type": "Feature", "geometry": data, "properties": {}}]

    out: List[dict] = []
    for feat in feats:
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        attrs = dict(feat.get("properties") or {})
        if not gtype or coords is None:
            continue
        if gtype == "Point":
            parts = [[(float(coords[0]), float(coords[1]))]]
        elif gtype == "MultiPoint":
            parts = [[(float(p[0]), float(p[1]))] for p in coords]
        elif gtype == "LineString":
            parts = [_ring(coords)]
        elif gtype == "MultiLineString":
            parts = [_ring(line) for line in coords]
        elif gtype == "Polygon":
            parts = [_ring(ring) for ring in coords]
        elif gtype == "MultiPolygon":
            # 一个要素包含多个环(写入 HDB 时会按"每环一要素"自动拆分)
            parts = []
            for poly in coords:
                for ring in poly:
                    parts.append(_ring(ring))
            out.append({"parts": parts, "attrs": attrs})
            continue
        else:
            continue
        out.append({"parts": parts, "attrs": attrs})
    return out


def _closed(ring: Sequence[tuple]) -> List[list]:
    pts = [[float(x), float(y)] for x, y in ring]
    if pts and pts[0] != pts[-1]:
        pts.append(list(pts[0]))
    return pts


def write_geojson(path: str, features: Sequence[dict], kind: str = "Region",
                  name_field: str | None = None) -> int:
    """写出 GeoJSON;``kind`` 为 Point / Line / Region。返回要素数。"""
    out = []
    for f in features:
        parts = f.get("parts") or []
        if not parts:
            continue
        if kind == "Point":
            x, y = parts[0][0]
            geom = {"type": "Point", "coordinates": [x, y]}
        elif kind == "Line":
            if len(parts) == 1:
                geom = {"type": "LineString",
                        "coordinates": [[x, y] for x, y in parts[0]]}
            else:
                geom = {"type": "MultiLineString",
                        "coordinates": [[[x, y] for x, y in ring] for ring in parts]}
        else:
            if len(parts) == 1:
                geom = {"type": "Polygon", "coordinates": [_closed(parts[0])]}
            else:
                geom = {"type": "MultiPolygon",
                        "coordinates": [[_closed(ring)] for ring in parts]}
        out.append({"type": "Feature", "geometry": geom,
                    "properties": f.get("attrs") or {}})

    data: Dict = {"type": "FeatureCollection", "features": out}
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False)
    return len(out)
