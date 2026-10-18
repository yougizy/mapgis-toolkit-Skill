"""颜色编码与 MapGIS 系统颜色库索引。

实测结论(重要):

* ``regInfo.fillclr`` / ``linInfo.outclr`` 只接受**颜色库索引**(小整数)。
* 真彩色 ``0x00BBGGRR`` 会被当作"索引 13816569"→ 渲染成黑。
* 真彩色 ``0x01BBGGRR`` 同样被拒 → 全黑。
* 唯一可靠的取色方式是颜色库索引,而索引→RGB **没有公开文档**。

``KNOWN_INDEX_RGB`` 取自 MapGIS 自带
``Program/Config/DataManage/RegFillColorConfig.xml`` 的注释,是少数可确认的索引。

`Pcolor.lib` 的结构为 ``28 字节头 + 256 条 × 206 字节``,每条记录内含
**68 个 RGB 色阶**(68×3+2=206),与"索引→颜色"不是一一对应,
因此无法直接解析出完整索引表。

## 配色校准流程

1. ``mapgis-toolkit color-card card.mapx`` 生成索引色卡
2. 在 MapGIS 中打开并导出 PNG
3. ``mapgis-toolkit color-probe card.png --out palette.json``
   → ``{索引: [r,g,b]}``
4. ``colors.load_palette(palette.json)`` 后用 ``nearest_index(rgb, palette)``
   把任意参考色映射到最接近的索引
"""

from __future__ import annotations

import json
from typing import Dict, Optional, Tuple

#: 已确认的 索引 -> RGB
KNOWN_INDEX_RGB: Dict[int, Tuple[int, int, int]] = {
    6: (255, 0, 0),
    10: (243, 151, 0),
    11: (142, 165, 31),
    15: (237, 194, 189),
    17: (255, 25, 25),
    18: (255, 50, 50),
    19: (255, 75, 75),
    20: (255, 100, 100),
    22: (255, 130, 130),
    34: (255, 91, 75),
    35: (255, 113, 100),
    36: (255, 127, 115),
    37: (255, 141, 130),
    158: (255, 243, 145),
}

#: 参考图「江西省地图(政区版)」的取样色
REFERENCE_ZONE_RGB: Dict[str, Tuple[int, int, int]] = {
    "南昌市": (252, 228, 236),
    "九江市": (211, 233, 213),
    "景德镇市": (252, 243, 212),
    "上饶市": (247, 216, 216),
    "鹰潭市": (209, 238, 213),
    "新余市": (216, 237, 216),
    "萍乡市": (216, 237, 216),
    "宜春市": (245, 214, 214),
    "抚州市": (251, 226, 205),
    "吉安市": (255, 245, 209),
    "赣州市": (213, 229, 213),
}

#: 参考图水系色
REFERENCE_WATER_RGB: Tuple[int, int, int] = (168, 211, 240)

#: 真彩色标志位;实测 MapGIS 不接受,保留常量供实验
TRUE_COLOR_FLAG = 0x01000000


def hex_to_rgb(hexrgb: str) -> Tuple[int, int, int]:
    """``'#RRGGBB'`` -> ``(r, g, b)``。"""
    h = hexrgb.lstrip("#")
    if len(h) != 6:
        raise ValueError("颜色格式应为 #RRGGBB: %r" % hexrgb)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """``(r, g, b)`` -> ``'#RRGGBB'``。"""
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(v))) for v in rgb)


def bgr(hexrgb: str, flag: int = 0) -> int:
    """``'#RRGGBB'`` -> MapGIS 数值 ``flag | 0x00BBGGRR``。

    注意:实测 ``flag=0`` 与 ``flag=0x01000000`` 都会被 MapGIS 拒绝(渲染黑),
    本函数保留用于生成"待定标"的颜色值或其它 MapGIS 产品。
    """
    r, g, b = hex_to_rgb(hexrgb)
    return flag | (b << 16) | (g << 8) | r


def index_rgb(index: int) -> Optional[Tuple[int, int, int]]:
    """查询已知索引的 RGB,未知返回 ``None``。"""
    return KNOWN_INDEX_RGB.get(index)


def nearest_index(rgb: Tuple[int, int, int],
                  palette: Optional[Dict[int, Tuple[int, int, int]]] = None
                  ) -> Optional[int]:
    """在色表中找最接近的索引(欧氏距离)。

    ``palette`` 为空时使用 :data:`KNOWN_INDEX_RGB`(只有 14 个已确认色),
    传入 ``color_probe`` 生成的完整色表可获得准确结果。
    """
    table = palette or KNOWN_INDEX_RGB
    best = None
    best_d = None
    for idx, ref in table.items():
        d = sum((a - b) ** 2 for a, b in zip(rgb, ref))
        if best_d is None or d < best_d:
            best, best_d = idx, d
    return best


def load_palette(path: str) -> Dict[int, Tuple[int, int, int]]:
    """读取 ``color_probe`` 生成的 ``palette.json``。"""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {int(k): tuple(v) for k, v in raw.items()}


def save_palette(palette: Dict[int, Tuple[int, int, int]], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({str(k): list(v) for k, v in palette.items()}, f,
                  ensure_ascii=False, indent=1)


def resolve_zone_indices(palette: Optional[Dict[int, Tuple[int, int, int]]] = None,
                         zone: Optional[Dict[str, Tuple[int, int, int]]] = None
                         ) -> Dict[str, int]:
    """把参考图的 11 个市色映射为索引。

    无 ``palette`` 时退化为"相邻市尽量不同色"的已知索引分配。
    """
    zone = zone or REFERENCE_ZONE_RGB
    if palette:
        out: Dict[str, int] = {}
        used = set()
        for name, rgb in zone.items():
            idx = nearest_index(rgb, palette)
            # 避免相邻市撞色:已被占用则取次近
            if idx in used:
                ranked = sorted(palette.items(),
                                key=lambda kv: sum((a - b) ** 2
                                                   for a, b in zip(rgb, kv[1])))
                for cand, _ in ranked:
                    if cand not in used:
                        idx = cand
                        break
            used.add(idx)
            out[name] = idx
        return out

    # 无精确色表:用已知色按色相近似分配(与参考图相比偏深,但可区分)
    fallback = ["南昌市", "九江市", "景德镇市", "上饶市", "鹰潭市",
                "新余市", "萍乡市", "宜春市", "抚州市", "吉安市", "赣州市"]
    order = [15, 11, 158, 37, 36, 22, 35, 34, 10, 158, 11]
    return dict(zip(fallback, order))


# ---------------------------------------------------------------------------
# 系统色库文件
# ---------------------------------------------------------------------------

#: 扩展色库(明文 RGB):12 字节头 + N×3 字节
EXT_LIB_RELATIVE = ("Program", "Config", "DefaultSystemLib", "Slib", "PColor_EXT.lib")


def ext_palette_path(mapgis_home: Optional[str] = None) -> str:
    """返回 ``PColor_EXT.lib`` 的路径。"""
    import os
    home = mapgis_home or os.environ.get("MAPGIS_HOME", r"D:\Program Files\MapGIS 10")
    return os.path.join(home, *EXT_LIB_RELATIVE)


def load_ext_palette(mapgis_home: Optional[str] = None,
                     path: Optional[str] = None) -> Tuple[Tuple[int, int, int], ...]:
    """解析扩展色库 ``PColor_EXT.lib``(明文 1640 色)。

    注意:这是**扩展色**,不含基础 256 色(6/17/158 等)。
    基础色表 ``Pcolor.lib`` 为编码存储,无法直接解析。
    """
    src = path or ext_palette_path(mapgis_home)
    with open(src, "rb") as f:
        data = f.read()
    body = data[12:]
    return tuple((body[i], body[i + 1], body[i + 2])
                 for i in range(0, len(body) - 2, 3))


def ext_nearest(rgb: Tuple[int, int, int],
                palette: Optional[Tuple[Tuple[int, int, int], ...]] = None
                ) -> Tuple[int, Tuple[int, int, int]]:
    """在扩展色库中找最接近的颜色,返回 ``(序号, RGB)``。"""
    table = palette if palette is not None else load_ext_palette()
    best_i, best_d = 0, None
    for i, ref in enumerate(table):
        d = sum((a - b) ** 2 for a, b in zip(rgb, ref))
        if best_d is None or d < best_d:
            best_i, best_d = i, d
    return best_i, table[best_i]
