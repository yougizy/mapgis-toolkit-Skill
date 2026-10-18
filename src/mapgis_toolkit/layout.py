"""MapGIS 10 地图文档(.mapx)版面元素。

元素类型(逆向自官方样本 ``CoomMap/湖北省行政区划图.mapx``):

=====================  ====================================================
type                  用途
=====================  ====================================================
PolygonElement        图廓 / 色块 / 图例框(矩形)
MapElement            地图框(``MapGuid`` 关联地图节点,``LogicRect`` 页面 mm,
                      ``viewRect`` 地理范围)
TextElement           文字(图名、比例尺、审图号、邻省名)
NorthArrowElement     指北针(符号数据直接沿用官方样本)
=====================  ====================================================

版面坐标单位是毫米,原点在页面左下角。
"""

from __future__ import annotations

import os
import re
from typing import Optional, Sequence, Tuple

from . import mapx as _mapx

SYSLIB = "9cbd5f3b-3d69-46aa-8a6d-af8d0f9f621b"

_TEMPLATE_CACHE: dict = {}


def _template(kind: str) -> str:
    if kind in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[kind]
    text = _mapx._load(_mapx.SAMPLE_POLY)
    m = re.search(r'<element\b[^>]*type="%s"' % kind, text)
    if not m:
        raise _mapx.MapxError("样本里没有版面元素类型: %s" % kind)
    blk = _mapx._block(text, m.start(), tag="element")
    _TEMPLATE_CACHE[kind] = blk
    return blk


def _indent(xml: str, n: int = 4) -> str:
    pad = "\t" * n
    return "\n".join(pad + ln.strip() if ln.strip() else ln for ln in xml.split("\n"))


def polygon_element(x0: float, y0: float, x1: float, y1: float,
                    fillclr: int = 9, outpenw: float = 0.4,
                    outclr: str = "0;0;0") -> str:
    """矩形图廓 / 色块 / 图例框。"""
    x = _template("PolygonElement")
    dots = "".join(
        '\t\t\t\t\t\t\t\t<dot x="%s" y="%s"></dot>\n' % (round(px, 6), round(py, 6))
        for px, py in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)))
    x = re.sub(r"<dots>.*?</dots>", "<dots>\n" + dots + "\t\t\t\t\t\t\t</dots>",
               x, count=1, flags=re.S)
    x = re.sub(r'(<regInfo\b[^>]*?\bfillclr=")[^"]*(")',
               lambda m: m.group(1) + str(fillclr) + m.group(2), x, count=1)
    x = re.sub(r'(<regInfo\b[^>]*?\boutpenw=")[^"]*(")',
               lambda m: m.group(1) + str(outpenw) + m.group(2), x, count=1)
    x = re.sub(r'(<line\b[^>]*?\boutpenw=")[^"]*(")',
               lambda m: m.group(1) + "%s;%s;%s" % (outpenw, outpenw, outpenw)
               + m.group(2), x, count=1)
    x = re.sub(r'(<line\b[^>]*?\boutclr=")[^"]*(")',
               lambda m: m.group(1) + outclr + m.group(2), x, count=1)
    return _indent(x, 4)


def map_element(map_guid: str, map_name: str,
                logic_rect: Sequence[float],
                view_rect: Sequence[float]) -> str:
    """地图框:``logic_rect`` 为页面 mm 坐标,``view_rect`` 为地理范围。"""
    x0, y0, x1, y1 = logic_rect
    vx0, vy0, vx1, vy1 = view_rect
    x = _template("MapElement")
    x = re.sub(r'MapName="[^"]*"', 'MapName="%s"' % map_name, x, count=1)
    x = re.sub(r'MapGuid="[^"]*"', 'MapGuid="%s"' % map_guid, x, count=1)
    x = re.sub(
        r"<MapElementCustiomViewExtent>.*?</MapElementCustiomViewExtent>",
        "<MapElementCustiomViewExtent>\n"
        "\t\t\t\t\t\t<xmin>%s</xmin>\n\t\t\t\t\t\t<ymin>%s</ymin>\n"
        "\t\t\t\t\t\t<xmax>%s</xmax>\n\t\t\t\t\t\t<ymax>%s</ymax>\n"
        "\t\t\t\t\t</MapElementCustiomViewExtent>" % (vx0, vy0, vx1, vy1),
        x, count=1, flags=re.S)
    x = re.sub(r'<LogicRect[^>]*></LogicRect>',
               '<LogicRect xmin="%s" ymin="%s" xmax="%s" ymax="%s"></LogicRect>'
               % (round(x0, 6), round(y0, 6), round(x1, 6), round(y1, 6)),
               x, count=1)
    x = re.sub(r'<viewRect[^>]*></viewRect>',
               '<viewRect xmin="%s" ymin="%s" xmax="%s" ymax="%s"></viewRect>'
               % (vx0, vy0, vx1, vy1), x, count=1)
    return _indent(x, 4)


_TEXT_TEMPLATE = u'''<element type="TextElement" class="CreateGElement@GisCartoPrj.dll" bFixAspect="1" bCanScale="1" bCanRotate="1" sysLibGuid="%(syslib)s" name="TextElement" desc="">
\t<DecorationInfo Origin.x="%(x)s" Origin.y="%(y)s" angle="0." name="TextElement" alias="" desc="">
\t\t<content>
\t\t\t<text>%(text)s</text>
\t\t</content>
\t\t<param>
\t\t\t<info height="%(h)s" width="%(w)s" space="%(space)s" fontang="0" strang="0" ifnt="%(ifnt)s" chnt="0" ifnx="0" hvpl="0" iclr="%(color)s" ovprnt="0" fillflg="0" backexp="0" backclr="0" offsetx="0" offsety="0"></info>
\t\t\t<space>%(space)s</space>
\t\t\t<align>%(align)s</align>
\t\t</param>
\t</DecorationInfo>
\t<Extend></Extend>
</element>'''


def text_element(text: str, x: float, y: float, height: float = 4.0,
                 color: int = 1, align: int = 0, space: int = 0,
                 ifnt: int = 1) -> str:
    """文字元素;``align`` 0 左 / 1 居中 / 2 右(以 MapGIS 实际表现为准)。"""
    return _indent(_TEXT_TEMPLATE % {
        "syslib": SYSLIB, "x": round(x, 6), "y": round(y, 6), "text": text,
        "h": height, "w": height, "color": color, "align": align,
        "space": space, "ifnt": ifnt}, 4)


def north_arrow(x: float, y: float, height: float = 8.0, width: float = 7.0,
                angle: float = 0.0) -> str:
    """指北针(符号数据沿用官方样本)。"""
    x0 = _template("NorthArrowElement")
    x0 = re.sub(r'(<DecorationInfo\b[^>]*?\bOrigin\.x=")[^"]*(")',
                lambda m: m.group(1) + str(round(x, 6)) + m.group(2), x0, count=1)
    x0 = re.sub(r'(<DecorationInfo\b[^>]*?\bOrigin\.y=")[^"]*(")',
                lambda m: m.group(1) + str(round(y, 6)) + m.group(2), x0, count=1)
    x0 = re.sub(r'(<DecorationInfo\b[^>]*?\bangle=")[^"]*(")',
                lambda m: m.group(1) + str(angle) + m.group(2), x0, count=1)
    x0 = re.sub(r"<height>[^<]*</height>", "<height>%s</height>" % height, x0, count=1)
    x0 = re.sub(r"<width>[^<]*</width>", "<width>%s</width>" % width, x0, count=1)
    return _indent(x0, 4)


def layout(page_w: float, page_h: float, elements_xml: str) -> str:
    """组装 layout 节点。"""
    return (u'\t\t\t<layout class="CreateLayOut@GisCartoPrj.dll">\n'
            u"\t\t\t\t<height>%s</height>\n"
            u"\t\t\t\t<width>%s</width>\n"
            u"\t\t\t\t<elements>\n%s\n\t\t\t\t</elements>\n"
            u"\t\t\t\t<bookMarks></bookMarks>\n"
            u'\t\t\t\t<Extend>\n\t\t\t\t\t<AdaptionToElement>False</AdaptionToElement>\n'
            u"\t\t\t\t</Extend>\n"
            u"\t\t\t</layout>" % (page_h, page_w, elements_xml))
