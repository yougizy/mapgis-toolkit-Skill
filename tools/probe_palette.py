# -*- coding: utf-8 -*-
"""尝试解析 MapGIS 系统颜色库 Pcolor.lib。"""
from __future__ import annotations

import os
import struct

PATH = r"D:\Program Files\MapGIS 10\Program\Config\DefaultSystemLib\Slib\Pcolor.lib"


def main() -> None:
    data = open(PATH, "rb").read()
    print("大小:", len(data))
    print("头部:", data[:32])
    print("ASCII:", "".join(chr(b) if 32 <= b < 127 else "." for b in data[:64]))

    # 扫描所有 (255,0,0) 等已知色的位置
    for probe in ((255, 0, 0), (237, 194, 189), (255, 243, 145), (142, 165, 31)):
        pat = bytes(probe)
        pos, hits = 0, []
        while True:
            i = data.find(pat, pos)
            if i < 0:
                break
            hits.append(i)
            pos = i + 1
            if len(hits) >= 8:
                break
        print("%s -> %s" % (probe, hits))

    # 假设 256 条记录,推算记录长度
    n = 256
    for header in (0, 4, 8, 12, 16):
        for rec in (206, 207, 208, 200, 204, 12, 16):
            if header + n * rec == len(data):
                print("候选: header=%d, record=%d" % (header, rec))

    # 把文件按 12 字节步长打印前 40 条的三元组
    print("\n按不同偏移读取 RGB 三元组:")
    for off in (0, 4, 8, 12):
        vals = []
        for i in range(6):
            p = off + i * 12
            if p + 3 <= len(data):
                vals.append(tuple(data[p:p + 3]))
        print("  off=%d step=12: %s" % (off, vals))


if __name__ == "__main__":
    print(os.path.exists(PATH))
    main()
