# -*- coding: utf-8 -*-
"""栅格与网络分析测试(rasterio / networkx 可选)。"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from mapgis_toolkit import network
except ImportError as e:  # pragma: no cover
    network = None
    _net_skip = str(e)
else:
    _net_skip = ""

try:
    from mapgis_toolkit import raster
except ImportError as e:  # pragma: no cover
    raster = None
    _raster_skip = str(e)
else:
    _raster_skip = ""


@unittest.skipIf(network is None, _net_skip or "缺少 networkx")
class TestNetwork(unittest.TestCase):
    def setUp(self):
        self.feats = [
            {"parts": [[(0, 0), (1, 0), (2, 0)]], "attrs": {}},
            {"parts": [[(2, 0), (3, 0)]], "attrs": {}},
            {"parts": [[(10, 10), (11, 10)]], "attrs": {}},  # 孤立段
        ]

    def test_summary(self):
        s = network.summary(self.feats)
        self.assertEqual(s["nodes"], 6)
        self.assertEqual(s["edges"], 4)
        self.assertEqual(s["components"], 2)
        self.assertAlmostEqual(s["total_length"], 4.0)

    def test_shortest_path(self):
        r = network.shortest_path(self.feats, (0, 0), (3, 0))
        self.assertAlmostEqual(r["length"], 3.0)
        self.assertEqual(r["nodes"], 4)

    def test_largest_component(self):
        big = network.largest_component(self.feats)
        self.assertEqual(len(big["parts"]), 2)


@unittest.skipIf(raster is None, _raster_skip or "缺少 rasterio")
class TestRaster(unittest.TestCase):
    def setUp(self):
        try:
            import numpy as np
            import rasterio
            from rasterio.transform import from_origin
        except ImportError as e:
            self.skipTest(str(e))
        self.tmp = tempfile.mkdtemp(prefix="mapgis_raster_")
        self.tif = os.path.join(self.tmp, "t.tif")
        data = np.arange(100, dtype="uint8").reshape(10, 10)
        with rasterio.open(
                self.tif, "w", driver="GTiff", height=10, width=10, count=1,
                dtype="uint8", crs="EPSG:4490",
                transform=from_origin(113.0, 30.0, 0.1, 0.1)) as dst:
            dst.write(data, 1)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_info(self):
        i = raster.info(self.tif)
        self.assertEqual(i["width"], 10)
        self.assertEqual(i["height"], 10)
        self.assertEqual(i["bands"], 1)
        self.assertIn("4490", i["crs"])

    def test_stats(self):
        s = raster.stats(self.tif)
        self.assertAlmostEqual(s["min"], 0.0)
        self.assertAlmostEqual(s["max"], 99.0)

    def test_clip(self):
        out = os.path.join(self.tmp, "clip.tif")
        r = raster.clip(self.tif, out, bbox=(113.0, 29.5, 113.5, 30.0))
        self.assertTrue(r["ok"])
        self.assertEqual(r["width"], 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
