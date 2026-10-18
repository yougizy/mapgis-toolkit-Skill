# -*- coding: utf-8 -*-
"""GeoJSON 读写测试。"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mapgis_toolkit import geojson  # noqa: E402


class TestGeoJson(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mapgis_geojson_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _roundtrip(self, kind, feats):
        path = os.path.join(self.tmp, "t.geojson")
        n = geojson.write_geojson(path, feats, kind=kind)
        self.assertEqual(n, len(feats))
        return geojson.read_geojson(path)

    def test_point(self):
        feats = [{"parts": [[(113.5, 27.2)]], "attrs": {"NAME": u"南昌"}}]
        out = self._roundtrip("Point", feats)
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0]["parts"][0][0][0], 113.5, places=9)
        self.assertEqual(out[0]["attrs"]["NAME"], u"南昌")

    def test_line(self):
        feats = [{"parts": [[(113.5, 27.2), (114.0, 27.6)]], "attrs": {"N": "a"}}]
        out = self._roundtrip("Line", feats)
        self.assertEqual(len(out[0]["parts"][0]), 2)

    def test_polygon_closes_ring(self):
        ring = [(113.5, 27.2), (114.0, 27.2), (114.0, 27.8)]
        out = self._roundtrip("Region", [{"parts": [ring], "attrs": {}}])
        pts = out[0]["parts"][0]
        self.assertEqual(pts[0], pts[-1], "闭合环首尾应相同")

    def test_multipolygon(self):
        r1 = [(0, 0), (1, 0), (1, 1), (0, 0)]
        r2 = [(2, 2), (3, 2), (3, 3), (2, 2)]
        out = self._roundtrip("Region", [{"parts": [r1, r2], "attrs": {}}])
        self.assertEqual(len(out[0]["parts"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
