# MapGIS 功能覆盖矩阵

> 依据:从 MapGIS Desktop 帮助文档 `Documentation/MapGISDesktop/operation/` 自动提取,
> 共 **290 个功能页面 / 1317 个功能标题**(明细见 `capabilities.json`)。
> 由 `tools/extract_capabilities.py` 重新生成。

## 结论先说

MapGIS Desktop 的功能分三层:

| 层 | 能否在本项目实现 | 说明 |
|---|---|---|
| **文件层**(数据/文档/样式) | ✅ 可以 | HDB 是 SQLite、`.mapx` 是 XML,已逆向 |
| **算法层**(裁剪/缓冲/叠加/综合) | 🟡 部分可做 | 纯 Python 可做简单版;复杂的需要几何引擎 |
| **运行时层**(服务、瓦片、三维、GPU) | 🔴 不做 | 依赖 MapGIS 服务端/客户端进程 |

**"把所有功能都加进来"在文件层是可行的,算法层可以逐步补,运行时层只能调外部服务。**

## 模块级矩阵

| MapGIS 模块 | 页面数 | 本项目状态 | 说明 |
|---|---|---|---|
| 工作空间 / 二维地图 | ~60 | 🟡 部分 | 图层/符号/标注/视图已做;服务图层(WMTS/WMS/天地图)未做 |
| 数据管理(DataManager) | ~70 | 🟡 部分 | 建库/要素类 CRUD/导入导出/体检已做;栅格、元数据、数据转换未做 |
| 地图编辑(MapEditor) | ~40 | 🟡 部分 | 要素读写已做;交互式编辑需要 GUI,不做 |
| 排版打印(Layout) | ~20 | 🟡 部分 | 图廓/地图框/文字/指北针/色块图例已做;统计图/表格/图片未做 |
| 地图综合(MapSynthesis) | ~15 | 🟡 部分 | 可做简化/抽稀;拓扑综合未做 |
| 栅格编辑 / 影像分析 | ~40 | 🔴 未做 | 需要栅格引擎(可用 GDAL/rasterio 接入) |
| DEM 分析 | ~15 | 🔴 未做 | 需要栅格引擎 |
| 网络分析 | ~10 | 🔴 未做 | 需要图算法引擎 |
| 三维编辑与分析 | ~25 | 🔴 未做 | 需要 3D 引擎 |
| 地图瓦片 | ~10 | 🔴 未做 | 需要服务端/瓦片生成 |
| MapGIS 工具箱 | ~10 | 🟡 部分 | 200+ 工具中的矢量类可逐步实现 |
| 应用专题 | ~15 | 🔴 未做 | 依赖上述能力 |

## 已实现的具体功能

### 数据(文件层)

- 要素类:新建 / 列出 / 重命名 / 删除
- 要素:写入(点/线/区,自动拆分超长线)/ 读取 / 属性查询 / 空间查询(bbox)
- 统计:要素数、范围、字段唯一值/数值统计
- 体检:完整性、要素表/rtree/符号表引用、subtype 与几何类型一致性
- 导入导出:Shapefile ↔ HDB
- 坐标:CGCS2000(srid=8)读写

### 地图(文档层)

- 图层:类型、数据源 URL、顺序、可见性
- 符号:面/线/点(含 MapGIS 的"三值线宽/线色"规则)
- 标注:字段表达式、字号、颜色
- 专题设色:单色 / 多类(拆图层方案)
- 版面:图廓、地图框、文字、指北针、矩形色块(图例)
- 工具:颜色库索引色卡

## 可继续实现(按可行性)

### A. 纯 Python 就能做

| 功能 | 状态 |
|---|---|
| **要素类字段增删改** | ✅ `hdb.add_field` / `hdb.drop_field` / `cli`(Python API) |
| **按属性更新要素** | ✅ `hdb.update_features` / MCP `hdb_update_features` |
| **导出 GeoJSON** | ✅ `geojson.write_geojson` / `cli geojson-export` |
| **从 GeoJSON 导入** | ✅ `geojson.read_geojson` / `cli geojson-import` |
| **批量出图** | ✅ `batch.build_batch` / `batch.build_by_regions` / MCP `mapx_batch_build` |
| **图层样式导入/导出** | ✅ `style.styles_from_mapx` / `cli styles-export` |
| **线抽稀(Douglas-Peucker)** | ✅ `geometry.simplify` |
| **HDB 修复(rtree/objcnt/subtype/符号表)** | ✅ `hdb.repair` / `cli repair` |
| **颜色映射自动化(色卡 PNG 取色)** | ✅ `color_probe.extract_palette` / `cli color-probe` |
| **参考色 → 索引(含内置参考图色值)** | ✅ `colors.REFERENCE_ZONE_RGB` / `resolve_zone_indices` / `nearest_index` |
| **注记类(acls)** | ✅ `annotation.add/read/delete` / `cli annotations-list` |
| **三维面(mptype 8/9)** | ✅ `three_d.decode/encode_shape3d` / `cli 3d-info` |

### B. 需要额外库(已接入)

| 功能 | 依赖 | 状态 |
|---|---|---|
| **裁剪 / 缓冲 / 相交 / 融合** | shapely | ✅ `ops.clip/buffer_features/intersect/dissolve` |
| **坐标投影** | pyproj | ✅ `ops.project/project_extent` |
| **栅格元数据 / 统计 / 裁剪 / PNG** | rasterio + numpy | ✅ `raster.*` |
| **栅格重采样 / 镶嵌 / 计算器 / 投影** | rasterio + numpy | ✅ `raster.resample/mosaic/calculator/reproject` |
| **网络分析(最短路径/连通分量)** | networkx | ✅ `network.*` |
| **拓扑检查(无效/重叠/缝隙/悬挂/重复)** | shapely | ✅ `topology.*` / `cli topology` |
| 栅格金字塔/瓦片 | rasterio | 🟡 待做 |
| **三维面几何(读/写)** | 标准库 | ✅ `three_d` |
| 三维场景/渲染 | pyvista / MapGIS | 🔴 待做 |

### C. 不适合本项目

- 交互式地图编辑(需要 MapGIS GUI)
- 地图瓦片发布、IGServer 服务
- 三维场景渲染
- 依赖 MapGIS 授权组件的功能(符号库渲染、图例生成)

## 路线建议

1. **先把文件层做扎实**(当前)→ 加字段/属性更新、GeoJSON、批量出图、HDB 修复
2. **引入 shapely/pyproj**(可选依赖)→ 裁剪、叠加、缓冲、投影
3. **栅格层**(可选)→ rasterio 接入
4. **保持 MCP 工具面稳定**,新增能力只加工具、不改已有签名

## 重新生成本矩阵

```bash
python tools/extract_capabilities.py --json docs/capabilities.json
```
