"""MapGIS 10 地图文档(.mapx)生成。

``.mapx`` 是 **gb2312 编码的纯 XML**,结构::

    <datacenter>
      <root ... version="MapGIS K10">
        <subnode type="Map" class="CreateMap@GisCartoPrj.dll">
          <viewExtent .../>
          <subnode type="SFeatureLayer" geometryType="1|2|3" class="CreateGLayer@GisCartoPrj.dll">
            <url>gdbp://MapGISLocalPlus/库名/sfcls/要素类名</url>
            <subnode type="SimpleTheme" class="CreateGTheme@GisCartoPrj.dll"> ... </subnode>
            <label type="SimpleLabel" ...> ... </label>
          </subnode>
          <layout class="CreateLayOut@GisCartoPrj.dll"> ... </layout>
        </subnode>
      </root>
    </datacenter>

图层绘制顺序:**写在后面的图层画在上面**。

生成策略:以 MapGIS 官方样本(CoomMap 系列)的图层节点为模板改写,
保证标签结构合法;模板缺失时由 :func:`simple_theme` 兜底生成符号节点。
"""

from __future__ import annotations

import os
import re
from typing import Optional

#: MapGIS 安装目录(可用环境变量覆盖)
MAPGIS_HOME = os.environ.get("MAPGIS_HOME", r"D:\Program Files\MapGIS 10")
_TEMPLATE_DIR = os.path.join(MAPGIS_HOME, "Program", "Config", "MapTemplates", "CoomMap")
SAMPLE_POLY = os.path.join(_TEMPLATE_DIR, u"湖北省行政区划图.mapx")
SAMPLE_LINE = os.path.join(_TEMPLATE_DIR, u"湖北省公路铁路网.mapx")

HEADER = u'<?xml version="1.0" encoding="gb2312" standalone="no" ?>\n<datacenter>\n'
FOOTER = u'\t</root>\n</datacenter>\n'

MAP_HEAD = u'''\t<root filePath="%(path)s" title="地图文档" subject="" author="" category="" keywords="" comments="" version="MapGIS K10">
\t\t<ClibDir6x></ClibDir6x>
\t\t<SlibDir6x></SlibDir6x>
\t\t<subnode name="%(title)s" mapguid="%(guid)s" LegendBoardGUID="9cbd5f3b-3d69-46aa-8a6d-af8d0f9f621b" LegendBoardID="0" type="Map" class="CreateMap@GisCartoPrj.dll">
\t\t\t<description></description>
\t\t\t<isDisplayOnLayout>1</isDisplayOnLayout>
\t\t\t<isCustomEntireExtent>0</isCustomEntireExtent>
\t\t\t<customEntireExtent xmin="0." ymin="0." xmax="0." ymax="0."></customEntireExtent>
\t\t\t<viewExtent xmin="%(xmin)s" ymin="%(ymin)s" xmax="%(xmax)s" ymax="%(ymax)s"></viewExtent>
\t\t\t<minScale>0.</minScale>
\t\t\t<maxScale>0.</maxScale>
\t\t\t<ScaleRangeMinScale>0.</ScaleRangeMinScale>
\t\t\t<ScaleRangeMaxScale>0.</ScaleRangeMaxScale>
\t\t\t<isFixedScalesDisplay>0</isFixedScalesDisplay>
\t\t\t<isProjTrans>0</isProjTrans>
\t\t\t<rotateCenter>
\t\t\t\t<X>0.</X>
\t\t\t\t<Y>0.</Y>
\t\t\t</rotateCenter>
\t\t\t<rotateAngle>0.</rotateAngle>
\t\t\t<backColor>9</backColor>
\t\t\t<backgroundImage></backgroundImage>
\t\t\t<displayHint>2</displayHint>
\t\t\t<imageLayerZoom>-1</imageLayerZoom>
\t\t\t<fixedMapScales></fixedMapScales>
'''

EMPTY_LAYOUT = u'''\t\t\t<layout class="CreateLayOut@GisCartoPrj.dll">
\t\t\t\t<height>841.000000</height>
\t\t\t\t<width>594.000000</width>
\t\t\t\t<elements></elements>
\t\t\t\t<bookMarks></bookMarks>
\t\t\t</layout>
'''

DEFAULT_GUID = "b5252cad-2281-46b6-992a-8c7be0098b34"


class MapxError(RuntimeError):
    """地图文档生成异常。"""


def _load(path: str) -> str:
    with open(path, "rb") as f:
        return f.read().decode("gb2312", "replace")


def _block(text: str, start: int, tag: str = "subnode") -> str:
    depth = 0
    i = start
    pat = re.compile(r"<(/?)%s\b" % tag)
    while True:
        m = pat.search(text, i)
        if not m:
            return text[start:]
        if m.group(1) == "":
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                j = text.find(">", m.end())
                return text[start:j + 1]
        i = m.end()


def get_layer_template(sample_path: str, layer_name: str) -> str:
    """从官方样本里取某个图层节点的完整 XML 作为模板。"""
    s = _load(sample_path)
    m = re.search(r'<subnode\s+name="%s"' % re.escape(layer_name), s)
    if not m:
        raise MapxError("样本里没有图层: %s (%s)" % (layer_name, sample_path))
    return _block(s, m.start())


def _set_first_attr(xml: str, attr: str, value: str) -> str:
    return re.sub(r'(<subnode\s+[^>]*?\b%s=")[^"]*(")' % attr,
                  lambda m: m.group(1) + value + m.group(2), xml, count=1)


# ---------------------------------------------------------------------------
# 符号节点
# ---------------------------------------------------------------------------

def simple_theme(geom_type: str, fill: Optional[dict] = None,
                 line: Optional[dict] = None,
                 point: Optional[dict] = None) -> str:
    """生成 SimpleTheme 节点。

    模板图层若没有符号节点,必须补一个,否则 MapGIS 会渲染成黑色/不显示。
    ``geom_type``: ``"1"`` 点 / ``"2"`` 线 / ``"3"`` 面。
    """
    if geom_type == "1":
        p = point or {}
        geo = (u'<pntInfo lib="0" id="%s" fillclr="%s" transparent="0" '
               u'scale="%s" angle="0;0;0" isFrontDis="1"></pntInfo>'
               % (p.get("id", 1), p.get("fillclr", 1), p.get("scale", "1;1;1")))
    elif geom_type == "2":
        ln = line or {}
        geo = (u'<linInfo lib="0" id="1" ovprnt="0" outpenw="%s" outclr="%s" '
               u'headtype="0" jointype="0" adjustflg="0" makemethod="0" '
               u'xscale="10." yscale="10."></linInfo>'
               % (ln.get("outpenw", "0.3;0.3;0.3"), ln.get("outclr", "9;4;3")))
    else:
        f = fill or {}
        geo = (u'<regInfo lib="0" id="0" ovprnt="0" fillmode="0" fillclr="%s" '
               u'endclr="0" pathei="5." patwid="5." ang="0." patclr="%s" '
               u'outpenw="%s" fullpatflg="1"></regInfo>'
               % (f.get("fillclr", 1), f.get("patclr", 3), f.get("outpenw", 0.3)))
    return (u'<subnode name="统一专题图" type="SimpleTheme" '
            u'class="CreateGTheme@GisCartoPrj.dll">\n'
            u'\t<state>VISIBLE</state>\n'
            u'\t<geomInfoType>%s</geomInfoType>\n'
            u'\t<minScale>0.</minScale>\n'
            u'\t<maxScale>0.</maxScale>\n'
            u'\t<ScaleRange MinScale="0." MaxScale="0."></ScaleRange>\n'
            u'\t<geoInfo>\n\t\t%s\n\t</geoInfo>\n'
            u'</subnode>' % (geom_type, geo))


# ---------------------------------------------------------------------------
# 图层
# ---------------------------------------------------------------------------

def make_layer(template: str, name: str, url: str, fill: Optional[dict] = None,
               line: Optional[dict] = None, point: Optional[dict] = None,
               label_expr: Optional[str] = None, label_visible: bool = False,
               label_size: float = 10.0, label_color: int = 0,
               theme: Optional[str] = None) -> str:
    """改写模板图层节点:名称、数据源、符号、标注(可选替换专题图)。"""
    x = _set_first_attr(template, "name", name)
    x = re.sub(r"<url>.*?</url>", u"<url>%s</url>" % url, x, count=1, flags=re.S)

    # 专题图 / 符号节点
    tm = re.search(r'<subnode\s+name="[^"]*"\s+type="(?:SimpleTheme|MultiClassTheme|UniqueTheme)"',
                   x)
    if tm is None and theme is None:
        gt = re.search(r'geometryType="(\d)"', x)
        theme = simple_theme(gt.group(1) if gt else "3", fill, line, point)
    if tm:
        blk = _block(x, tm.start())
        if theme is not None:
            x = x.replace(blk, theme)

    if fill:
        x = re.sub(r'(<regInfo\b[^>]*?\bfillclr=")[^"]*(")',
                   lambda m: m.group(1) + str(fill.get("fillclr", 1)) + m.group(2),
                   x, count=1)
        if "outpenw" in fill:
            x = re.sub(r'(<regInfo\b[^>]*?\boutpenw=")[^"]*(")',
                       lambda m: m.group(1) + str(fill["outpenw"]) + m.group(2),
                       x, count=1)
        if "patclr" in fill:
            x = re.sub(r'(<regInfo\b[^>]*?\bpatclr=")[^"]*(")',
                       lambda m: m.group(1) + str(fill["patclr"]) + m.group(2),
                       x, count=1)
    if line:
        m2 = re.search(r"<linInfo\b[^>]*>", x)
        if m2:
            tag = m2.group(0)
            nt = tag
            if "outclr" in line:
                nt = re.sub(r'outclr="[^"]*"', 'outclr="%s"' % line["outclr"], nt, count=1)
            if "outpenw" in line:
                nt = re.sub(r'outpenw="[^"]*"', 'outpenw="%s"' % line["outpenw"], nt, count=1)
            x = x.replace(tag, nt, 1)
    if point:
        m3 = re.search(r"<pntInfo\b[^>]*>", x)
        if m3:
            tag = m3.group(0)
            nt = tag
            if "fillclr" in point:
                nt = re.sub(r'fillclr="[^"]*"', 'fillclr="%s"' % point["fillclr"], nt, count=1)
            if "scale" in point:
                nt = re.sub(r'scale="[^"]*"', 'scale="%s"' % point["scale"], nt, count=1)
            if "id" in point:
                nt = re.sub(r'\bid="[^"]*"', 'id="%s"' % point["id"], nt, count=1)
            x = x.replace(tag, nt, 1)

    if label_expr is not None:
        x = re.sub(r'(<label\b[^>]*>.*?<state>)[^<]*(</state>)',
                   lambda m: m.group(1) + ("VISIBLE" if label_visible else "UNVISIBLE")
                   + m.group(2), x, count=1, flags=re.S)
        if "<labelExpression>" in x:
            x = re.sub(r"<labelExpression>.*?</labelExpression>",
                       u"<labelExpression>%s</labelExpression>" % label_expr,
                       x, count=1, flags=re.S)
        elif "<labelExpression/>" in x:
            x = x.replace("<labelExpression/>",
                          u"<labelExpression>%s</labelExpression>" % label_expr, 1)
        for attr, value in (("height", label_size), ("width", label_size),
                            ("iclr", label_color)):
            x = re.sub(r'(<label\b[^>]*>.*?<annInfo\b[^>]*?\b%s=")[^"]*(")' % attr,
                       lambda m, v=value: m.group(1) + str(v) + m.group(2),
                       x, count=1, flags=re.S)

    return "\n".join("\t\t\t\t" + ln.strip() if ln.strip() else ln
                     for ln in x.split("\n"))


# ---------------------------------------------------------------------------
# 文档
# ---------------------------------------------------------------------------

def build_mapx(out_path: str, title: str, layers_xml: str,
               view_extent, layout_xml: Optional[str] = None,
               guid: str = DEFAULT_GUID) -> str:
    """组装并写出 .mapx(gb2312)。"""
    x0, y0, x1, y1 = view_extent
    head = MAP_HEAD % {
        "path": out_path.replace("/", "\\"), "title": title, "guid": guid,
        "xmin": "%.6f" % x0, "ymin": "%.6f" % y0,
        "xmax": "%.6f" % x1, "ymax": "%.6f" % y1,
    }
    lay = layout_xml if layout_xml is not None else EMPTY_LAYOUT
    xml = HEADER + head + layers_xml + "\n" + lay + "\n\t\t</subnode>\n" + FOOTER
    with open(out_path, "wb") as f:
        f.write(xml.encode("gb2312", "replace"))
    return out_path
