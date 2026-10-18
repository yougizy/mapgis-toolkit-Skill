"""批量出图:一次生成多份 `.mapx`。

典型用法(每个行政区一张图)::

    from mapgis_toolkit import batch

    specs = [{
        "out": r"out/南昌市.mapx",
        "title": "南昌市",
        "view_extent": [115.4, 28.1, 116.6, 29.2],
        "layers": [
            {"name": "南昌市", "url": "gdbp://.../设区市_南昌",
             "geometry_type": "3", "fill": {"fillclr": 15}},
        ],
    }, ...]
    batch.build_batch(specs)

也提供 :func:`build_by_regions`,按"每个区域一个要素类"的约定批量生成。
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence

from . import mapx


def _templates() -> Dict[str, str]:
    return {
        "3": mapx.get_layer_template(mapx.SAMPLE_POLY, u"湖北省边界"),
        "2": mapx.get_layer_template(mapx.SAMPLE_LINE, u"湖北省公路"),
        "1": mapx.get_layer_template(mapx.SAMPLE_LINE, u"湖北省市驻地"),
    }


def build_one(spec: dict, templates: Optional[Dict[str, str]] = None) -> str:
    """按单个 spec 生成 mapx。spec 字段见模块文档。"""
    tpl = templates or _templates()
    parts = []
    for lay in spec.get("layers", []):
        gt = str(lay.get("geometry_type", "3"))
        label = lay.get("label") or {}
        parts.append(mapx.make_layer(
            tpl[gt], lay["name"], lay["url"],
            fill=lay.get("fill"), line=lay.get("line"), point=lay.get("point"),
            label_expr=label.get("expr"),
            label_visible=label.get("visible", True),
            label_size=label.get("size", 10.0),
            label_color=label.get("color", 6),
            theme=lay.get("theme_xml")))
    mapx.build_mapx(spec["out"], spec.get("title", ""), "\n".join(parts),
                    spec["view_extent"], layout_xml=spec.get("layout_xml"))
    return spec["out"]


def build_batch(specs: Sequence[dict]) -> List[str]:
    """批量生成,返回输出路径列表。"""
    tpl = _templates()
    outs = []
    for spec in specs:
        out_dir = os.path.dirname(os.path.abspath(spec["out"]))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        outs.append(build_one(spec, tpl))
    return outs


def build_by_regions(out_dir: str, regions: Sequence[dict],
                     db_name: str, common_layers: Sequence[dict] = (),
                     cache_layer: str = u"市驻地") -> List[str]:
    """按区域批量出图。

    ``regions`` 每项::

        {"name": "南昌市", "class": "设区市_南昌", "extent": [xmin, ymin, xmax, ymax]}

    生成 ``out_dir/<name>.mapx``,图层为:区域面 + ``common_layers``。
    """
    specs = []
    for r in regions:
        base = "gdbp://MapGISLocalPlus/%s/sfcls/" % db_name
        layers = [{"name": r["name"], "url": base + r["class"],
                   "geometry_type": "3", "fill": {"fillclr": r.get("fillclr", 15)}}]
        layers += list(common_layers)
        specs.append({
            "out": os.path.join(out_dir, "%s.mapx" % r["name"]),
            "title": r["name"],
            "view_extent": r["extent"],
            "layers": layers,
        })
    return build_batch(specs)


# ---------------------------------------------------------------------------
# 批量格式转换
# ---------------------------------------------------------------------------

_SHAPE_KIND = {1: "Point", 3: "Line", 5: "Region"}


def convert_shp_dir_to_hdb(db_path: str, shp_dir: str, srid: int = 8,
                           recursive: bool = False) -> List[dict]:
    """把目录下所有 shapefile 导入为 HDB 要素类(要素类名 = 文件名)。

    返回每项 ``{"file", "class", "features"}``。
    """
    import sqlite3
    from . import hdb, shp

    pattern = "**/*.shp" if recursive else "*.shp"
    import glob
    files = sorted(glob.glob(os.path.join(shp_dir, pattern), recursive=recursive))
    con = sqlite3.connect(db_path)
    dbname = os.path.splitext(os.path.basename(db_path))[0]
    results = []
    try:
        for path in files:
            shape_type, feats = shp.read_shp(path)
            kind = _SHAPE_KIND.get(shape_type)
            if not kind:
                results.append({"file": path, "error": "不支持的 shape type %s" % shape_type})
                continue
            name = os.path.splitext(os.path.basename(path))[0]
            fields = [(f, "TEXT", 0, f) for f in (feats[0]["attrs"] if feats else {})]
            hdb.add_feature_class(con, name, kind, feats, fields=fields,
                                  srid=srid, database_name=dbname)
            results.append({"file": path, "class": name, "features": len(feats)})
    finally:
        con.close()
    return results


def convert_hdb_to_shp_dir(db_path: str, out_dir: str) -> List[dict]:
    """把 HDB 里所有要素类导出为 shapefile(文件名 = 要素类名)。"""
    import sqlite3
    from . import hdb

    os.makedirs(out_dir, exist_ok=True)
    con = sqlite3.connect(db_path)
    results = []
    try:
        for row in hdb.list_feature_classes(con):
            name = row["name"]
            out = os.path.join(out_dir, "%s.shp" % name)
            try:
                n = hdb.export_shp(con, name, out)
                results.append({"class": name, "file": out, "features": n})
            except Exception as exc:  # 空要素类等
                results.append({"class": name, "error": str(exc)})
    finally:
        con.close()
    return results
