# MapGIS 10 HDB 格式逆向笔记

样本:`<MapGIS>/Sample/示例数据.hdb`(SQLite 3)。

## 1. 几何二进制 `mpshape`

| 几何 | `mptype` | 结构(小端) |
|---|---|---|
| 点 | `1` | `<I 1>` + `<3d x, y, z>`(28 字节) |
| 线 | `4` | `b"\x00\x02"` + `<B 点数>` + `b"\x00\x00\x00"` + `<2d x,y> * n` |
| 区 | `8` | `b"\x01\x00\x00\x00\x01\x00\x00\x00\x07\x00\x02"` + `<I 点数>` + `<2d x,y> * n` |

* 线的**第 3 个字节就是点数**,上限 255;超过须拆段。
* 区的点数用 4 字节,11 字节头固定。
* 坐标是 IEEE754 double,**与要素的原生坐标系一致**(本项目用 CGCS2000 度)。

验证:把示例库全部要素解码后再重新编码,**与原 BLOB 逐字节一致**
（点 485/485、线 49/49、区 19/19）。这条验证是整套格式理解的地基。

## 2. 表结构

```
mpf<N>(mpoid INTEGER PRIMARY KEY,
       mpshape BLOB NOT NULL,
       mptype INTEGER NOT NULL,
       mpginf_id INTEGER NOT NULL,
       mpmod_time TEXT NOT NULL DEFAULT (datetime(...)),
       mpLayer INTEGER NOT NULL DEFAULT 0,
       [mpLength]             -- 线
       [mpArea, mpPerimeter]  -- 区
       [, 属性列...])

mpf<N>_rtree(mpid, mpxmin, mpxmax, mpymin, mpymax)   -- SQLite rtree 虚拟表
mi<N>(id INTEGER PRIMARY KEY, definition JSON)        -- 图形参数(符号)
```

* **表号 `N` 等于 `mpdb_item.id`**,不是任意编号。
* `mpginf_id` 指向同名 `mi<N>` 表的 `id`。
* `rtree` 用 **float32** 存边界,比对时要按相对精度(如 `1e-5`)而非 `1e-9`。

## 3. 元数据表

### `mpdb_item`(最关键的字段)

| 字段 | 说明 |
|---|---|
| `id` | 表号,决定 `mpf<N>` / `mi<N>` |
| `name` | 要素类显示名 |
| `physical_name` | `mpf<N>` |
| `uuid` | 32 位大写十六进制 |
| `type` | `30` = 简单要素类 |
| **`subtype`** | **点=1 / 线=2 / 面=3** ← 写错会导致图层不渲染 |
| `definition` | `MpGDBItemDef` XML |
| `objcnt` | 要素数 |

### `mpdb_sfcls`

`id, name, database_name, schema, table_name, geometry_column, type, fds_id, gnet_id, srid, scalex, scaley, dwflags, xoffset, yoffset, zoffset, moffset, xscale, yscale, zscale, mscale, subtype_fld, version, minx, miny, maxx, maxy, minz, maxz, mmin, mmax, encode, storage_config`

* `srid` 指向 `mpdb_sref.id`;**CGCS2000(epsg 4490)的 id = 8**。
* `encode` / `storage_config` 用 `MAPGISBLOB`。
* `version` 取 `70`。

### `mpdb_fldinf`

字段定义。`fld_type`:`0` 文本、`4` 整数、`7` 双精度。

### `mpdb_sequence` / `mpdb_index`

* `sequence`:每个 `mpf<N>` 与 `mi<N>` 各一条,记录最大 id。
* `index`:空间索引一条,`type=8`,`physical_name=mpf<N>_rtree`。

## 4. 建库流程

1. 复制一个 MapGIS 空库(含 `mpdb_*` 与 `mpdb_sref` 506 条)
2. 为每个要素类:
   - `CREATE TABLE mpf<N>` + `CREATE VIRTUAL TABLE mpf<N>_rtree USING rtree(...)`
   - `CREATE TABLE mi<N>` 并写入符号 JSON
   - 写要素(几何 + 属性),同步写 rtree
   - 写 `mpdb_item`(注意 `subtype`)、`mpdb_sfcls`(注意 `srid`)、`mpdb_fldinf`、`mpdb_sequence`、`mpdb_index`
3. `mpdb_item.id` 从 `max(id)+1` 递增

## 5. 踩过的坑

| 坑 | 现象 | 原因 |
|---|---|---|
| `subtype` 全写 1 | 面/线图层完全不渲染,只有点状标注 | MapGIS 按 subtype 判断几何类型 |
| `objcnt` 不一致 | 图层要素数显示异常 | 必须等于实际行数 |
| `mi<N>` 缺失 | 图层无符号 | 每个要素类都要有同名符号表 |
| `rtree` 用 float32 | 精确比对失败 | 边界被量化,比对用相对容差 |
| `database_name` 与文件名不符 | `gdbp://` URL 解析不到 | 库名 = 文件名(不含扩展名) |
