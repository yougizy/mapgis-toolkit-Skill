# -*- coding: utf-8 -*-
"""配色映射测试。"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mapgis_toolkit import colors  # noqa: E402


class TestColors(unittest.TestCase):
    def test_nearest_known(self):
        self.assertEqual(colors.nearest_index((255, 0, 0)), 6)
        self.assertEqual(colors.nearest_index((255, 243, 145)), 158)

    def test_nearest_custom_palette(self):
        palette = {1: (250, 250, 250), 2: (10, 10, 10)}
        self.assertEqual(colors.nearest_index((9, 9, 9), palette), 2)
        self.assertEqual(colors.nearest_index((245, 245, 245), palette), 1)

    def test_hex_roundtrip(self):
        rgb = colors.hex_to_rgb("#A8D3F0")
        self.assertEqual(rgb, (168, 211, 240))
        self.assertEqual(colors.rgb_to_hex(rgb), "#A8D3F0")

    def test_zone_fallback_distinct_neighbors(self):
        idx = colors.resolve_zone_indices(None)
        self.assertEqual(len(idx), 11)
        # 已知索引范围内
        for v in idx.values():
            self.assertIn(v, colors.KNOWN_INDEX_RGB)
        # 南昌与九江相邻,颜色应不同
        self.assertNotEqual(idx[u"南昌市"], idx[u"九江市"])

    def test_zone_with_palette(self):
        palette = {i: (i, i, i) for i in range(11)}
        idx = colors.resolve_zone_indices(palette)
        self.assertEqual(len(set(idx.values())), 11, "11 个市应拿到 11 个不同索引")

    def test_palette_roundtrip(self):
        tmp = tempfile.mkdtemp(prefix="mapgis_palette_")
        try:
            path = os.path.join(tmp, "palette.json")
            colors.save_palette({0: (255, 255, 255), 6: (255, 0, 0)}, path)
            loaded = colors.load_palette(path)
            self.assertEqual(loaded[6], (255, 0, 0))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_reference_colors_present(self):
        self.assertEqual(len(colors.REFERENCE_ZONE_RGB), 11)
        self.assertEqual(colors.REFERENCE_WATER_RGB, (168, 211, 240))

    def test_ext_palette(self):
        if not os.path.exists(colors.ext_palette_path()):
            self.skipTest("未安装 MapGIS 或缺少 PColor_EXT.lib")
        table = colors.load_ext_palette()
        self.assertEqual(len(table), 1640)
        self.assertEqual(table[0], (0, 0, 255))
        self.assertEqual(table[1], (255, 0, 0))

    def test_ext_nearest(self):
        if not os.path.exists(colors.ext_palette_path()):
            self.skipTest("未安装 MapGIS 或缺少 PColor_EXT.lib")
        i, rgb = colors.ext_nearest((190, 226, 249))
        self.assertEqual(rgb, (190, 226, 249))
        self.assertGreaterEqual(i, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
