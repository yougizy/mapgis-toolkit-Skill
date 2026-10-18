# -*- coding: utf-8 -*-
"""在 MapGIS 安装目录中定位真正的颜色表(搜索已知索引色)。"""
from __future__ import annotations

import os

HOME = os.environ.get("MAPGIS_HOME", r"D:\Program Files\MapGIS 10")
ROOTS = [
    os.path.join(HOME, "Program", "Config"),
    os.path.join(HOME, "Program"),
    os.path.join(HOME, "SLib"),
]

# 已确认的索引色(15/11/158/10 最独特)
TARGETS = {
    "15 粉": (237, 194, 189),
    "11 黄绿": (142, 165, 31),
    "158 浅黄": (255, 243, 145),
    "10 橙": (243, 151, 0),
    "17 粉红": (255, 25, 25),
}


def main() -> None:
    seen = set()
    hits_any = False
    for root in ROOTS:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                path = os.path.join(dirpath, name)
                if path in seen:
                    continue
                seen.add(path)
                try:
                    if os.path.getsize(path) > 4 * 1024 * 1024:
                        continue
                    with open(path, "rb") as f:
                        data = f.read()
                except OSError:
                    continue
                found = []
                for label, (r, g, b) in TARGETS.items():
                    for tag, pat in (("RGB", bytes((r, g, b))),
                                     ("BGR", bytes((b, g, r)))):
                        i = data.find(pat)
                        if i >= 0:
                            found.append("%s@%d(%s)" % (label, i, tag))
                if found:
                    hits_any = True
                    print("%s\n    %s" % (path, " | ".join(found)))
    print("\n扫描文件数:", len(seen))
    if not hits_any:
        print("未找到任何已知索引色")


if __name__ == "__main__":
    main()
