# -*- coding: utf-8 -*-
"""Shapefile 读写测试(点/线/面 roundtrip)。"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mapgis_toolkit import shp  # noqa: E402


class TestShp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mapgis_shp_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _roundtrip(self, shape_type, features, fields):
        path = os.path.join(self.tmp, "t.shp")
        shp.write_shp(path, shape_type, features, fields=fields,
                      prj_wkt='GEOGCS["CGCS2000"]')
        st, feats = shp.read_shp(path)
        self.assertEqual(st, shape_type)
        self.assertEqual(len(feats), len(features))
        return feats

    def test_point(self):
        feats = [{"parts": [[(113.5, 27.2)]], "attrs": {"NAME": u"南昌"}},
                 {"parts": [[(114.1, 26.8)]], "attrs": {"NAME": u"吉安"}}]
        out = self._roundtrip(shp.SHAPE_POINT, feats, ["NAME"])
        self.assertAlmostEqual(out[0]["parts"][0][0][0], 113.5, places=9)
        self.assertEqual(out[0]["attrs"]["NAME"], u"南昌")

    def test_polyline(self):
        feats = [{"parts": [[(113.5, 27.2), (114.0, 27.6), (114.5, 27.9)]],
                  "attrs": {"NAME": u"赣江"}}]
        out = self._roundtrip(shp.SHAPE_POLYLINE, feats, ["NAME"])
        self.assertEqual(len(out[0]["parts"][0]), 3)
        self.assertEqual(out[0]["attrs"]["NAME"], u"赣江")

    def test_polygon_multipart(self):
        ring1 = [(113.5, 27.2), (114.0, 27.2), (114.0, 27.8), (113.5, 27.2)]
        ring2 = [(115.0, 28.0), (115.5, 28.0), (115.5, 28.4), (115.0, 28.0)]
        feats = [{"parts": [ring1, ring2], "attrs": {"NAME": u"九江"}}]
        out = self._roundtrip(shp.SHAPE_POLYGON, feats, ["NAME"])
        self.assertEqual(len(out[0]["parts"]), 2)
        self.assertEqual(out[0]["parts"][0], ring1)

    def test_shx_exists(self):
        path = os.path.join(self.tmp, "s.shp")
        shp.write_shp(path, shp.SHAPE_POINT,
                      [{"parts": [[(1.0, 2.0)]], "attrs": {"A": "1"}}], fields=["A"])
        for ext in (".shp", ".shx", ".dbf"):
            self.assertTrue(os.path.exists(os.path.join(self.tmp, "s" + ext)), ext)


if __name__ == "__main__":
    unittest.main(verbosity=2)
