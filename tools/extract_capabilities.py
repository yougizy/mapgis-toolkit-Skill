# -*- coding: utf-8 -*-
"""从 MapGIS Desktop 帮助文档提取功能目录,用于生成覆盖矩阵。

用法:  python tools/extract_capabilities.py [--json out.json]
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys

DEFAULT_DOC = __import__("os").path.join(
    __import__("os").environ.get("MAPGIS_HOME", r"D:\Program Files\MapGIS 10"),
    "Documentation", "MapGISDesktop", "operation")


def text_of(path: str) -> str:
    for enc in ("utf-8", "gb18030"):
        try:
            with open(path, "rb") as f:
                return f.read().decode(enc)
        except UnicodeDecodeError:
            continue
    with open(path, "rb") as f:
        return f.read().decode("utf-8", "replace")


def headings(raw: str):
    """提取 h1-h4 标题文本。"""
    out = []
    for m in re.finditer(r"<h([1-4])[^>]*>(.*?)</h\1>", raw, flags=re.S):
        txt = re.sub(r"<[^>]+>", "", m.group(2))
        txt = html.unescape(txt).strip()
        if txt and txt not in ("此页内容",):
            out.append(txt)
    return out


def walk(root: str) -> dict:
    result = {}
    for dirpath, _dirs, files in os.walk(root):
        rel = os.path.relpath(dirpath, root).replace("\\", "/")
        for name in sorted(files):
            if not name.lower().endswith(".html"):
                continue
            if name in ("index.html", "Template.html"):
                continue
            path = os.path.join(dirpath, name)
            hs = headings(text_of(path))
            if not hs:
                continue
            key = (rel + "/" + name).lstrip("./")
            result[key] = hs[:40]
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", default=DEFAULT_DOC)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    if not os.path.isdir(args.doc):
        print("帮助文档目录不存在:", args.doc)
        return 1
    data = walk(args.doc)

    total = 0
    for page, hs in data.items():
        print("==", page)
        for h in hs:
            print("   -", h)
            total += 1
    print("\n页面数: %d, 功能标题数: %d" % (len(data), total))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("已写出:", args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
