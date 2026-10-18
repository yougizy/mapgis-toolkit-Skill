"""拓扑与几何质量检查(基于 shapely)。

检查项:
    - 无效几何(自相交、环方向错误等)
    - 面重叠(overlaps,可设面积阈值)
    - 重复几何(WKB 相同)
    - 线悬挂点(度数为 1 的端点)
    - 点重复(坐标相同)

返回结构统一为::

    {"ok": bool, "issues": [{"type","oid","oid2","detail"}], "count": N}
"""

from __future__ import annotations

from typing import List, Sequence

try:
    from shapely.validation import explain_validity
    from shapely.wkb import dumps as wkb_dumps
except ImportError as exc:  # pragma: no cover
    raise ImportError("需要 shapely:pip install shapely") from exc

from . import ops


class TopologyError(RuntimeError):
    """拓扑检查异常。"""


def _result(issues: List[dict]) -> dict:
    return {"ok": not issues, "count": len(issues), "issues": issues}


def check_geometries(features: Sequence[dict], kind: str) -> dict:
    """通用检查:无效几何 + 重复几何。"""
    issues: List[dict] = []
    seen = {}
    for i, f in enumerate(features):
        oid = f.get("oid", i)
        try:
            geom = ops.feature_to_geometry(f, kind)
        except Exception as exc:
            issues.append({"type": "invalid", "oid": oid, "detail": str(exc)})
            continue
        if not geom.is_valid:
            issues.append({"type": "invalid", "oid": oid,
                           "detail": explain_validity(geom)})
        key = wkb_dumps(geom, hex=True)
        if key in seen:
            issues.append({"type": "duplicate", "oid": oid, "oid2": seen[key],
                           "detail": "与 oid=%s 几何相同" % seen[key]})
        else:
            seen[key] = oid
    return _result(issues)


def check_overlaps(features: Sequence[dict], min_area: float = 0.0) -> dict:
    """面重叠检查:两两相交且相交面积 > ``min_area``。"""
    issues: List[dict] = []
    geoms = []
    for i, f in enumerate(features):
        try:
            geoms.append((f.get("oid", i), ops.feature_to_geometry(f, "Region")))
        except Exception:
            continue
    for a in range(len(geoms)):
        for b in range(a + 1, len(geoms)):
            oid_a, ga = geoms[a]
            oid_b, gb = geoms[b]
            if not ga.intersects(gb):
                continue
            inter = ga.intersection(gb)
            area = getattr(inter, "area", 0.0)
            if area > min_area:
                issues.append({"type": "overlap", "oid": oid_a, "oid2": oid_b,
                               "detail": "重叠面积 %.6f" % area})
    return _result(issues)


def check_gaps(features: Sequence[dict], min_area: float = 0.0) -> dict:
    """面缝隙检查:所有面 union 后与逐个面积之和的差(近似)。"""
    geoms = []
    for i, f in enumerate(features):
        try:
            geoms.append(ops.feature_to_geometry(f, "Region"))
        except Exception:
            continue
    if not geoms:
        return _result([])
    from shapely.ops import unary_union
    merged = unary_union(geoms)
    total = sum(g.area for g in geoms)
    holes = 0.0
    if merged.geom_type in ("Polygon", "MultiPolygon"):
        polys = [merged] if merged.geom_type == "Polygon" else list(merged.geoms)
        for p in polys:
            holes += sum(inter.area for inter in p.interiors)
    issues = []
    if holes > min_area:
        issues.append({"type": "gap", "oid": None,
                       "detail": "内环(洞)总面积 %.6f" % holes})
    if abs(total - merged.area) > max(min_area, 1e-9):
        issues.append({"type": "overlap_total", "oid": None,
                       "detail": "面积总和 %.6f 与融合面积 %.6f 不一致"
                                 % (total, merged.area)})
    return _result(issues)


def check_line_dangles(features: Sequence[dict]) -> dict:
    """线悬挂点:端点只被一条线使用。"""
    from collections import Counter
    counter = Counter()
    for f in features:
        for ring in f.get("parts") or []:
            if len(ring) >= 2:
                counter[(round(ring[0][0], 6), round(ring[0][1], 6))] += 1
                counter[(round(ring[-1][0], 6), round(ring[-1][1], 6))] += 1
    issues = [{"type": "dangle", "oid": None, "detail": "端点 %s 仅连接 1 条线" % (pt,)}
              for pt, n in counter.items() if n == 1]
    return _result(issues)


def check_points_duplicate(features: Sequence[dict]) -> dict:
    """点重复:坐标完全相同。"""
    seen = {}
    issues = []
    for i, f in enumerate(features):
        oid = f.get("oid", i)
        parts = f.get("parts") or []
        if not parts or not parts[0]:
            continue
        key = (round(parts[0][0][0], 6), round(parts[0][0][1], 6))
        if key in seen:
            issues.append({"type": "duplicate", "oid": oid, "oid2": seen[key],
                           "detail": "坐标重复 %s" % (key,)})
        else:
            seen[key] = oid
    return _result(issues)


def run_all(features: Sequence[dict], kind: str) -> dict:
    """按几何类型跑一组检查,汇总结果。"""
    results = {"geometry": check_geometries(features, kind)}
    if kind == "Region":
        results["overlaps"] = check_overlaps(features)
        results["gaps"] = check_gaps(features)
    elif kind == "Line":
        results["dangles"] = check_line_dangles(features)
    elif kind == "Point":
        results["duplicates"] = check_points_duplicate(features)
    total = sum(r["count"] for r in results.values())
    return {"ok": total == 0, "total_issues": total, "checks": results}
