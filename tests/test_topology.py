# -*- coding: utf-8 -*-
"""拓扑检查测试(shapely 可选)。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from mapgis_toolkit import topology
except ImportError as e:  # pragma: no cover
    topology = None
    _skip = str(e)
else:
    _skip = ""


@unittest.skipIf(topology is None, _skip or "缺少 shapely")
class TestTopology(unittest.TestCase):
    def test_valid_polygons(self):
        feats = [
            {"oid": 1, "parts": [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]]},
            {"oid": 2, "parts": [[(2, 0), (3, 0), (3, 1), (2, 1), (2, 0)]]},
        ]
        r = topology.run_all(feats, "Region")
        self.assertTrue(r["ok"], r)

    def test_overlap_detected(self):
        feats = [
            {"oid": 1, "parts": [[(0, 0), (3, 0), (3, 3), (0, 3), (0, 0)]]},
            {"oid": 2, "parts": [[(2, 2), (5, 2), (5, 5), (2, 5), (2, 2)]]},
        ]
        r = topology.check_overlaps(feats)
        self.assertFalse(r["ok"])
        self.assertEqual(r["issues"][0]["type"], "overlap")

    def test_duplicate_polygon(self):
        ring = [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]
        r = topology.check_geometries(
            [{"oid": 1, "parts": [ring]}, {"oid": 2, "parts": [ring]}], "Region")
        self.assertFalse(r["ok"])
        self.assertEqual(r["issues"][0]["type"], "duplicate")

    def test_dangles(self):
        feats = [
            {"oid": 1, "parts": [[(0, 0), (1, 0)]]},
            {"oid": 2, "parts": [[(1, 0), (2, 0)]]},
        ]
        r = topology.check_line_dangles(feats)
        # 两个端点各只连 1 条线:(0,0) 和 (2,0)
        self.assertEqual(r["count"], 2)

    def test_duplicate_points(self):
        feats = [{"oid": 1, "parts": [[(1.0, 2.0)]]},
                 {"oid": 2, "parts": [[(1.0, 2.0)]]}]
        r = topology.check_points_duplicate(feats)
        self.assertEqual(r["count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
