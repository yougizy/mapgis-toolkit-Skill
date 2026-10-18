# -*- coding: utf-8 -*-
"""命令行入口。

用法::

    python -m mapgis_toolkit.cli info    <库.hdb>
    python -m mapgis_toolkit.cli inspect <库.hdb> [--json]
    python -m mapgis_toolkit.cli export  <库.hdb> <要素类> <输出.shp>
    python -m mapgis_toolkit.cli import  <库.hdb> <要素类> <输入.shp> --type Region
    python -m mapgis_toolkit.cli query   <库.hdb> <要素类> [--where 字段=值] [--limit N]
    python -m mapgis_toolkit.cli spatial <库.hdb> <要素类> --bbox xmin,ymin,xmax,ymax
    python -m mapgis_toolkit.cli stats   <库.hdb> <要素类> [--field 字段]
    python -m mapgis_toolkit.cli rename  <库.hdb> <旧名> <新名>
    python -m mapgis_toolkit.cli delete  <库.hdb> <要素类> --yes
    python -m mapgis_toolkit.cli color-card <输出.mapx> [--count 128]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from typing import List, Optional

from . import colors, hdb, layout, mapx, shp


def _open(path: str) -> sqlite3.Connection:
    if not os.path.exists(path):
        raise SystemExit("库不存在: %s" % path)
    try:
        con = sqlite3.connect(path)
        con.execute("select count(*) from mpdb_item").fetchone()
        return con
    except sqlite3.OperationalError:
        # 只读目录(如 Program Files)下的库,只能以 immutable 只读方式打开
        from pathlib import Path
        con = sqlite3.connect(Path(path).as_uri() + "?mode=ro&immutable=1", uri=True)
        return con


def _parse_where(items: Optional[List[str]]) -> dict:
    out = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit("--where 需要 字段=值 形式: %r" % item)
        k, v = item.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def cmd_info(args) -> int:
    con = _open(args.db)
    rows = hdb.list_feature_classes(con)
    print("%-4s %-14s %-8s %-8s %-8s %s" % ("id", "名称", "要素数", "srid", "subtype", "范围"))
    for r in rows:
        print("%-4d %-14s %-8s %-8s %-8s [%.4f,%.4f,%.4f,%.4f]" % (
            r["id"], r["name"], r["objcnt"], r["srid"], r["subtype"],
            r["minx"] or 0, r["miny"] or 0, r["maxx"] or 0, r["maxy"] or 0))
    print("\n共 %d 个要素类" % len(rows))
    con.close()
    return 0


def cmd_inspect(args) -> int:
    con = _open(args.db)
    report = hdb.inspect(con)
    con.close()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    print("完整性:", report["integrity"])
    for c in report["classes"]:
        print("  %-12s %-6s 要素=%-5d rtree=%-5d subtype=%-2s 几何一致=%s"
              % (c["name"], c["table"], c["count"], c["rtree"], c["subtype"],
                 "是" if c["geometry_ok"] else "否"))
    if report["problems"]:
        print("\n问题:")
        for p in report["problems"]:
            print("  -", p)
    else:
        print("\n未发现问题")
    return 0 if report["ok"] else 1


def cmd_export(args) -> int:
    con = _open(args.db)
    n = hdb.export_shp(con, args.cls, args.out)
    con.close()
    print("已导出 %s -> %s(%d 个要素)" % (args.cls, args.out, n))
    return 0


def cmd_import(args) -> int:
    kind = args.type
    shape_type, feats = shp.read_shp(args.shp)
    mapping = {"Point": shp.SHAPE_POINT, "Line": shp.SHAPE_POLYLINE,
               "Region": shp.SHAPE_POLYGON}
    if shape_type != mapping[kind]:
        raise SystemExit("shapefile 类型与 --type 不符: %s vs %s"
                         % (shp.SHAPE_NAME.get(shape_type), kind))
    con = _open(args.db)
    fields = [(f, "TEXT", 0, f) for f in (feats[0]["attrs"] if feats else {})]
    n = hdb.add_feature_class(con, args.cls, kind, feats, fields=fields,
                              srid=args.srid,
                              database_name=os.path.splitext(
                                  os.path.basename(args.db))[0])
    con.close()
    print("已导入 %s -> %s(表号 mpf%d)" % (args.shp, args.cls, n))
    return 0


def cmd_query(args) -> int:
    con = _open(args.db)
    feats = hdb.query_features(con, args.cls, _parse_where(args.where), args.limit)
    con.close()
    print(json.dumps([{"oid": f["oid"], "attrs": f["attrs"]} for f in feats],
                     ensure_ascii=False, indent=2))
    print("\n命中 %d 个要素" % len(feats))
    return 0


def cmd_spatial(args) -> int:
    bbox = [float(x) for x in args.bbox.split(",")]
    if len(bbox) != 4:
        raise SystemExit("--bbox 需要 xmin,ymin,xmax,ymax")
    con = _open(args.db)
    feats = hdb.spatial_query(con, args.cls, bbox)
    con.close()
    print(json.dumps([{"oid": f["oid"], "attrs": f["attrs"]} for f in feats],
                     ensure_ascii=False, indent=2))
    print("\n命中 %d 个要素" % len(feats))
    return 0


def cmd_stats(args) -> int:
    con = _open(args.db)
    stats = hdb.feature_stats(con, args.cls, args.field)
    con.close()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def cmd_rename(args) -> int:
    con = _open(args.db)
    hdb.rename_feature_class(con, args.old, args.new)
    con.close()
    print("已重命名: %s -> %s" % (args.old, args.new))
    return 0


def cmd_delete(args) -> int:
    if not args.yes:
        raise SystemExit("删除不可恢复,请加 --yes 确认")
    con = _open(args.db)
    hdb.delete_feature_class(con, args.cls)
    con.close()
    print("已删除要素类:", args.cls)
    return 0


def cmd_repair(args) -> int:
    con = _open(args.db)
    result = hdb.repair(con)
    con.close()
    if result["actions"]:
        for a in result["actions"]:
            print("  -", a)
    else:
        print("无需修复")
    print("共 %d 项修复" % result["count"])
    return 0


def cmd_geojson_export(args) -> int:
    from . import geojson
    con = _open(args.db)
    feats = hdb.read_features(con, args.cls)
    con.close()
    if not feats:
        raise SystemExit("要素类为空: %s" % args.cls)
    kind = feats[0]["geom_type"]
    n = geojson.write_geojson(args.out, feats, kind=kind)
    print("已导出 %s -> %s(%d 个要素, %s)" % (args.cls, args.out, n, kind))
    return 0


def cmd_geojson_import(args) -> int:
    from . import geojson
    feats = geojson.read_geojson(args.geojson)
    con = _open(args.db)
    fields = [(f, "TEXT", 0, f) for f in (feats[0]["attrs"] if feats else {})]
    n = hdb.add_feature_class(
        con, args.cls, args.type, feats, fields=fields, srid=args.srid,
        database_name=os.path.splitext(os.path.basename(args.db))[0])
    con.close()
    print("已导入 %s -> %s(表号 mpf%d, %d 个要素)"
          % (args.geojson, args.cls, n, len(feats)))
    return 0


def cmd_color_probe(args) -> int:
    from . import color_probe
    palette = color_probe.extract_palette(args.png, cols=args.cols, rows=args.rows)
    color_probe.save_palette(palette, args.out)
    print("已提取 %d 个色块 -> %s" % (len(palette), args.out))
    for idx in sorted(palette)[:8]:
        print("   %3d: %s" % (idx, palette[idx]))
    return 0


def cmd_annotations_list(args) -> int:
    from . import annotation
    con = _open(args.db)
    rows = annotation.list_annotation_classes(con)
    con.close()
    if not rows:
        print("无注记类")
        return 0
    for r in rows:
        print("%-4s %-14s %-10s %s 条" % (r["id"], r["name"],
                                          r["physical_name"], r["objcnt"]))
    return 0


def cmd_annotations_read(args) -> int:
    from . import annotation
    con = _open(args.db)
    items = annotation.read_annotations(con, args.name)
    con.close()
    print(json.dumps(items, ensure_ascii=False, indent=2))
    return 0


def cmd_3d_info(args) -> int:
    from . import three_d
    con = _open(args.db)
    row = con.execute("select physical_name from mpdb_item where name=?",
                      (args.cls,)).fetchone()
    if not row:
        con.close()
        raise SystemExit("要素类不存在: %s" % args.cls)
    rows = con.execute('select mpoid, mptype, mpshape from "%s" limit 5' % row[0]).fetchall()
    con.close()
    if not rows:
        raise SystemExit("要素类为空: %s" % args.cls)
    items = []
    for oid, mptype, blob in rows:
        try:
            parts = three_d.decode_shape3d(bytes(blob))
            items.append({"oid": oid, "mptype": mptype, "parts": len(parts),
                          "points": sum(len(p) for p in parts),
                          "bbox3d": three_d.bbox3d(parts) if parts else None})
        except Exception as exc:
            items.append({"oid": oid, "mptype": mptype, "error": str(exc)})
    print(json.dumps({"class": args.cls, "features": len(items),
                      "items": items}, ensure_ascii=False, indent=2))
    return 0


def cmd_topology(args) -> int:
    from . import topology
    con = _open(args.db)
    feats = hdb.read_features(con, args.cls)
    con.close()
    if not feats:
        raise SystemExit("要素类为空: %s" % args.cls)
    report = topology.run_all(feats, feats[0]["geom_type"])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


def cmd_raster_resample(args) -> int:
    from . import raster
    result = raster.resample(args.src, args.dst, args.scale)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_raster_mosaic(args) -> int:
    from . import raster
    result = raster.mosaic(args.inputs, args.dst)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_raster_calc(args) -> int:
    from . import raster
    result = raster.calculator(args.expr, args.dst, args.bands, args.ref)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_raster_info(args) -> int:
    from . import raster
    info = raster.info(args.tif)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def cmd_raster_stats(args) -> int:
    from . import raster
    print(json.dumps(raster.stats(args.tif, args.band), ensure_ascii=False, indent=2))
    return 0


def cmd_net_summary(args) -> int:
    from . import network
    con = _open(args.db)
    feats = hdb.read_features(con, args.cls)
    con.close()
    print(json.dumps(network.summary(feats), ensure_ascii=False, indent=2))
    return 0


def cmd_batch_import(args) -> int:
    from . import batch
    results = batch.convert_shp_dir_to_hdb(args.db, args.dir, args.srid, args.recursive)
    ok = [r for r in results if "error" not in r]
    for r in results:
        if "error" in r:
            print("  !! %s: %s" % (r["file"], r["error"]))
        else:
            print("  %-20s -> %-12s %d 要素"
                  % (os.path.basename(r["file"]), r["class"], r["features"]))
    print("\n成功 %d / 共 %d" % (len(ok), len(results)))
    return 0


def cmd_batch_export(args) -> int:
    from . import batch
    results = batch.convert_hdb_to_shp_dir(args.db, args.dir)
    for r in results:
        if "error" in r:
            print("  !! %s: %s" % (r["class"], r["error"]))
        else:
            print("  %-12s -> %-24s %d 要素"
                  % (r["class"], os.path.basename(r["file"]), r["features"]))
    print("\n共 %d 个要素类" % len(results))
    return 0


def cmd_styles_export(args) -> int:
    from . import style
    with open(args.mapx, "rb") as f:
        text = f.read().decode("gb2312", "replace")
    styles = style.styles_from_mapx(text)
    style.save_styles(styles, args.out)
    print("已提取 %d 个图层样式 -> %s" % (len(styles), args.out))
    for s in styles[:6]:
        print("   %-14s gt=%s" % (s["name"], s["geometry_type"]))
    return 0


def cmd_color_card(args) -> int:
    els = [layout.text_element("MapGIS 颜色库索引色卡 0-%d" % (args.count - 1),
                               8.0, 288.0, height=6.0, color=0)]
    cols = 16
    rows = (args.count + cols - 1) // cols
    cw, ch = 12.6, 33.0
    for i in range(args.count):
        r, c = divmod(i, cols)
        x = 4.0 + c * cw
        y = 14.0 + (rows - 1 - r) * ch
        els.append(layout.polygon_element(x, y + 9, x + cw - 2.0, y + ch - 2,
                                          fillclr=i, outpenw=0.2))
        els.append(layout.text_element(str(i), x + 0.8, y + 1.5, height=3.6, color=0))
    mapx.build_mapx(args.out, "索引色卡", "", (0.0, 0.0, 1.0, 1.0),
                    layout_xml=layout.layout(210.0, 297.0, "\n".join(els)))
    print("已生成色卡: %s(%d 个色块)" % (args.out, args.count))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mapgis-toolkit-Skill",
                                description="MapGIS 10 HDB / .mapx 工具集")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("info", help="列出要素类")
    s.add_argument("db")
    s.set_defaults(func=cmd_info)

    s = sub.add_parser("inspect", help="库体检")
    s.add_argument("db")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_inspect)

    s = sub.add_parser("export", help="HDB 要素类 -> shapefile")
    s.add_argument("db")
    s.add_argument("cls")
    s.add_argument("out")
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("import", help="shapefile -> HDB 要素类")
    s.add_argument("db")
    s.add_argument("cls")
    s.add_argument("shp")
    s.add_argument("--type", choices=["Point", "Line", "Region"], required=True)
    s.add_argument("--srid", type=int, default=8)
    s.set_defaults(func=cmd_import)

    s = sub.add_parser("query", help="属性查询")
    s.add_argument("db")
    s.add_argument("cls")
    s.add_argument("--where", action="append", metavar="字段=值")
    s.add_argument("--limit", type=int)
    s.set_defaults(func=cmd_query)

    s = sub.add_parser("spatial", help="空间查询(bbox)")
    s.add_argument("db")
    s.add_argument("cls")
    s.add_argument("--bbox", required=True, help="xmin,ymin,xmax,ymax")
    s.set_defaults(func=cmd_spatial)

    s = sub.add_parser("stats", help="统计")
    s.add_argument("db")
    s.add_argument("cls")
    s.add_argument("--field")
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser("rename", help="重命名要素类")
    s.add_argument("db")
    s.add_argument("old")
    s.add_argument("new")
    s.set_defaults(func=cmd_rename)

    s = sub.add_parser("delete", help="删除要素类")
    s.add_argument("db")
    s.add_argument("cls")
    s.add_argument("--yes", action="store_true")
    s.set_defaults(func=cmd_delete)

    s = sub.add_parser("repair", help="修复库(objcnt/subtype/rtree/符号表)")
    s.add_argument("db")
    s.set_defaults(func=cmd_repair)

    s = sub.add_parser("geojson-export", help="HDB 要素类 -> GeoJSON")
    s.add_argument("db")
    s.add_argument("cls")
    s.add_argument("out")
    s.set_defaults(func=cmd_geojson_export)

    s = sub.add_parser("geojson-import", help="GeoJSON -> HDB 要素类")
    s.add_argument("db")
    s.add_argument("cls")
    s.add_argument("geojson")
    s.add_argument("--type", choices=["Point", "Line", "Region"], required=True)
    s.add_argument("--srid", type=int, default=8)
    s.set_defaults(func=cmd_geojson_import)

    s = sub.add_parser("color-probe", help="从色卡 PNG 提取 索引->RGB")
    s.add_argument("png")
    s.add_argument("--out", default="palette.json")
    s.add_argument("--cols", type=int, default=16)
    s.add_argument("--rows", type=int, default=8)
    s.set_defaults(func=cmd_color_probe)

    s = sub.add_parser("annotations-list", help="列出注记类")
    s.add_argument("db")
    s.set_defaults(func=cmd_annotations_list)

    s = sub.add_parser("annotations-read", help="读取注记内容")
    s.add_argument("db")
    s.add_argument("name")
    s.set_defaults(func=cmd_annotations_read)

    s = sub.add_parser("3d-info", help="三维要素概况")
    s.add_argument("db")
    s.add_argument("cls")
    s.set_defaults(func=cmd_3d_info)

    s = sub.add_parser("topology", help="拓扑/几何质量检查")
    s.add_argument("db")
    s.add_argument("cls")
    s.set_defaults(func=cmd_topology)

    s = sub.add_parser("raster-resample", help="栅格重采样")
    s.add_argument("src")
    s.add_argument("dst")
    s.add_argument("--scale", type=float, default=1.0)
    s.set_defaults(func=cmd_raster_resample)

    s = sub.add_parser("raster-mosaic", help="栅格镶嵌")
    s.add_argument("dst")
    s.add_argument("inputs", nargs="+")
    s.set_defaults(func=cmd_raster_mosaic)

    s = sub.add_parser("raster-calc", help="栅格计算器")
    s.add_argument("ref")
    s.add_argument("dst")
    s.add_argument("--expr", required=True, help="如 b1-b2")
    s.add_argument("--bands", nargs="+", required=True)
    s.set_defaults(func=cmd_raster_calc)

    s = sub.add_parser("raster-info", help="栅格元数据")
    s.add_argument("tif")
    s.set_defaults(func=cmd_raster_info)

    s = sub.add_parser("raster-stats", help="栅格波段统计")
    s.add_argument("tif")
    s.add_argument("--band", type=int, default=1)
    s.set_defaults(func=cmd_raster_stats)

    s = sub.add_parser("net-summary", help="线要素网络概况")
    s.add_argument("db")
    s.add_argument("cls")
    s.set_defaults(func=cmd_net_summary)

    s = sub.add_parser("batch-import", help="目录下 shapefile 批量导入 HDB")
    s.add_argument("db")
    s.add_argument("dir")
    s.add_argument("--srid", type=int, default=8)
    s.add_argument("--recursive", action="store_true")
    s.set_defaults(func=cmd_batch_import)

    s = sub.add_parser("batch-export", help="HDB 全量导出 shapefile")
    s.add_argument("db")
    s.add_argument("dir")
    s.set_defaults(func=cmd_batch_export)

    s = sub.add_parser("styles-export", help="从 .mapx 提取图层样式为 JSON")
    s.add_argument("mapx")
    s.add_argument("out")
    s.set_defaults(func=cmd_styles_export)

    s = sub.add_parser("color-card", help="生成颜色库索引色卡")
    s.add_argument("out")
    s.add_argument("--count", type=int, default=128)
    s.set_defaults(func=cmd_color_card)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
