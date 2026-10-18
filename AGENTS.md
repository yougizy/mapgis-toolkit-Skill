# AGENTS.md — mapgis-toolkit-Skill 开发说明

面向在本仓库里继续开发的 agent / 人。

## 项目定位

**不依赖 MapGIS 进程**,直接读写 MapGIS 10 的文件层:

- `.hdb` — SQLite 数据库(要素类、注记类、栅格目录、元数据)
- `.mapx` — gb2312 编码的 XML 地图文档(图层、符号、标注、版面)

目标不是复刻 MapGIS GUI,而是把**可自动化的部分**做成稳定的 Python 库 / CLI / MCP 工具。

## 目录

```
src/mapgis_toolkit/
  geometry.py   点/线/区二进制编解码、抽稀、质心
  shp.py        Shapefile 读写(纯标准库)
  hdb.py        建库、要素类 CRUD、查询、统计、体检、修复
  mapx.py       .mapx 生成(图层/符号/标注)
  layout.py     版面元素
  colors.py     索引色编码
  style.py      图层样式提取
  annotation.py 注记类(acls)
  three_d.py    三维面(mptype 8/9)
  geojson.py    GeoJSON 双向
  ops.py        裁剪/缓冲/相交/融合/投影(shapely/pyproj)
  raster.py     栅格(rasterio/numpy)
  network.py    网络分析(networkx)
  topology.py   拓扑检查(shapely)
  color_probe.py 色卡 PNG → 索引色表(Pillow)
  batch.py      批量出图 / 批量转换
  cli.py        27 个子命令
  mcp_server.py 36 个 MCP 工具
tests/          62 项单测(11 个测试文件)
tools/          逆向探查与提取
                probe_sample / probe_annotation / probe_3d / probe_palette
                probe_stylelib / find_color_tables / extract_ext_palette
                extract_capabilities
examples/       完整出图示例(build_jiangxi_mapx.py)
docs/           格式笔记、能力矩阵、扩展色表(palette_ext.json)
```

## 开发约定

1. **测试先行**:任何改动跑 `python -m unittest discover -s tests`,必须全绿。
2. **可选依赖要懒加载**:`ops`、`raster`、`network`、`color_probe` 在模块顶层 `import` 时缺库会抛 `ImportError`,调用方(`cli`、`mcp_server`)应在函数内部 import,避免整体不可用。
3. **路径**:Windows 中文路径一律用 `pathlib` / `unicode`;只读目录(`Program Files`)下的库用 `?mode=ro&immutable=1`。
4. **`.mapx` 编码**:读 `gb2312`,写 `gb2312`;不要用 UTF-8 覆盖。
5. **要素类元数据三件套**:`mpdb_item`(type/subtype/physical_name)、`mpdb_sfcls`(范围/几何列)、`mpdb_sequence`(自增)—— 新建类时三者都要写。
6. **`subtype` 必须与几何一致**:点 1 / 线 2 / 面 3。这是"整层不渲染"的常见根因。
7. **图层顺序**:`.mapx` 中后面的 `<subnode>` 覆盖前面的;面在下、点在上。
8. **`outpenw` 三值**;`fillclr`/`iclr` 用索引,不用真彩色。

## 常用命令

```bash
# 测试
python -m unittest discover -s tests

# CLI
python -m mapgis_toolkit.cli --help
python -m mapgis_toolkit.cli info  库.hdb
python -m mapgis_toolkit.cli inspect 库.hdb
python -m mapgis_toolkit.cli repair  库.hdb

# MCP
python -m mapgis_toolkit.mcp_server

# 逆向探查(只读)
python tools/probe_sample.py
python tools/probe_annotation.py
python tools/probe_3d.py
python tools/extract_capabilities.py --json docs/capabilities.json
```

## 配色

- 索引色是唯一可靠的取色方式。
- **系统色库实测（完整）**：

  | 文件 | 结论 |
  |---|---|
  | `SLib/Pcolor.lib`（71 KB，实际使用） | 头部 `e0 05` → **1504 色**；色值为编码存储（RGB/BGR/RGB565/BGR565 全部试过，均不匹配） |
  | `DefaultSystemLib/Slib/Pcolor.lib`（52 KB） | `28 头 + 256×206`；同样编码存储 |
  | `PColor_EXT.lib` | ✅ 明文：`12 头 + 1640×3` RGB |
  | `PColor_EXT_1.lib` | 非 RGB 表 |
  | `styleLib.sty` | SQLite，10 张样式表，**无颜色表** |
  | `Config/lut/*.lut` | 栅格伪彩色（LUT1.0），与矢量索引色无关 |

- 颜色号实测：`1407 = RGB(232,205,223)`；扩展色表最近色为 `index 772 = (229,204,229)`，
  **顺序不对应、偏移不固定**。
- 从颜色选择器截图自动提取色表**不可行**（淡彩块与白底对比度不足，列检测被切断）。
- 可用 API：`colors.load_ext_palette()` / `ext_nearest()` /
  `colors.REFERENCE_ZONE_RGB` / `resolve_zone_indices()`。
- 校准链：`color-card` → MapGIS 导出 PNG → `color-probe` → `--palette`。
- 不要把真彩色写进 `fillclr`/`iclr`（会被当索引渲染成黑）。

## 已知边界

- 不能做:服务发布、瓦片、交互式编辑、三维渲染、依赖 MapGIS 授权组件的符号渲染。
- 注记图层的 `.mapx` 节点类型(`CreateGAnnotaionLayer@cln_workspace.dll`)依据 `ClassFactory.xml` 推断,**尚未在 MapGIS 中实机确认**。
- 三维写入只覆盖 mptype 8/9 的面;尾部索引字段按样本写入,未经 MapGIS 回读验证。

## 相关

- 详细格式:`docs/format-hdb.md`、`docs/format-mapx.md`
- 功能覆盖:`docs/capability-map.md`(290 页 / 1317 条)
- Skill 入口:`.reasonix/skills/mapgis-toolkit-Skill.md`
