# -*- coding: utf-8 -*-
"""地理运算测试(shapely / pyproj 可选)。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from mapgis_toolkit import ops
except ImportError as e:  # pragma: no cover
    ops = None
    _skip_reason = str(e)
else:
    _skip_reason = ""


@unittest.skipIf(ops is None, _skip_reason or "缺少 shapely")
class TestOps(unittest.TestCase):
    def setUp(self):
        self.poly = [{"parts": [[(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)]], "attrs": {}}]
        self.poly2 = [{"parts": [[(2, 2), (6, 2), (6, 6), (2, 6), (2, 2)]], "attrs": {}}]
        self.line = [{"parts": [[(-1, 2), (5, 2)]], "attrs": {}}]

    def test_clip_line_by_polygon(self):
        out = ops.clip(self.line, "Line", self.poly, "Region")
        self.assertTrue(out)
        xs = [p[0] for ring in out for p in ring["parts"][0]]
        self.assertGreaterEqual(min(xs), -1e-9)
        self.assertLessEqual(max(xs), 4 + 1e-9)

    def test_intersect(self):
        out = ops.intersect(self.poly, "Region", self.poly2, "Region")
        self.assertTrue(out)
        # 交集是 2x2 的正方形
        xs = [p[0] for p in out[0]["parts"][0]]
        self.assertAlmostEqual(max(xs) - min(xs), 2.0, places=6)

    def test_buffer(self):
        out = ops.buffer_features(self.line, "Line", 1.0)
        self.assertTrue(out)
        xs = [p[0] for ring in out for p in ring["parts"][0]]
        self.assertAlmostEqual(min(xs), -2.0, places=6)
        self.assertAlmostEqual(max(xs), 6.0, places=6)

    def test_project(self):
        feats = [{"parts": [[(116.0, 28.0)]], "attrs": {}}]
        out = ops.project(feats, "EPSG:4490", "EPSG:3857")
        x, y = out[0]["parts"][0][0]
        self.assertGreater(x, 1e7)
        self.assertGreater(y, 3e6)

    def test_dissolve(self):
        out = ops.dissolve(self.poly + self.poly2, "Region")
        self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
