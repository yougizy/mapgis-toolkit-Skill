"""图层样式提取与应用。

`mapx` 里每个图层的样式都写在 `<regInfo>/<linInfo>/<pntInfo>` 与 `<label>` 里。
本模块把样式抽成 JSON,便于:
    - 从既有 `.mapx` 导出样式集,复用到新图层
    - 在项目间共享配色/标注规则
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional


def _attr(tag: str, name: str) -> Optional[str]:
    m = re.search(r'\b%s="([^"]*)"' % re.escape(name), tag)
    return m.group(1) if m else None


def _first(text: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, text, flags=re.S)
    return m.group(0) if m else None


def layer_style_from_xml(xml: str) -> dict:
    """从单个图层节点的 XML 提取样式。"""
    name = _attr(_first(xml, r"<subnode\b[^>]*>") or "", "name") or ""
    gt = _attr(_first(xml, r"<subnode\b[^>]*>") or "", "geometryType") or ""

    style: dict = {"name": name, "geometry_type": gt}

    reg = _first(xml, r"<regInfo\b[^>]*>")
    if reg:
        style["fill"] = {
            "fillclr": _attr(reg, "fillclr"),
            "patclr": _attr(reg, "patclr"),
            "outpenw": _attr(reg, "outpenw"),
            "fillmode": _attr(reg, "fillmode"),
        }

    lin = _first(xml, r"<linInfo\b[^>]*>")
    if lin:
        style["line"] = {
            "outclr": _attr(lin, "outclr"),
            "outpenw": _attr(lin, "outpenw"),
            "id": _attr(lin, "id"),
        }

    pnt = _first(xml, r"<pntInfo\b[^>]*>")
    if pnt:
        style["point"] = {
            "fillclr": _attr(pnt, "fillclr"),
            "scale": _attr(pnt, "scale"),
            "id": _attr(pnt, "id"),
        }

    label = _first(xml, r"<label\b[^>]*>.*?</label>")
    if label:
        expr = _first(label, r"<labelExpression>(.*?)</labelExpression>")
        ann = _first(label, r"<annInfo\b[^>]*>")
        m_state = re.search(r"<state>(.*?)</state>", label, flags=re.S)
        style["label"] = {
            "state": (m_state.group(1).strip() if m_state else ""),
            "expression": (expr or "").replace("<labelExpression>", "")
            .replace("</labelExpression>", ""),
            "height": _attr(ann or "", "height"),
            "color": _attr(ann or "", "iclr"),
        }
    return style


def styles_from_mapx(mapx_text: str) -> List[dict]:
    """从整份 `.mapx` 文本提取所有图层样式。"""
    out = []
    for m in re.finditer(r'<subnode\b[^>]*type="SFeatureLayer"[^>]*>', mapx_text):
        start = m.start()
        depth = 0
        i = start
        block = None
        for mm in re.finditer(r"<(/?)subnode\b", mapx_text[start:]):
            if mm.group(1) == "":
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    j = mapx_text.find(">", start + mm.end())
                    block = mapx_text[start:j + 1]
                    break
        if block:
            out.append(layer_style_from_xml(block))
    return out


def save_styles(styles: List[dict], out_json: str) -> None:
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(styles, f, ensure_ascii=False, indent=2)


def load_styles(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
