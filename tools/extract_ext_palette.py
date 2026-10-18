# -*- coding: utf-8 -*-
"""从 PColor_EXT.lib 提取 1640 色扩展调色板 -> JSON。

格式:12 字节头 + N×3 字节 RGB。
"""
from __future__ import annotations

import json
import os
import sys

BASE = os.path.join(os.environ.get("MAPGIS_HOME", r"D:\Program Files\MapGIS 10"),
                    "Program", "Config", "DefaultSystemLib", "Slib")
SRC = os.path.join(BASE, "PColor_EXT.lib")


def extract(path: str = SRC, header: int = 12):
    data = open(path, "rb").read()
    body = data[header:]
    return [(body[i], body[i + 1], body[i + 2]) for i in range(0, len(body) - 2, 3)]


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs", "palette_ext.json")
    colors = extract()
    with open(out, "w", encoding="utf-8") as f:
        json.dump([list(c) for c in colors], f, ensure_ascii=False, indent=0)
    print("已提取 %d 色 -> %s" % (len(colors), out))
    print("前 10:", colors[:10])
    return 0


if __name__ == "__main__":
    sys.exit(main())
