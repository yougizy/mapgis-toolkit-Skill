# -*- coding: utf-8 -*-
"""HDB 扩展能力测试:增删改查、空间查询、统计。"""

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mapgis_toolkit import hdb  # noqa: E402

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEMPLATE = os.environ.get("MG_TEMPLATE", "")


@unittest.skipUnless(os.path.exists(TEMPLATE), "缺少 MapGIS 空库模板")
class TestHdbCrud(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mapgis_crud_")
        self.db = os.path.join(self.tmp, "t.hdb")
        con = hdb.new_database(TEMPLATE, self.db)
        hdb.add_feature_class(
            con, u"城市", "Point",
            [{"parts": [[(113.5, 27.2)]], "attrs": {"NAME": u"南昌", "POP": "600"}},
             {"parts": [[(114.1, 26.8)]], "attrs": {"NAME": u"吉安", "POP": "450"}},
             {"parts": [[(115.0, 28.0)]], "attrs": {"NAME": u"宜春", "POP": "500"}}],
            fields=[("NAME", "TEXT", 0, u"名称"), ("POP", "TEXT", 0, u"人口")],
            database_name="t")
        con.close()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _con(self):
        return sqlite3.connect(self.db)

    def test_query_equality(self):
        con = self._con()
        feats = hdb.query_features(con, u"城市", {"NAME": u"南昌"})
        con.close()
        self.assertEqual(len(feats), 1)
        self.assertEqual(feats[0]["attrs"]["NAME"], u"南昌")

    def test_query_in_and_limit(self):
        con = self._con()
        feats = hdb.query_features(con, u"城市", {"NAME": [u"南昌", u"宜春"]})
        limited = hdb.query_features(con, u"城市", limit=2)
        con.close()
        self.assertEqual(len(feats), 2)
        self.assertEqual(len(limited), 2)

    def test_spatial_query(self):
        con = self._con()
        feats = hdb.spatial_query(con, u"城市", [114.0, 26.5, 114.5, 27.0])
        con.close()
        self.assertEqual(len(feats), 1)
        self.assertEqual(feats[0]["attrs"]["NAME"], u"吉安")

    def test_stats(self):
        con = self._con()
        s = hdb.feature_stats(con, u"城市", "POP")
        con.close()
        self.assertEqual(s["count"], 3)
        self.assertEqual(s["numeric"]["max"], 600.0)
        self.assertEqual(s["numeric"]["min"], 450.0)

    def test_rename_and_delete(self):
        con = self._con()
        hdb.rename_feature_class(con, u"城市", u"城镇")
        names = {r["name"] for r in hdb.list_feature_classes(con)}
        self.assertIn(u"城镇", names)
        hdb.delete_feature_class(con, u"城镇")
        report = hdb.inspect(con)
        con.close()
        self.assertEqual(report["classes"], [])
        self.assertTrue(report["ok"], report["problems"])


@unittest.skipUnless(os.path.exists(os.path.join(
    os.path.dirname(__file__), "..", "src")), "包路径缺失")
class TestMcpImport(unittest.TestCase):
    def test_import_server(self):
        try:
            from mapgis_toolkit import mcp_server
        except ImportError as e:
            self.skipTest("未安装 mcp: %s" % e)
        self.assertTrue(hasattr(mcp_server, "mcp"))
        for name in ("hdb_list_classes", "hdb_inspect", "hdb_export_shp",
                     "hdb_import_shp", "hdb_query", "hdb_stats",
                     "mapx_build", "mapx_color_card"):
            self.assertTrue(hasattr(mcp_server, name), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
