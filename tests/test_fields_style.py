# -*- coding: utf-8 -*-
"""字段/属性维护、线抽稀、样式提取测试。"""

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mapgis_toolkit import geometry, hdb, style  # noqa: E402

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEMPLATE = os.environ.get("MG_TEMPLATE", "")


class TestSimplify(unittest.TestCase):
    def test_straight_line(self):
        pts = [(0, 0), (1, 0.0001), (2, 0), (3, 0)]
        out = geometry.simplify(pts, 0.01)
        self.assertEqual(out[0], (0, 0))
        self.assertEqual(out[-1], (3, 0))
        self.assertLess(len(out), len(pts))

    def test_keep_shape(self):
        pts = [(0, 0), (1, 1), (2, 0)]
        out = geometry.simplify(pts, 0.01)
        self.assertEqual(len(out), 3, "尖角应保留")

    def test_zero_tolerance(self):
        pts = [(0, 0), (1, 1), (2, 0)]
        self.assertEqual(geometry.simplify(pts, 0), pts)


@unittest.skipUnless(os.path.exists(TEMPLATE), "缺少 MapGIS 空库模板")
class TestFields(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mapgis_field_")
        self.db = os.path.join(self.tmp, "t.hdb")
        con = hdb.new_database(TEMPLATE, self.db)
        hdb.add_feature_class(
            con, u"点", "Point",
            [{"parts": [[(1.0, 2.0)]], "attrs": {"NAME": u"甲"}}],
            fields=[("NAME", "TEXT", 0, u"名称")], database_name="t")
        con.close()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _con(self):
        return sqlite3.connect(self.db)

    def test_add_and_drop_field(self):
        con = self._con()
        hdb.add_field(con, u"点", "CODE", "TEXT", 0, u"编码")
        cols = [r[1] for r in con.execute("PRAGMA table_info(mpf1)")]
        self.assertIn("CODE", cols)
        hdb.drop_field(con, u"点", "CODE")
        cols = [r[1] for r in con.execute("PRAGMA table_info(mpf1)")]
        self.assertNotIn("CODE", cols)
        con.close()

    def test_update_features(self):
        con = self._con()
        hdb.add_field(con, u"点", "POP", "REAL", 7, u"人口")
        n = hdb.update_features(con, u"点", {"NAME": u"甲"}, {"POP": 123})
        self.assertEqual(n, 1)
        feats = hdb.read_features(con, u"点")
        con.close()
        self.assertEqual(feats[0]["attrs"]["POP"], 123)


class TestStyle(unittest.TestCase):
    XML = (
        u'<subnode name="测试" type="SFeatureLayer" geometryType="3" '
        u'class="CreateGLayer@GisCartoPrj.dll">'
        u'<geoInfo><regInfo lib="0" id="0" fillclr="15" patclr="3" '
        u'outpenw="0.5" fillmode="0"></regInfo></geoInfo>'
        u'<label name="noname" type="SimpleLabel"><state>VISIBLE</state>'
        u'<labelExpression>NAME</labelExpression>'
        u'<annInfo height="11" iclr="6"></annInfo></label>'
        u'</subnode>'
    )

    def test_extract(self):
        s = style.layer_style_from_xml(self.XML)
        self.assertEqual(s["name"], u"测试")
        self.assertEqual(s["geometry_type"], "3")
        self.assertEqual(s["fill"]["fillclr"], "15")
        self.assertEqual(s["label"]["expression"], "NAME")
        self.assertEqual(s["label"]["color"], "6")

    def test_roundtrip_file(self):
        tmp = tempfile.mkdtemp(prefix="mapgis_style_")
        try:
            path = os.path.join(tmp, "styles.json")
            style.save_styles([style.layer_style_from_xml(self.XML)], path)
            loaded = style.load_styles(path)
            self.assertEqual(loaded[0]["fill"]["fillclr"], "15")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
