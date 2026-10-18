"""颜色库索引取色:从色卡截图/导出的 PNG 自动建立 索引 -> RGB 表。

流程:
    1. `mapgis-toolkit color-card card.mapx` 生成色卡
    2. 在 MapGIS 中打开并导出为 PNG(或用截图)
    3. `mapgis-toolkit color-probe card.png --cols 16 --rows 8` 
       自动读取每个色块中心像素,得到索引 -> RGB

色卡布局需与生成时一致(默认 16 列、起始 4mm/14mm、单元 12.6×33mm、页面 210×297mm)。
"""

from __future__ import annotations

import json
from typing import Dict, List, Tuple

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover
    raise ImportError("需要 Pillow:pip install pillow") from exc


class ColorProbeError(RuntimeError):
    """色卡取色异常。"""


def extract_palette(png_path: str, cols: int = 16, rows: int = 8,
                    page_w_mm: float = 210.0, page_h_mm: float = 297.0,
                    x0_mm: float = 4.0, y0_mm: float = 14.0,
                    cw_mm: float = 12.6, ch_mm: float = 33.0,
                    swatch_top_mm: float = 9.0, swatch_inset_mm: float = 2.0,
                    page_margin_px: int = 0) -> Dict[int, Tuple[int, int, int]]:
    """读取色卡 PNG,返回 ``{索引: (r, g, b)}``。

    色块几何(与 ``cli color-card`` 一致):
        第 i 个色块左上角 =(x0 + c*cw, y0 + (rows-1-r)*ch),
        色块区域 = 该单元上方 9mm 起、右侧留 2mm。
    """
    img = Image.open(png_path).convert("RGB")
    W, H = img.size
    if page_margin_px:
        W -= page_margin_px * 2
        H -= page_margin_px * 2
        ox = oy = page_margin_px
    else:
        ox = oy = 0

    sx = W / page_w_mm
    sy = H / page_h_mm

    def to_px(x_mm: float, y_mm: float) -> Tuple[int, int]:
        # 版面原点在左下角,图片原点在左上角
        return int(ox + x_mm * sx), int(oy + (page_h_mm - y_mm) * sy)

    palette: Dict[int, Tuple[int, int, int]] = {}
    for i in range(cols * rows):
        r, c = divmod(i, cols)
        x_mm = x0_mm + c * cw_mm
        y_mm = y0_mm + (rows - 1 - r) * ch_mm
        # 色块中心:色块从 y+9 到 y+ch-2,右侧留 2mm
        cx_mm = x_mm + (cw_mm - swatch_inset_mm) / 2.0
        cy_mm = y_mm + (swatch_top_mm + ch_mm - 2.0) / 2.0
        px, py = to_px(cx_mm, cy_mm)
        if not (0 <= px < img.width and 0 <= py < img.height):
            continue
        palette[i] = img.getpixel((px, py))
    return palette


def save_palette(palette: Dict[int, Tuple[int, int, int]], out_json: str) -> None:
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({str(k): list(v) for k, v in palette.items()}, f,
                  ensure_ascii=False, indent=1)


def load_palette(path: str) -> Dict[int, Tuple[int, int, int]]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {int(k): tuple(v) for k, v in raw.items()}


def nearest(palette: Dict[int, Tuple[int, int, int]],
            rgb: Tuple[int, int, int]) -> Tuple[int, int]:
    """在色表中找最接近的索引,返回 ``(索引, 距离平方)``。"""
    best = None
    for idx, ref in palette.items():
        d = sum((a - b) ** 2 for a, b in zip(rgb, ref))
        if best is None or d < best[1]:
            best = (idx, d)
    if best is None:
        raise ColorProbeError("色表为空")
    return best
