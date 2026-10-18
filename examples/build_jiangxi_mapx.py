# -*- coding: utf-8 -*-
"""复刻「江西省地图(政区版)」参考图,生成 MapGIS .mapx。

依赖:
    - HDB 库:江西省地图_制图3.hdb(11 市面 + 河流 + 湖泊 + 界线 + 注记点)
    - MapGIS 安装目录下的 .mapx 图层模板(MAPGIS_HOME)

用法:
    python examples/build_jiangxi_mapx.py [输出.mapx]
"""
from __future__ import annotations

import os
import sys

from mapgis_toolkit import colors, layout, mapx

DBNAME = u"江西省地图_制图3"
OUT = os.environ.get("JIANGXI_MAPX_OUT", u"江西省地图_政区版.mapx")

VIEW = (113.45, 24.35, 118.60, 30.20)
PAGE_W, PAGE_H = 210.0, 297.0
FRAME = (10.0, 20.0, 200.0, 278.0)
MAP_RECT = (14.0, 30.0, 196.0, 270.0)

# 与 colors.REFERENCE_ZONE_RGB 的键一致
ZONE_ORDER = [u"南昌市", u"九江市", u"景德镇市", u"上饶市", u"鹰潭市",
              u"新余市", u"萍乡市", u"宜春市", u"抚州市", u"吉安市", u"赣州市"]

BLUE_LINE = u"9;9;9"
RED = 6


def url(cls: str) -> str:
    return u"gdbp://MapGISLocalPlus/%s/sfcls/%s" % (DBNAME, cls)


def to_page(lon: float, lat: float):
    x0, y0, x1, y1 = MAP_RECT
    vx0, vy0, vx1, vy1 = VIEW
    px = x0 + (lon - vx0) / (vx1 - vx0) * (x1 - x0)
    py = y1 - (lat - vy0) / (vy1 - vy0) * (y1 - y0)
    return px, py


def build_layers(palette=None) -> str:
    tpl_poly = mapx.get_layer_template(mapx.SAMPLE_POLY, u"湖北省边界")
    tpl_line = mapx.get_layer_template(mapx.SAMPLE_LINE, u"湖北省公路")
    tpl_point = mapx.get_layer_template(mapx.SAMPLE_LINE, u"湖北省市驻地")

    idx_map = colors.resolve_zone_indices(palette)
    layers = []

    # 1) 11 个设区市面(底)
    for city in ZONE_ORDER:
        short = city.replace(u"市", u"")
        layers.append(mapx.make_layer(
            tpl_poly, u"设区市_%s" % short, url(u"设区市_%s" % short),
            fill={"fillclr": idx_map[city], "outpenw": 0.15, "patclr": 3},
            label_expr=u"NAME", label_visible=True,
            label_size=10.0, label_color=RED))

    # 2) 湖泊
    layers.append(mapx.make_layer(
        tpl_poly, u"湖泊水库", url(u"湖泊水库"),
        fill={"fillclr": 9, "outpenw": 0.1, "patclr": 9}))

    # 3) 河流
    layers.append(mapx.make_layer(
        tpl_line, u"四级河流", url(u"四级河流"),
        line={"outclr": BLUE_LINE, "outpenw": u"0.2;0.2;0.2"}))
    layers.append(mapx.make_layer(
        tpl_line, u"三级河流", url(u"三级河流"),
        line={"outclr": BLUE_LINE, "outpenw": u"0.35;0.35;0.35"}))
    layers.append(mapx.make_layer(
        tpl_line, u"长江", url(u"长江"),
        line={"outclr": BLUE_LINE, "outpenw": u"0.9;0.9;0.9"}))

    # 4) 界线
    layers.append(mapx.make_layer(
        tpl_line, u"设区市界", url(u"设区市界"),
        line={"outclr": u"3;3;3", "outpenw": u"0.25;0.25;0.25"}))
    layers.append(mapx.make_layer(
        tpl_line, u"省界", url(u"省域"),
        line={"outclr": u"3;3;3", "outpenw": u"0.8;0.8;0.8"}))

    # 5) 注记点 / 驻地 / 省会(顶)
    layers.append(mapx.make_layer(
        tpl_point, u"河流注记点", url(u"河流注记点"),
        point={"fillclr": 9, "scale": u"0.6;0.6;0.6"},
        label_expr=u"NAME", label_visible=True,
        label_size=6.0, label_color=9))

    layers.append(mapx.make_layer(
        tpl_point, u"市驻地", url(u"市驻地"),
        point={"fillclr": RED, "scale": u"1.2;1.2;1.2"}))

    layers.append(mapx.make_layer(
        tpl_point, u"省会", url(u"省会"),
        point={"fillclr": RED, "scale": u"2.0;2.0;2.0"},
        label_expr=u"NAME", label_visible=True,
        label_size=12.0, label_color=RED))

    return "\n".join(layers)


def build_layout() -> str:
    els = []

    # 图廓
    els.append(layout.polygon_element(*FRAME, fillclr=9, outpenw=0.7,
                                      outclr="0;0;0"))
    els.append(layout.polygon_element(12.0, 22.0, 198.0, 276.0,
                                      fillclr=9, outpenw=0.2, outclr="0;0;0"))

    # 标题 / 比例尺
    els.append(layout.text_element(u"江西省地图(政区版)", 16.0, 285.0,
                                   height=8.0, color=RED))
    els.append(layout.text_element(u"比例尺:1:2350000", 150.0, 285.0,
                                   height=4.0, color=RED))

    # 邻省
    for txt, lon, lat in (
            (u"湖 北 省", 115.2, 29.95), (u"安 徽 省", 117.5, 29.95),
            (u"浙 江 省", 118.35, 28.75), (u"福 建 省", 118.3, 26.3),
            (u"广 东 省", 115.5, 24.55), (u"湖 南 省", 113.75, 27.6)):
        px, py = to_page(lon, lat)
        els.append(layout.text_element(txt, px - 12, py - 2, height=4.5, color=RED))

    # 图例
    lx0, ly0, lx1, ly1 = 158.0, 34.0, 196.0, 64.0
    els.append(layout.polygon_element(lx0, ly0, lx1, ly1, fillclr=9,
                                      outpenw=0.25, outclr="0;0;0"))
    els.append(layout.text_element(u"图  例", lx0 + 14, ly1 - 5, height=4.0,
                                   color=RED))
    legend = [
        (u"省级行政中心", RED, 1),
        (u"设区市行政中心", RED, 2),
        (u"县级行政中心", RED, 3),
        (u"河流、湖泊及水库", 9, 4),
        (u"省界", 3, 5),
        (u"设区市界", 3, 6),
        (u"县级行政界", 3, 7),
    ]
    for label, color, row in legend:
        y = ly1 - 9 - (row - 1) * 3.4
        els.append(layout.polygon_element(lx0 + 3, y - 0.6, lx0 + 10, y + 1.4,
                                          fillclr=color, outpenw=0.1))
        els.append(layout.text_element(label, lx0 + 13, y - 0.8, height=2.8,
                                       color=RED))
    els.append(layout.text_element(u"注:图中所有界线不作为划界依据", lx0 + 2,
                                   ly0 + 1.2, height=2.2, color=RED))

    # 底部信息
    els.append(layout.text_element(u"审图号:赣S(2026)009号", 16.0, 14.0,
                                   height=3.2, color=RED))
    els.append(layout.text_element(u"江西省自然资源厅监制   江西省国土空间调查规划研究院编制",
                                   92.0, 14.0, height=3.2, color=RED))

    # 指北针
    els.append(layout.north_arrow(188.0, 258.0, height=9.0, width=6.0))

    # 地图框
    els.append(layout.map_element(mapx.DEFAULT_GUID, u"江西省专题图",
                                  MAP_RECT, VIEW))

    return layout.layout(PAGE_W, PAGE_H, "\n".join(els))


def main() -> int:
    argv = sys.argv[1:]
    palette_path = None
    if "--palette" in argv:
        i = argv.index("--palette")
        palette_path = argv[i + 1]
        del argv[i:i + 2]
    out = argv[0] if argv else OUT

    palette = colors.load_palette(palette_path) if palette_path else None
    if palette:
        print("使用校准色表:", palette_path, "(%d 色)" % len(palette))
    else:
        print("未提供 --palette,使用内置已知索引(颜色偏深)。")
        print("校准方法:color-card → MapGIS 导出 PNG → color-probe → --palette")

    out_dir = os.path.dirname(os.path.abspath(out))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    mapx.build_mapx(out, u"江西省地图(政区版)", build_layers(palette), VIEW,
                    layout_xml=build_layout())
    print("已生成:", out)
    print("大小: %.1f KB" % (os.path.getsize(out) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
