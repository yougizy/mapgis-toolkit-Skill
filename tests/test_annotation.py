# -*- coding: utf-8 -*-
"""注记类与三维几何测试。"""

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mapgis_toolkit import annotation, hdb, three_d  # noqa: E402

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEMPLATE = os.environ.get("MG_TEMPLATE", "")


class TestThreeD(unittest.TestCase):
    def test_roundtrip(self):
        parts = [
            [(538537.33, 3371901.6, 84.0), (538540.0, 3371902.0, 84.0),
             (538541.0, 3371905.0, 84.0), (538537.33, 3371901.6, 84.0)],
            [(538550.0, 3371910.0, 90.0), (538555.0, 3371912.0, 90.0)],
        ]
        blob = three_d.encode_shape3d(parts)
        decoded = three_d.decode_shape3d(blob)
        self.assertEqual(len(decoded), 2)
        self.assertEqual(len(decoded[0]), 4)
        self.assertAlmostEqual(decoded[0][0][0], 538537.33, places=6)
        self.assertAlmostEqual(decoded[1][1][2], 90.0, places=6)

    def test_bbox(self):
        parts = [[(0, 0, 0), (10, 20, 5)]]
        self.assertEqual(three_d.bbox3d(parts), (0, 0, 0, 10, 20, 5))

    def test_bad_marker(self):
        with self.assertRaises(three_d.ThreeDError):
            three_d.decode_shape3d(b"\x00" * 16)


@unittest.skipUnless(os.path.exists(TEMPLATE), "缺少 MapGIS 空库模板")
class TestAnnotationClass(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mapgis_ann_")
        self.db = os.path.join(self.tmp, "t.hdb")
        con = hdb.new_database(TEMPLATE, self.db)
        con.close()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_read_delete(self):
        con = sqlite3.connect(self.db)
        table = annotation.add_annotation_class(
            con, u"注记", [
                {"x": 116.0, "y": 28.6, "text": u"南昌", "color": 6, "height": 12},
                {"x": 115.0, "y": 27.8, "text": u"吉安", "color": 6, "height": 10},
            ], "t")
        self.assertEqual(table, "mpa1")
        items = annotation.read_annotations(con, u"注记")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["text"], u"南昌")
        annotation.delete_annotation_class(con, u"注记")
        self.assertEqual(annotation.list_annotation_classes(con), [])
        con.close()
        con = sqlite3.connect(self.db)
        report = hdb.inspect(con)
        con.close()
        self.assertTrue(report["ok"], report["problems"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
