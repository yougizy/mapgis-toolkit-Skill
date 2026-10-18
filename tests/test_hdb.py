# -*- coding: utf-8 -*-
"""HDB 建库 / 写入 / 读取 / 体检 / 导出测试。

需要 MapGIS 空库作为模板,通过环境变量 ``MG_TEMPLATE`` 指定;
未设置时相关测试自动跳过。
可用环境变量 ``MG_TEMPLATE`` 覆盖;模板缺失时跳过。
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mapgis_toolkit import hdb  # noqa: E402

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEMPLATE = os.environ.get("MG_TEMPLATE", "")


@unittest.skipUnless(os.path.exists(TEMPLATE), "缺少 MapGIS 空库模板")
class TestHdb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="mapgis_hdb_")
        cls.db = os.path.join(cls.tmp, "t.hdb")
        con = hdb.new_database(TEMPLATE, cls.db)
        cls.n_region = hdb.add_feature_class(
            con, u"面", "Region",
            [{"parts": [[(113.5, 27.2), (114.0, 27.2), (114.0, 27.8), (113.5, 27.2)]],
              "attrs": {"NAME": u"南昌"}}],
            fields=[("NAME", "TEXT", 0, u"名称")], database_name="t")
        cls.n_line = hdb.add_feature_class(
            con, u"线", "Line",
            [{"parts": [[(113.5, 27.2), (114.0, 27.6)]], "attrs": {"NAME": u"赣江"}}],
            fields=[("NAME", "TEXT", 0, u"名称")], database_name="t")
        cls.n_point = hdb.add_feature_class(
            con, u"点", "Point",
            [{"parts": [[(113.7, 27.3)]], "attrs": {"NAME": u"驻地"}}],
            fields=[("NAME", "TEXT", 0, u"名称")], database_name="t")
        con.close()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _con(self):
        import sqlite3
        return sqlite3.connect(self.db)

    def test_classes(self):
        con = self._con()
        rows = hdb.list_feature_classes(con)
        con.close()
        self.assertEqual(len(rows), 3)
        self.assertEqual({r["name"] for r in rows}, {u"面", u"线", u"点"})

    def test_inspect_ok(self):
        con = self._con()
        report = hdb.inspect(con)
        con.close()
        self.assertTrue(report["ok"], report["problems"])
        self.assertEqual(report["integrity"], "ok")
        for c in report["classes"]:
            self.assertTrue(c["geometry_ok"], c["name"])
            self.assertEqual(c["count"], c["rtree"])

    def test_read_back(self):
        con = self._con()
        feats = hdb.read_features(con, u"面")
        con.close()
        self.assertEqual(len(feats), 1)
        self.assertEqual(feats[0]["geom_type"], "Region")
        self.assertEqual(feats[0]["attrs"]["NAME"], u"南昌")
        self.assertEqual(len(feats[0]["parts"][0]), 4)

    def test_export_shp(self):
        con = self._con()
        out = os.path.join(self.tmp, "out.shp")
        n = hdb.export_shp(con, u"线", out)
        con.close()
        self.assertEqual(n, 1)
        self.assertTrue(os.path.exists(out))

    def test_subtype(self):
        con = self._con()
        rows = {r["name"]: r for r in hdb.list_feature_classes(con)}
        con.close()
        self.assertEqual(rows[u"点"]["subtype"], 1)
        self.assertEqual(rows[u"线"]["subtype"], 2)
        self.assertEqual(rows[u"面"]["subtype"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
