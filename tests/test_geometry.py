# -*- coding: utf-8 -*-
"""几何编解码测试。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mapgis_toolkit import geometry  # noqa: E402


class TestGeometry(unittest.TestCase):
    def test_point_roundtrip(self):
        b = geometry.encode_point(113.5, 27.2)
        self.assertEqual(len(b), 28)
        x, y, z = geometry.decode_point(b)
        self.assertAlmostEqual(x, 113.5, places=9)
        self.assertAlmostEqual(y, 27.2, places=9)
        self.assertEqual(z, 0.0)

    def test_line_roundtrip(self):
        pts = [(113.5, 27.2), (114.123456789, 27.987654321)]
        b = geometry.encode_line(pts)
        self.assertEqual(len(b), 6 + len(pts) * 16)
        self.assertEqual(b[2], len(pts))  # 头第 3 字节为点数
        self.assertEqual(geometry.decode_line(b), pts)

    def test_region_roundtrip(self):
        pts = [(113.5, 27.2), (114.0, 27.2), (114.0, 27.8), (113.5, 27.2)]
        b = geometry.encode_region(pts)
        self.assertEqual(len(b), 15 + len(pts) * 16)
        self.assertEqual(geometry.decode_region(b), pts)

    def test_decode_dispatch(self):
        self.assertEqual(geometry.decode(geometry.encode_point(1, 2), 1), [(1, 2)])
        self.assertEqual(geometry.decode(geometry.encode_region([(0, 0), (1, 0), (1, 1)]), 8),
                         [(0, 0), (1, 0), (1, 1)])

    def test_split_line(self):
        pts = [(float(i), float(i)) for i in range(600)]
        segs = geometry.split_line(pts)
        self.assertGreater(len(segs), 1)
        self.assertTrue(all(len(s) <= geometry.MAX_LINE_POINTS for s in segs))
        for a, b in zip(segs, segs[1:]):
            self.assertEqual(a[-1], b[0])

    def test_line_point_limit(self):
        with self.assertRaises(geometry.GeometryError):
            geometry.encode_line([(0.0, 0.0)] * (geometry.MAX_LINE_POINTS + 1))

    def test_bbox_and_centroid(self):
        pts = [(0, 0), (2, 0), (2, 2), (0, 2)]
        self.assertEqual(geometry.bbox(pts), (0, 0, 2, 2))
        cx, cy = geometry.centroid(pts)
        self.assertAlmostEqual(cx, 1.0, places=9)
        self.assertAlmostEqual(cy, 1.0, places=9)
        self.assertAlmostEqual(abs(geometry.ring_area(pts)), 4.0, places=9)
        self.assertAlmostEqual(geometry.ring_perimeter(pts), 8.0, places=9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
