"""MCP server —— 把 mapgis-toolkit 暴露给支持 MCP 的 AI 客户端。

启动::

    python -m mapgis_toolkit.mcp_server

配置示例(Claude Desktop / 其它 MCP 客户端)::

    {
      "mcpServers": {
        "mapgis-toolkit": {
          "command": "python",
          "args": ["-m", "mapgis_toolkit.mcp_server"],
          "env": {"PYTHONPATH": "<项目路径>/src"}
        }
      }
    }

说明:MapGIS 的 `.mapx` 颜色只能填颜色库索引,工具里已内置这一约束与已知索引表。
"""

from __future__ import annotations

import os
import sqlite3
from typing import List, Optional

try:
    # mcp 2.x:FastMCP 改名为 MCPServer
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    try:
        from mcp.server.fastmcp import FastMCP as _Server
    except ImportError as exc:  # pragma: no cover
        raise ImportError("需要安装 mcp:pip install mcp") from exc

from . import colors, hdb, layout, mapx, shp

mcp = _Server("mapgis-toolkit-Skill")


def _open(db_path: str) -> sqlite3.Connection:
    if not os.path.exists(db_path):
        raise FileNotFoundError("库不存在: %s" % db_path)
    return sqlite3.connect(db_path)


# ---------------------------------------------------------------------------
# HDB
# ---------------------------------------------------------------------------

@mcp.tool()
def hdb_list_classes(db_path: str) -> List[dict]:
    """列出 MapGIS 库(.hdb)中的要素类:id、名称、要素数、srid、范围。"""
    con = _open(db_path)
    try:
        return hdb.list_feature_classes(con)
    finally:
        con.close()


@mcp.tool()
def hdb_inspect(db_path: str) -> dict:
    """体检 MapGIS 库:完整性、要素表/空间索引/符号表引用、subtype 与几何类型一致性。"""
    con = _open(db_path)
    try:
        return hdb.inspect(con)
    finally:
        con.close()


@mcp.tool()
def hdb_export_shp(db_path: str, class_name: str, out_shp: str) -> dict:
    """把要素类导出为 ESRI Shapefile。"""
    con = _open(db_path)
    try:
        n = hdb.export_shp(con, class_name, out_shp)
        return {"ok": True, "features": n, "out": out_shp}
    finally:
        con.close()


@mcp.tool()
def hdb_import_shp(db_path: str, class_name: str, shp_path: str,
                   geom_type: str, srid: int = 8) -> dict:
    """把 Shapefile 导入为新的要素类。geom_type: Point / Line / Region。"""
    shape_type, feats = shp.read_shp(shp_path)
    expect = {"Point": shp.SHAPE_POINT, "Line": shp.SHAPE_POLYLINE,
              "Region": shp.SHAPE_POLYGON}
    if geom_type not in expect:
        raise ValueError("geom_type 必须是 Point/Line/Region")
    if shape_type != expect[geom_type]:
        raise ValueError("shapefile 类型为 %s,与 geom_type=%s 不符"
                         % (shp.SHAPE_NAME.get(shape_type), geom_type))
    con = _open(db_path)
    try:
        fields = [(f, "TEXT", 0, f) for f in (feats[0]["attrs"] if feats else {})]
        n = hdb.add_feature_class(
            con, class_name, geom_type, feats, fields=fields, srid=srid,
            database_name=os.path.splitext(os.path.basename(db_path))[0])
        return {"ok": True, "table": "mpf%d" % n, "features": len(feats)}
    finally:
        con.close()


# ---------------------------------------------------------------------------
# .mapx
# ---------------------------------------------------------------------------

@mcp.tool()
def mapx_build(out_path: str, title: str, layers: List[dict],
               view_extent: List[float], page: Optional[List[float]] = None,
               frame: Optional[List[float]] = None,
               texts: Optional[List[dict]] = None,
               north_arrow_at: Optional[List[float]] = None) -> dict:
    """生成 MapGIS 地图文档(.mapx)。

    layers 每项::

        {"name": "设区市_南昌", "url": "gdbp://MapGISLocalPlus/库/sfcls/设区市_南昌",
         "geometry_type": "3", "fill": {"fillclr": 15},
         "label": {"expr": "NAME", "size": 11, "color": 6}}

    geometry_type: "1" 点 / "2" 线 / "3" 面。
    图层顺序:列表前面的画在下面。
    """
    tpl = {"3": mapx.get_layer_template(mapx.SAMPLE_POLY, u"湖北省边界"),
           "2": mapx.get_layer_template(mapx.SAMPLE_LINE, u"湖北省公路"),
           "1": mapx.get_layer_template(mapx.SAMPLE_LINE, u"湖北省市驻地")}
    parts = []
    for lay in layers:
        gt = str(lay.get("geometry_type", "3"))
        label = lay.get("label") or {}
        parts.append(mapx.make_layer(
            tpl[gt], lay["name"], lay["url"],
            fill=lay.get("fill"), line=lay.get("line"), point=lay.get("point"),
            label_expr=label.get("expr"), label_visible=label.get("visible", True),
            label_size=label.get("size", 10.0), label_color=label.get("color", 6),
            theme=lay.get("theme_xml")))
    layout_xml = None
    if page and frame:
        els = [layout.polygon_element(*frame)]
        guid = mapx.DEFAULT_GUID
        els.append(layout.map_element(guid, title, frame, view_extent))
        for t in (texts or []):
            els.append(layout.text_element(t["text"], t["x"], t["y"],
                                           height=t.get("height", 4.0),
                                           color=t.get("color", 6)))
        if north_arrow_at:
            els.append(layout.north_arrow(*north_arrow_at))
        layout_xml = layout.layout(page[0], page[1], "\n".join(els))
    mapx.build_mapx(out_path, title, "\n".join(parts), view_extent,
                    layout_xml=layout_xml)
    return {"ok": True, "out": out_path, "layers": len(layers)}


@mcp.tool()
def mapx_color_card(out_path: str, count: int = 128) -> dict:
    """生成 MapGIS 颜色库索引色卡(.mapx),用于把 RGB 目标色映射到索引。"""
    els = [layout.text_element("MapGIS 颜色库索引色卡 0-%d" % (count - 1),
                               8.0, 288.0, height=6.0, color=0)]
    cols = 16
    rows = (count + cols - 1) // cols
    cw, ch = 12.6, 33.0
    for i in range(count):
        r, c = divmod(i, cols)
        x = 4.0 + c * cw
        y = 14.0 + (rows - 1 - r) * ch
        els.append(layout.polygon_element(x, y + 9, x + cw - 2.0, y + ch - 2,
                                          fillclr=i, outpenw=0.2))
        els.append(layout.text_element(str(i), x + 0.8, y + 1.5, height=3.6, color=0))
    mapx.build_mapx(out_path, "索引色卡", "", (0.0, 0.0, 1.0, 1.0),
                    layout_xml=layout.layout(210.0, 297.0, "\n".join(els)))
    return {"ok": True, "out": out_path, "swatches": count}


@mcp.tool()
def hdb_query(db_path: str, class_name: str, where: Optional[dict] = None,
              limit: Optional[int] = None) -> List[dict]:
    """按属性查询要素(等值匹配;值可为列表表示 IN)。"""
    con = _open(db_path)
    try:
        feats = hdb.query_features(con, class_name, where, limit)
        return [{"oid": f["oid"], "attrs": f["attrs"]} for f in feats]
    finally:
        con.close()


@mcp.tool()
def hdb_spatial_query(db_path: str, class_name: str,
                      bbox: List[float]) -> List[dict]:
    """空间查询:返回与 bbox 相交的要素。bbox = [xmin, ymin, xmax, ymax]。"""
    con = _open(db_path)
    try:
        feats = hdb.spatial_query(con, class_name, bbox)
        return [{"oid": f["oid"], "attrs": f["attrs"]} for f in feats]
    finally:
        con.close()


@mcp.tool()
def hdb_stats(db_path: str, class_name: str,
              field: Optional[str] = None) -> dict:
    """统计:要素数、范围;指定字段时给出唯一值或数值统计。"""
    con = _open(db_path)
    try:
        return hdb.feature_stats(con, class_name, field)
    finally:
        con.close()


@mcp.tool()
def hdb_rename_class(db_path: str, old_name: str, new_name: str) -> dict:
    """重命名要素类(只改显示名)。"""
    con = _open(db_path)
    try:
        hdb.rename_feature_class(con, old_name, new_name)
        return {"ok": True, "from": old_name, "to": new_name}
    finally:
        con.close()


@mcp.tool()
def hdb_delete_class(db_path: str, class_name: str) -> dict:
    """删除要素类及其表、索引、符号表与元数据(不可恢复)。"""
    con = _open(db_path)
    try:
        hdb.delete_feature_class(con, class_name)
        return {"ok": True, "deleted": class_name}
    finally:
        con.close()


@mcp.tool()
def hdb_repair(db_path: str) -> dict:
    """修复库:重算 objcnt、纠正 subtype、重建 rtree、补缺失符号表。"""
    con = _open(db_path)
    try:
        return hdb.repair(con)
    finally:
        con.close()


@mcp.tool()
def hdb_export_geojson(db_path: str, class_name: str, out_geojson: str) -> dict:
    """把要素类导出为 GeoJSON。"""
    from . import geojson
    con = _open(db_path)
    try:
        feats = hdb.read_features(con, class_name)
    finally:
        con.close()
    if not feats:
        raise ValueError("要素类为空: %s" % class_name)
    n = geojson.write_geojson(out_geojson, feats, kind=feats[0]["geom_type"])
    return {"ok": True, "features": n, "out": out_geojson}


@mcp.tool()
def hdb_import_geojson(db_path: str, class_name: str, geojson_path: str,
                       geom_type: str, srid: int = 8) -> dict:
    """把 GeoJSON 导入为新要素类。geom_type: Point / Line / Region。"""
    from . import geojson
    feats = geojson.read_geojson(geojson_path)
    con = _open(db_path)
    try:
        fields = [(f, "TEXT", 0, f) for f in (feats[0]["attrs"] if feats else {})]
        n = hdb.add_feature_class(
            con, class_name, geom_type, feats, fields=fields, srid=srid,
            database_name=os.path.splitext(os.path.basename(db_path))[0])
        return {"ok": True, "table": "mpf%d" % n, "features": len(feats)}
    finally:
        con.close()


@mcp.tool()
def hdb_clip(db_path: str, class_name: str, geom_type: str,
             mask_class: str, out_shp: str) -> dict:
    """用库内一个面要素类裁剪另一个要素类,结果导出为 shapefile。"""
    from . import ops
    con = _open(db_path)
    try:
        feats = hdb.read_features(con, class_name)
        mask = hdb.read_features(con, mask_class)
    finally:
        con.close()
    clipped = ops.clip(feats, geom_type, mask, "Region")
    if not clipped:
        raise ValueError("裁剪结果为空")
    from . import shp as shp_mod
    shp_mod.write_shp(out_shp, shp_mod.SHAPE_BY_KIND[geom_type], clipped,
                      fields=list((clipped[0]["attrs"] or {}).keys()))
    return {"ok": True, "features": len(clipped), "out": out_shp}


@mcp.tool()
def hdb_buffer(db_path: str, class_name: str, geom_type: str,
               distance: float, out_shp: str) -> dict:
    """对要素类做缓冲,结果(面)导出为 shapefile。"""
    from . import ops
    from . import shp as shp_mod
    con = _open(db_path)
    try:
        feats = hdb.read_features(con, class_name)
    finally:
        con.close()
    buffered = ops.buffer_features(feats, geom_type, distance)
    shp_mod.write_shp(out_shp, shp_mod.SHAPE_POLYGON, buffered,
                      fields=list((buffered[0]["attrs"] or {}).keys()) if buffered else [])
    return {"ok": True, "features": len(buffered), "out": out_shp}


@mcp.tool()
def color_probe_png(png_path: str, palette_out: str,
                    cols: int = 16, rows: int = 8) -> dict:
    """从色卡 PNG 提取 索引->RGB,写出 JSON。"""
    from . import color_probe
    palette = color_probe.extract_palette(png_path, cols=cols, rows=rows)
    color_probe.save_palette(palette, palette_out)
    return {"ok": True, "swatches": len(palette), "out": palette_out}


@mcp.tool()
def mapx_batch_build(specs: List[dict]) -> dict:
    """批量生成 .mapx。specs 每项:{out, title, view_extent, layers}。"""
    from . import batch
    outs = batch.build_batch(specs)
    return {"ok": True, "count": len(outs), "outs": outs}


@mcp.tool()
def hdb_add_field(db_path: str, class_name: str, field: str,
                  sql_type: str = "TEXT", fld_type: int = 0,
                  alias: str = "") -> dict:
    """给要素类加字段。fld_type: 0 文本 / 4 整数 / 7 双精度。"""
    con = _open(db_path)
    try:
        idx = hdb.add_field(con, class_name, field, sql_type, fld_type, alias)
        return {"ok": True, "field": field, "index": idx}
    finally:
        con.close()


@mcp.tool()
def hdb_update_features(db_path: str, class_name: str,
                        updates: dict, where: Optional[dict] = None) -> dict:
    """按属性条件更新字段值,返回更新条数。"""
    con = _open(db_path)
    try:
        n = hdb.update_features(con, class_name, where, updates)
        return {"ok": True, "updated": n}
    finally:
        con.close()


@mcp.tool()
def mapx_extract_styles(mapx_path: str, out_json: str) -> dict:
    """从 .mapx 提取所有图层样式,写出 JSON。"""
    from . import style
    with open(mapx_path, "rb") as f:
        text = f.read().decode("gb2312", "replace")
    styles = style.styles_from_mapx(text)
    style.save_styles(styles, out_json)
    return {"ok": True, "layers": len(styles), "out": out_json}


@mcp.tool()
def raster_info(path: str) -> dict:
    """栅格元数据(尺寸/波段/CRS/分辨率/范围)。"""
    from . import raster
    return raster.info(path)


@mcp.tool()
def raster_stats(path: str, band: int = 1) -> dict:
    """栅格波段统计(min/max/mean/std)。"""
    from . import raster
    return raster.stats(path, band)


@mcp.tool()
def raster_clip(path: str, out_path: str,
                bbox: Optional[List[float]] = None,
                geojson_path: Optional[str] = None) -> dict:
    """裁剪栅格(bbox 或 GeoJSON 掩膜)。"""
    from . import raster
    return raster.clip(path, out_path, bbox=bbox, geojson_path=geojson_path)


@mcp.tool()
def network_summary(db_path: str, class_name: str) -> dict:
    """线要素网络概况:节点/边/连通分量/总长度。"""
    from . import network
    con = _open(db_path)
    try:
        feats = hdb.read_features(con, class_name)
    finally:
        con.close()
    return network.summary(feats)


@mcp.tool()
def batch_import_shp_dir(db_path: str, shp_dir: str, srid: int = 8,
                         recursive: bool = False) -> dict:
    """把目录下所有 shapefile 批量导入为 HDB 要素类。"""
    from . import batch
    results = batch.convert_shp_dir_to_hdb(db_path, shp_dir, srid, recursive)
    return {"ok": True, "total": len(results),
            "ok_count": sum(1 for r in results if "error" not in r),
            "results": results}


@mcp.tool()
def batch_export_shp_dir(db_path: str, out_dir: str) -> dict:
    """把 HDB 所有要素类批量导出为 shapefile。"""
    from . import batch
    results = batch.convert_hdb_to_shp_dir(db_path, out_dir)
    return {"ok": True, "total": len(results),
            "ok_count": sum(1 for r in results if "error" not in r),
            "results": results}


@mcp.tool()
def hdb_topology(db_path: str, class_name: str) -> dict:
    """要素类拓扑/几何质量检查(无效几何/重叠/缝隙/悬挂点/重复)。"""
    from . import topology
    con = _open(db_path)
    try:
        feats = hdb.read_features(con, class_name)
    finally:
        con.close()
    if not feats:
        raise ValueError("要素类为空: %s" % class_name)
    return topology.run_all(feats, feats[0]["geom_type"])


@mcp.tool()
def raster_resample(src: str, dst: str, scale: float = 1.0) -> dict:
    """栅格重采样。"""
    from . import raster
    return raster.resample(src, dst, scale)


@mcp.tool()
def raster_mosaic(paths: List[str], dst: str) -> dict:
    """栅格镶嵌(坐标系需一致)。"""
    from . import raster
    return raster.mosaic(paths, dst)


@mcp.tool()
def raster_calculator(expr: str, out_path: str, bands: List[str],
                      ref_path: str) -> dict:
    """栅格计算器:expr 中 b1/b2… 对应 bands,ref_path 提供元数据。"""
    from . import raster
    return raster.calculator(expr, out_path, bands, ref_path)


@mcp.tool()
def hdb_list_annotations(db_path: str) -> dict:
    """列出库中的注记类(acls)。"""
    from . import annotation
    con = _open(db_path)
    try:
        return {"classes": annotation.list_annotation_classes(con)}
    finally:
        con.close()


@mcp.tool()
def hdb_read_annotations(db_path: str, class_name: str) -> dict:
    """读取注记类的内容(文本/坐标/字号/颜色)。"""
    from . import annotation
    con = _open(db_path)
    try:
        items = annotation.read_annotations(con, class_name)
    finally:
        con.close()
    return {"ok": True, "count": len(items), "items": items}


@mcp.tool()
def hdb_add_annotations(db_path: str, class_name: str, items: List[dict],
                        database_name: str = "") -> dict:
    """新建注记类并写入注记。items: [{x,y,text,height,color,font,angle}]。"""
    from . import annotation
    con = _open(db_path)
    try:
        dbname = database_name or os.path.splitext(os.path.basename(db_path))[0]
        table = annotation.add_annotation_class(con, class_name, items, dbname)
        return {"ok": True, "table": table, "count": len(items)}
    finally:
        con.close()


@mcp.tool()
def hdb_read_3d(db_path: str, class_name: str, limit: int = 10) -> dict:
    """读取三维要素(mptype 8/9)的顶点。"""
    from . import three_d
    con = _open(db_path)
    table = con.execute(
        "select physical_name from mpdb_item where name=?", (class_name,)).fetchone()
    if not table:
        con.close()
        raise ValueError("要素类不存在: %s" % class_name)
    rows = con.execute('select mpoid, mptype, mpshape from "%s" limit ?' % table[0],
                       (limit,)).fetchall()
    con.close()
    out = []
    for oid, mptype, blob in rows:
        try:
            parts = three_d.decode_shape3d(bytes(blob))
        except Exception as exc:
            out.append({"oid": oid, "mptype": mptype, "error": str(exc)})
            continue
        out.append({"oid": oid, "mptype": mptype,
                    "parts": len(parts),
                    "points": sum(len(p) for p in parts),
                    "bbox3d": three_d.bbox3d(parts) if parts else None})
    return {"ok": True, "count": len(out), "items": out}


@mcp.tool()
def color_known_indices() -> dict:
    """返回已确认的 MapGIS 颜色库索引 -> RGB 对照表。"""
    return {str(k): list(v) for k, v in colors.KNOWN_INDEX_RGB.items()}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
