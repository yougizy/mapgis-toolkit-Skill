# mapgis-toolkit

[English](README.md) | **简体中文**

> 逆向 MapGIS 10 的 **HDB 地理数据库**与 **`.mapx` 地图文档**格式，提供可编程的读写、体检与制图能力。
> 不依赖 MapGIS 客户端、不依赖 GDAL，核心只用 Python 标准库。

> 本项目为独立社区项目，与 MapGIS 官方无关。

## 为什么有这个项目

MapGIS Desktop 没有可调用的 API/MCP，窗口也不暴露可编程控件（只能截图 + 坐标点击）。
要稳定地批量制图、检查数据、生成工程，只能从**文件格式**入手。

本项目把 MapGIS 10.8 自带样本（`Sample/示例数据.hdb`、`Program/Config/MapTemplates/CoomMap/*.mapx`）
逆向成一套可用的读写库，并做了字节级验证。

## 能力一览

| 领域 | 能力 |
|---|---|
| 几何 | 点/线/区二进制编解码、Douglas–Peucker 抽稀、质心 |
| 数据库 | 建库、要素类 CRUD、属性/空间查询、统计、体检与修复 |
| 数据交换 | Shapefile ↔ HDB ↔ GeoJSON，目录批量转换 |
| 地图文档 | 图层生成（符号/标注）、单值专题图、版面元素（图廓/地图框/文字/指北针） |
| 注记类 | `acls` 读写（文本、位置、字号、颜色） |
| 三维 | 三维面几何（`mptype` 8/9）编解码 |
| 栅格 | 元数据、统计、裁剪、重采样、镶嵌、栅格计算器（rasterio） |
| 分析 | 裁剪/缓冲/相交/融合/投影（shapely/pyproj）；网络分析（networkx）；拓扑检查 |
| 接口 | 27 个 CLI 子命令 · Python 库 · 36 个 MCP 工具 |

## 安装

```bash
git clone <仓库地址>
cd mapgis-toolkit-Skill
pip install -e .
```

可选依赖：

```bash
pip install -e ".[mcp]"     # MCP server
pip install -e ".[geo]"     # shapely + pyproj
pip install -e ".[raster]"  # rasterio + numpy
pip install -e ".[net]"     # networkx
pip install -e ".[color]"   # Pillow（色卡取色）
pip install -e ".[all]"
```

要求 Python 3.9+；核心格式编解码只用标准库。

## 快速开始

### 命令行

```bash
python -m mapgis_toolkit.cli --help

python -m mapgis_toolkit.cli info     data.hdb
python -m mapgis_toolkit.cli inspect  data.hdb
python -m mapgis_toolkit.cli export   data.hdb  rivers out.shp
python -m mapgis_toolkit.cli import   data.hdb  rivers rivers.shp --type Line
python -m mapgis_toolkit.cli query    data.hdb  cities --where NAME=南昌市
python -m mapgis_toolkit.cli stats    data.hdb  cities --field AREA
python -m mapgis_toolkit.cli repair   data.hdb
```

### Python

```python
from mapgis_toolkit import hdb, shp

con = hdb.new_database("template.hdb", "out.hdb")
shape_type, features = shp.read_shp("rivers.shp")
hdb.add_feature_class(con, "rivers", "Line", features,
                      fields=[("NAME", "TEXT", 0, "名称")], srid=8)
print(hdb.inspect(con)["ok"])
con.close()
```

### 生成地图文档

```python
from mapgis_toolkit import layout, mapx

layer = mapx.make_layer(
    template_xml, "cities", "gdbp://MapGISLocalPlus/out/sfcls/cities",
    fill={"fillclr": 15}, label_expr="NAME", label_visible=True,
)
page = layout.layout(210.0, 297.0, "\n".join([
    layout.polygon_element(10, 20, 200, 278, fillclr=9, outpenw=0.7),
    layout.text_element("我的地图", 16, 285, height=8, color=6),
    layout.map_element(mapx.DEFAULT_GUID, "main", (14, 30, 196, 270),
                       (113.5, 24.4, 118.5, 30.1)),
]))
mapx.build_mapx("out.mapx", "我的地图", layer, (113.5, 24.4, 118.5, 30.1),
                layout_xml=page)
```

完整示例（11 个设区市、河流湖泊、图例、图廓）见
[`examples/build_jiangxi_mapx.py`](examples/build_jiangxi_mapx.py)。

### MCP

```bash
python -m mapgis_toolkit.mcp_server
```

```json
{
  "mcpServers": {
    "mapgis-toolkit": {
      "command": "python",
      "args": ["-m", "mapgis_toolkit.mcp_server"],
      "env": { "PYTHONPATH": "<仓库路径>/src" }
    }
  }
}
```

## 格式笔记

- [`docs/format-hdb.md`](docs/format-hdb.md) — 表结构、几何编码、元数据
- [`docs/format-mapx.md`](docs/format-mapx.md) — 文档结构、图层、符号、版面
- [`docs/capability-map.md`](docs/capability-map.md) — 对 290 个帮助页面 / 1317 个功能标题的覆盖矩阵

## 已知限制

- **颜色索引**：`fillclr` / `iclr` 只接受颜色库索引，真彩色会渲染成黑色。
  基础 256 色表在 `Pcolor.lib` 中是编码存储，无法直接解析。
  可用色卡校准流程：`color-card` → 导出 PNG → `color-probe`。
- **图例**：官方样本没有图例 XML，本项目用 `PolygonElement` 手绘基础图例。
- **在 MapGIS 中保存会重写**：`geometryType` 按库内 `subtype` 回写，版面元素可能被清空。
  建议只用脚本生成、只读查看。
- **专题图**：`MultiClassTheme` 在部分环境被忽略；更稳妥的是每类单独一个要素类 + `SimpleTheme`。
- **运行时能力**：服务发布、瓦片、交互式编辑、三维渲染依赖 MapGIS 运行时，不在范围内。

## 参与贡献

欢迎 issue 与 PR，请先阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

```bash
python -m unittest discover -s tests
```

部分测试需要 MapGIS 空库作为模板，设置 `MG_TEMPLATE` 指向它；未设置时自动跳过。

## 许可

[MIT](LICENSE)
