"""MapGIS 10 地理数据库(.hdb,SQLite)读写与体检。

库结构(逆向自 MapGIS 10.8 ``Sample/示例数据.hdb``):

========================  =============================================================
表                        含义
========================  =============================================================
``mpf<N>``                要素表:``mpoid, mpshape(BLOB), mptype, mpginf_id,
                          mpmod_time, mpLayer [, mpLength | mpArea,mpPerimeter][, 属性列]``
``mpf<N>_rtree``          空间索引(SQLite rtree 虚拟表,边界用 float32)
``mi<N>``                 符号参数(id, definition JSON)
``mpdb_item``             数据集/要素类登记(subtype: 点=1 / 线=2 / 面=3)
``mpdb_sfcls``            简单要素类元数据(srid、范围、编码等)
``mpdb_fldinf``           字段定义
``mpdb_sequence``         各表序列
``mpdb_index``            索引定义(空间索引)
========================  =============================================================

表号 ``N`` 与 ``mpdb_item.id`` 一致;要素的 ``mpginf_id`` 指向同名 ``mi<N>`` 表。
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import uuid as _uuid
from typing import Dict, Iterable, List, Sequence, Tuple

from . import geometry

POINT, LINE, REGION = "Point", "Line", "Region"

_MPTYPE = {"Point": geometry.MPTYPE_POINT, "Line": geometry.MPTYPE_LINE,
           "Region": geometry.MPTYPE_REGION}
_SUBTYPE = {"Point": 1, "Line": 2, "Region": 3}
_GEOM_FIELDS = {
    "Point": [],
    "Line": [("mpLength", "REAL", 7, "长度")],
    "Region": [("mpArea", "REAL", 7, "面积"), ("mpPerimeter", "REAL", 7, "周长")],
}

_ITEM_DEF_XML = (
    '<?xml version="1.0"?>\n<MpGDBItemDef>\n\t<Type>SFeatureCls</Type>\n'
    '\t<Content>\n\t\t<MpSFeatureClsDef version="1.0">\n'
    '\t\t\t<OIDColumnName />\n\t\t\t<OIDSequenceName />\n'
    '\t\t\t<mpSystemGUID />\n\t\t\t<RangeValid>true</RangeValid>\n'
    '\t\t</MpSFeatureClsDef>\n\t</Content>\n</MpGDBItemDef>\n'
)

_INDEX_DEF_XML = (
    '<?xml version="1.0"?>\n<MpGDBIndexDef>\n\t<Type>SpatialIndex</Type>\n'
    '\t<Content version="">\n\t\t<MpIndexDef>\n\t\t\t<SQLText> insert into %(rt)s'
    ' select a.mpoid, b.xmin, b.xmax, b.ymin, b.ymax from %(tb)s a,'
    ' st_envelope(a. mpshape, a.mptype, $1, $2) b</SQLText>\n'
    '\t\t</MpIndexDef>\n\t</Content>\n</MpGDBIndexDef>\n'
)

_GINF_STYLE = {"Point": ("MpPointGInf", "SymID"), "Line": ("MpLineGInf", "LinstyID"),
               "Region": ("MpRegionGInf", "SymID")}


class HdbError(RuntimeError):
    """HDB 读写异常。"""


def _symbol_json(geom_type: str) -> str:
    inner, sym = _GINF_STYLE[geom_type]
    if geom_type == "Line":
        body = ('{"LibID":0,"LinstyID":1,"Ovprnt":0,"OutPenW0":0.05,'
                '"OutPenW1":0.05,"OutPenW2":0.05,"OutClr0":1,"OutClr1":4,'
                '"OutClr2":3,"HeadType":0,"JoinType":0,"Adjustflg":0,'
                '"Makemethod":0,"Xscale":10.0,"Yscale":10.0}')
    elif geom_type == "Point":
        body = ('{"LibID":0,"SymID":1,"Height":3.0,"Width":3.0,"Angle":0.0,'
                '"OutPenW0":0.05,"OutPenW1":0.05,"OutPenW2":0.05,'
                '"OutClr0":1,"OutClr1":4,"OutClr2":3,"Ovprnt":0,"FillFlg":1,'
                '"BackExp":1.0,"BackClr":1}')
    else:
        body = ('{"LibID":0,"SymID":1,"Ovprnt":0,"OutPenW0":0.05,'
                '"OutPenW1":0.05,"OutPenW2":0.05,"OutClr0":1,"OutClr1":4,'
                '"OutClr2":3,"FillFlg":1,"BackExp":1.0,"BackClr":1}')
    return ('{"MpGInf":{"Type":"%s","Content":{"version":"1.0","%s":%s}}}'
            % (geom_type, inner, body))


# ---------------------------------------------------------------------------
# 建库
# ---------------------------------------------------------------------------

def new_database(template_path: str, dst_path: str) -> sqlite3.Connection:
    """以 MapGIS 空库为模板复制出新库,返回连接(自动建统一索引)。"""
    if not os.path.exists(template_path):
        raise HdbError("模板库不存在: %s" % template_path)
    if os.path.exists(dst_path):
        os.remove(dst_path)
    shutil.copyfile(template_path, dst_path)
    con = sqlite3.connect(dst_path)
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("PRAGMA synchronous=OFF")
    return con


def _next_item_id(con: sqlite3.Connection) -> int:
    row = con.execute("select max(id) from mpdb_item").fetchone()
    return (row[0] or 0) + 1


def add_feature_class(con: sqlite3.Connection, name: str, geom_type: str,
                      features: Sequence[dict], fields: Sequence[tuple] | None = None,
                      srid: int = 8, database_name: str | None = None) -> int:
    """新建简单要素类并写入要素,返回表号 N。

    ``features`` 结构同 :mod:`mapgis_toolkit.shp` 的读取结果。
    ``fields`` 为 ``[(字段名, SQL 类型, fld_type, 别名), ...]``。
    """
    if geom_type not in _MPTYPE:
        raise HdbError("geom_type 必须是 Point/Line/Region")
    fields = list(fields or [])
    dbname = database_name or os.path.splitext(os.path.basename(
        con.execute("PRAGMA database_list").fetchone()[2]))[0]

    n = _next_item_id(con)
    tb, rt = "mpf%d" % n, "mpf%d_rtree" % n
    mptype = _MPTYPE[geom_type]
    subtype = _SUBTYPE[geom_type]

    # --- 要素表 ---
    cols = ["mpoid INTEGER primary key", "mpshape BLOB not null",
            "mptype INTEGER not null", "mpginf_id INTEGER not null",
            "mpmod_time TEXT NOT NULL DEFAULT (datetime(CURRENT_TIMESTAMP,'localtime'))",
            "mpLayer INTEGER NOT NULL DEFAULT 0"]
    for fname, ftype, _ft, _a in _GEOM_FIELDS[geom_type]:
        cols.append("%s %s" % (fname, ftype))
    for fname, fsql, _ft, _a in fields:
        cols.append("%s %s" % (fname, fsql))
    con.execute('CREATE TABLE "%s"(%s)' % (tb, ",".join(cols)))
    con.execute('CREATE VIRTUAL TABLE "%s" USING rtree(mpid int, mpxmin real, '
                'mpxmax real, mpymin real, mpymax real)' % rt)

    # --- 符号参数 ---
    con.execute('CREATE TABLE "mi%d"(id int primary key, definition json not null)' % n)
    con.execute('INSERT INTO "mi%d"(id, definition) VALUES (?, ?)' % n,
                (0, _symbol_json(geom_type)))

    # --- 写要素 ---
    ins = ["mpoid", "mpshape", "mptype", "mpginf_id", "mpLayer"]
    ins += [f[0] for f in _GEOM_FIELDS[geom_type]]
    ins += [f[0] for f in fields]
    sql = 'INSERT INTO "%s"(%s) VALUES (%s)' % (tb, ",".join(ins),
                                                ",".join("?" * len(ins)))

    records: List[Tuple[int, bytes, dict, list]] = []
    oid = 0
    for feat in features:
        for ring in feat.get("parts") or []:
            if not ring:
                continue
            if geom_type == "Point":
                oid += 1
                records.append((oid, geometry.encode_point(ring[0][0], ring[0][1]),
                                feat.get("attrs", {}), ring))
            elif geom_type == "Line":
                for seg in geometry.split_line(ring):
                    oid += 1
                    records.append((oid, geometry.encode_line(seg),
                                    feat.get("attrs", {}), seg))
            else:
                oid += 1
                records.append((oid, geometry.encode_region(ring),
                                feat.get("attrs", {}), ring))

    minx = miny = 3.4e38
    maxx = maxy = -3.4e38
    for o, blob, attrs, pts in records:
        xmin, ymin, xmax, ymax = geometry.bbox(pts)
        minx, miny = min(minx, xmin), min(miny, ymin)
        maxx, maxy = max(maxx, xmax), max(maxy, ymax)
        vals: list = [o, sqlite3.Binary(blob), mptype, 0, 0]
        if geom_type == "Line":
            vals.append(sum(
                ((pts[i][0] - pts[i - 1][0]) ** 2 + (pts[i][1] - pts[i - 1][1]) ** 2) ** 0.5
                for i in range(1, len(pts))))
        elif geom_type == "Region":
            vals.append(abs(geometry.ring_area(pts)))
            vals.append(geometry.ring_perimeter(pts))
        for fname, _s, _ft, _a in fields:
            vals.append(attrs.get(fname, ""))
        con.execute(sql, vals)
        con.execute('INSERT INTO "%s"(mpid, mpxmin, mpxmax, mpymin, mpymax) '
                    'VALUES (?,?,?,?,?)' % rt, (o, xmin, xmax, ymin, ymax))

    if oid == 0:
        minx = miny = maxx = maxy = 0.0

    # --- 元数据 ---
    con.execute(
        "INSERT INTO mpdb_item(id,name,alias_name,database_name,schema,subset,"
        "physical_name,uuid,type,subtype,dwflags,definition,metadata,objcnt,loadrefcnt) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (n, name, "", dbname, "main", 1, tb, _uuid.uuid4().hex.upper(), 30,
         subtype, None, _ITEM_DEF_XML, None, oid, 0))

    con.execute(
        "INSERT INTO mpdb_sfcls(id,name,database_name,schema,table_name,"
        "geometry_column,type,fds_id,gnet_id,srid,scalex,scaley,dwflags,"
        "xoffset,yoffset,zoffset,moffset,xscale,yscale,zscale,mscale,"
        "subtype_fld,version,minx,miny,maxx,maxy,minz,maxz,mmin,mmax,"
        "encode,storage_config) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (n, name, dbname, "main", tb, "mpshape", None, 0, 0, srid,
         1.0, 1.0, None, -400.0, -400.0, -100000.0, -100000.0,
         1000000000, 1000000000, 10000, 10000, None, 70,
         minx, miny, maxx, maxy, 3.4e38, -3.4e38, 3.4e38, -3.4e38,
         "MAPGISBLOB", "MAPGISBLOB"))

    con.execute("INSERT INTO mpdb_sequence(table_name, seq_id) VALUES (?,?)", (tb, oid))
    con.execute("INSERT INTO mpdb_sequence(table_name, seq_id) VALUES (?,?)",
                ("mi%d" % n, 1))
    con.execute(
        "INSERT INTO mpdb_index(clsid,name,type,physical_name,table_name,schema,"
        "is_unique,column_name,is_asc,definition) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (n, rt, 8, rt, tb, "main", 0, "mpshape", 1,
         _INDEX_DEF_XML % {"rt": rt, "tb": tb}))

    idx = 0
    base = [("mpLayer", "INTEGER", 4, "图层")]
    if geom_type == "Line":
        base.append(("mpLength", "REAL", 7, "长度"))
    elif geom_type == "Region":
        base += [("mpArea", "REAL", 7, "面积"), ("mpPerimeter", "REAL", 7, "周长")]
    for fname, _t, ft, alias in base + list(fields):
        if ft == 7:
            leng, msk, pnt = 8, 15, 6
        elif ft == 4:
            leng, msk, pnt = 4, 10, 0
        else:
            leng, msk, pnt = 254, 255, 0
        con.execute(
            "INSERT INTO mpdb_fldinf(clsid,table_name,fld_name,fld_index,"
            "fld_leng,msk_leng,pnt_leng,edt_enable,fld_type,alias_name,not_null,"
            "is_must) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (n, tb, fname, idx, leng, msk, pnt, 1 if ft == 4 else 0, ft,
             alias, 0, 0))
        idx += 1
    con.commit()
    return n


# ---------------------------------------------------------------------------
# 读取
# ---------------------------------------------------------------------------

def list_feature_classes(con: sqlite3.Connection) -> List[dict]:
    """列出要素类(id/name/table/要素数/坐标系/范围/subtype)。"""
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "select i.id, i.name, i.physical_name, i.objcnt, i.subtype, s.srid, "
        "s.minx, s.miny, s.maxx, s.maxy from mpdb_item i "
        "left join mpdb_sfcls s on s.id = i.id order by i.id").fetchall()
    return [dict(r) for r in rows]


def feature_class_id(con: sqlite3.Connection, name: str) -> int:
    row = con.execute("select id from mpdb_item where name = ?", (name,)).fetchone()
    if not row:
        raise HdbError("找不到要素类: %s" % name)
    return row[0]


def read_features(con: sqlite3.Connection, name: str) -> List[dict]:
    """读取要素类全部要素,返回 ``[{"oid","geom_type","parts","attrs"}]``。"""
    cid = feature_class_id(con, name)
    table = con.execute("select physical_name from mpdb_item where id=?",
                        (cid,)).fetchone()[0]
    attr_cols = [r[0] for r in con.execute(
        "select fld_name from mpdb_fldinf where clsid=? order by fld_index",
        (cid,)) if r[0] not in ("mpLayer", "mpLength", "mpArea", "mpPerimeter")]
    cols = ["mpoid", "mpshape", "mptype"] + attr_cols
    out: List[dict] = []
    for row in con.execute('select %s from "%s"' % (",".join(cols), table)):
        oid, blob, mptype = row[0], row[1], row[2]
        pts = geometry.decode(bytes(blob), mptype)
        out.append({
            "oid": oid,
            "geom_type": geometry.KIND_BY_MPTYPE.get(mptype, "?"),
            "parts": [pts],
            "attrs": {c: row[3 + i] for i, c in enumerate(attr_cols)},
        })
    return out


# ---------------------------------------------------------------------------
# 体检
# ---------------------------------------------------------------------------

def inspect(con: sqlite3.Connection) -> dict:
    """体检:库完整性、要素表/rtree/符号表引用、subtype 与几何类型一致性。"""
    problems: List[str] = []
    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        problems.append("integrity_check: %s" % integrity)

    tables = {r[0] for r in con.execute(
        "select name from sqlite_master where type in ('table','view')")}
    classes: List[dict] = []
    expect_subtype = {geometry.MPTYPE_POINT: 1, geometry.MPTYPE_LINE: 2,
                      geometry.MPTYPE_REGION: 3}
    for item in list_feature_classes(con):
        name, table, sub = item["name"], item["physical_name"], item["subtype"]
        n = con.execute('select count(*) from "%s"' % table).fetchone()[0] \
            if table in tables else -1
        rt = con.execute('select count(*) from "%s_rtree"' % table).fetchone()[0] \
            if table + "_rtree" in tables else -1
        mi_ok = "mi%d" % item["id"] in tables
        mptype = con.execute('select mptype from "%s" limit 1' % table).fetchone() \
            if n > 0 and table in tables else None
        geom_ok = True
        if mptype:
            geom_ok = expect_subtype.get(mptype[0]) == sub
            if not geom_ok:
                problems.append("%s: subtype=%s 与 mptype=%s 不一致"
                                % (name, sub, mptype[0]))
        if n != item["objcnt"]:
            problems.append("%s: objcnt=%s 实际=%s" % (name, item["objcnt"], n))
        if rt != n:
            problems.append("%s: rtree=%s 要素=%s" % (name, rt, n))
        if not mi_ok:
            problems.append("%s: 缺符号表 mi%d" % (name, item["id"]))
        classes.append({
            "id": item["id"], "name": name, "table": table,
            "count": n, "rtree": rt, "srid": item["srid"],
            "subtype": sub, "geometry_ok": geom_ok,
            "extent": [item["minx"], item["miny"], item["maxx"], item["maxy"]],
        })
    return {"ok": not problems, "integrity": integrity, "classes": classes,
            "problems": problems}


# ---------------------------------------------------------------------------
# 导出 shp
# ---------------------------------------------------------------------------

def export_shp(con: sqlite3.Connection, name: str, out_path: str) -> int:
    """把要素类导出为 shapefile,返回要素数。"""
    from . import shp as shp_mod
    feats = read_features(con, name)
    if not feats:
        raise HdbError("要素类为空: %s" % name)
    kind = feats[0]["geom_type"]
    shape_type = shp_mod.SHAPE_BY_KIND[kind]
    fields = list(feats[0]["attrs"].keys())
    shp_mod.write_shp(out_path, shape_type, feats, fields=fields)
    return len(feats)


# ---------------------------------------------------------------------------
# 要素类管理
# ---------------------------------------------------------------------------

def delete_feature_class(con: sqlite3.Connection, name: str) -> None:
    """删除要素类及其要素表、空间索引、符号表与所有元数据。"""
    cid = feature_class_id(con, name)
    table = con.execute("select physical_name from mpdb_item where id=?",
                        (cid,)).fetchone()[0]
    con.execute('DROP TABLE IF EXISTS "%s"' % table)
    con.execute('DROP TABLE IF EXISTS "%s_rtree"' % table)
    con.execute('DROP TABLE IF EXISTS "mi%d"' % cid)
    for sql in (
        "delete from mpdb_item where id=?",
        "delete from mpdb_sfcls where id=?",
        "delete from mpdb_fldinf where clsid=?",
        "delete from mpdb_index where clsid=?",
    ):
        con.execute(sql, (cid,))
    con.execute("delete from mpdb_sequence where table_name in (?,?)",
                (table, "mi%d" % cid))
    con.commit()


def rename_feature_class(con: sqlite3.Connection, name: str,
                          new_name: str) -> None:
    """重命名要素类(只改显示名,不动表名与数据)。"""
    cid = feature_class_id(con, name)
    con.execute("update mpdb_item set name=? where id=?", (new_name, cid))
    con.execute("update mpdb_sfcls set name=? where id=?", (new_name, cid))
    con.commit()


def query_features(con: sqlite3.Connection, name: str,
                   where: Optional[dict] = None,
                   limit: Optional[int] = None) -> List[dict]:
    """属性查询:``where`` 为 ``{字段: 值}`` 的等值匹配;``值`` 可为 list(IN)。"""
    feats = read_features(con, name)
    if where:
        def match(f):
            attrs = f["attrs"]
            for k, v in where.items():
                if isinstance(v, (list, tuple, set)):
                    if str(attrs.get(k)) not in {str(x) for x in v}:
                        return False
                elif str(attrs.get(k)) != str(v):
                    return False
            return True
        feats = [f for f in feats if match(f)]
    return feats[:limit] if limit else feats


def spatial_query(con: sqlite3.Connection, name: str,
                  bbox: Sequence[float]) -> List[dict]:
    """空间查询:返回与 ``(xmin, ymin, xmax, ymax)`` 相交的要素。"""
    xmin, ymin, xmax, ymax = bbox
    out = []
    for f in read_features(con, name):
        xs = [p[0] for ring in f["parts"] for p in ring]
        ys = [p[1] for ring in f["parts"] for p in ring]
        if not xs:
            continue
        if max(xs) >= xmin and min(xs) <= xmax and max(ys) >= ymin and min(ys) <= ymax:
            out.append(f)
    return out


def repair(con: sqlite3.Connection) -> dict:
    """修复库:重算 objcnt、纠正 subtype、重建空间索引、补缺失的符号表。

    返回 ``{"actions": [...], "count": N}``。
    """
    actions: List[str] = []
    tables = {r[0] for r in con.execute(
        "select name from sqlite_master where type in ('table','view')")}
    expect = {1: 1, 4: 2, 8: 3}
    for item in list_feature_classes(con):
        cid, name = item["id"], item["name"]
        table, sub = item["physical_name"], item["subtype"]

        if table in tables:
            n = con.execute('select count(*) from "%s"' % table).fetchone()[0]
            if n != item["objcnt"]:
                con.execute("update mpdb_item set objcnt=? where id=?", (n, cid))
                actions.append("%s: objcnt %s -> %s" % (name, item["objcnt"], n))

            row = con.execute('select mptype from "%s" limit 1' % table).fetchone()
            if row and expect.get(row[0]) and expect[row[0]] != sub:
                con.execute("update mpdb_item set subtype=? where id=?",
                            (expect[row[0]], cid))
                actions.append("%s: subtype %s -> %s"
                               % (name, sub, expect[row[0]]))

        if table + "_rtree" in tables:
            con.execute('delete from "%s_rtree"' % table)
            for oid, blob, mptype in con.execute(
                    'select mpoid, mpshape, mptype from "%s"' % table).fetchall():
                pts = geometry.decode(bytes(blob), mptype)
                xmin, ymin, xmax, ymax = geometry.bbox(pts)
                con.execute('insert into "%s_rtree"'
                            '(mpid, mpxmin, mpxmax, mpymin, mpymax) '
                            'values (?,?,?,?,?)' % table,
                            (oid, xmin, xmax, ymin, ymax))
            actions.append("%s: rtree 重建" % name)

        if "mi%d" % cid not in tables:
            con.execute('CREATE TABLE "mi%d"(id int primary key, definition json not null)'
                        % cid)
            con.execute('INSERT INTO "mi%d"(id, definition) VALUES (?, ?)' % cid,
                        (0, _symbol_json("Region")))
            actions.append("%s: 补符号表 mi%d" % (name, cid))

    con.commit()
    return {"actions": actions, "count": len(actions)}


def feature_stats(con: sqlite3.Connection, name: str,
                  field: Optional[str] = None) -> dict:
    """统计:要素数、范围;指定字段时给出唯一值或数值统计。"""
    feats = read_features(con, name)
    xs, ys = [], []
    for f in feats:
        for ring in f["parts"]:
            for x, y in ring:
                xs.append(x)
                ys.append(y)
    stats: dict = {
        "name": name,
        "count": len(feats),
        "geometry_types": sorted({f["geom_type"] for f in feats}),
        "extent": [min(xs), min(ys), max(xs), max(ys)] if xs else None,
    }
    if field:
        vals = [f["attrs"].get(field) for f in feats if f["attrs"].get(field) not in (None, "")]
        stats["field"] = field
        stats["non_empty"] = len(vals)
        nums = []
        for v in vals:
            try:
                nums.append(float(v))
            except (TypeError, ValueError):
                nums = []
                break
        if nums:
            stats["numeric"] = {
                "min": min(nums), "max": max(nums),
                "mean": sum(nums) / len(nums),
            }
        else:
            from collections import Counter
            stats["top_values"] = Counter(map(str, vals)).most_common(20)
    return stats


# ---------------------------------------------------------------------------
# 字段与属性维护
# ---------------------------------------------------------------------------

def add_field(con: sqlite3.Connection, name: str, field: str,
              sql_type: str = "TEXT", fld_type: int = 0,
              alias: str = "") -> int:
    """给要素类加字段,并登记到 mpdb_fldinf。返回 fld_index。"""
    cid = feature_class_id(con, name)
    table = con.execute("select physical_name from mpdb_item where id=?",
                        (cid,)).fetchone()[0]
    con.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (table, field, sql_type))
    row = con.execute("select max(fld_index) from mpdb_fldinf where clsid=?",
                      (cid,)).fetchone()
    idx = (row[0] or -1) + 1
    if fld_type == 7:
        leng, msk, pnt = 8, 15, 6
    elif fld_type == 4:
        leng, msk, pnt = 4, 10, 0
    else:
        leng, msk, pnt = 254, 255, 0
    con.execute(
        "INSERT INTO mpdb_fldinf(clsid,table_name,fld_name,fld_index,"
        "fld_leng,msk_leng,pnt_leng,edt_enable,fld_type,alias_name,not_null,"
        "is_must) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (cid, table, field, idx, leng, msk, pnt, 1 if fld_type == 4 else 0,
         fld_type, alias or field, 0, 0))
    con.commit()
    return idx


def drop_field(con: sqlite3.Connection, name: str, field: str) -> None:
    """删除字段(需要 SQLite 3.35+ 的 DROP COLUMN)。"""
    cid = feature_class_id(con, name)
    table = con.execute("select physical_name from mpdb_item where id=?",
                        (cid,)).fetchone()[0]
    con.execute('ALTER TABLE "%s" DROP COLUMN "%s"' % (table, field))
    con.execute("delete from mpdb_fldinf where clsid=? and fld_name=?",
                (cid, field))
    con.commit()


def update_features(con: sqlite3.Connection, name: str,
                    where: Optional[dict] = None,
                    updates: Optional[dict] = None) -> int:
    """按属性条件更新字段值,返回更新条数。

    ``where`` 为 ``{字段: 值}`` 等值匹配(空表示全部);``updates`` 为 ``{字段: 新值}``。
    """
    if not updates:
        return 0
    cid = feature_class_id(con, name)
    table = con.execute("select physical_name from mpdb_item where id=?",
                        (cid,)).fetchone()[0]
    conds, args = [], []
    for k, v in (where or {}).items():
        conds.append('"%s" = ?' % k)
        args.append(v)
    sql = 'UPDATE "%s" SET %s' % (
        table, ", ".join('"%s" = ?' % k for k in updates))
    params = list(updates.values()) + args
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    cur = con.execute(sql, params)
    con.commit()
    return cur.rowcount
