"""网络分析(基于 networkx)。

适用于道路/河流等线要素:
    - 按端点构建网络(节点坐标取整作为 ID)
    - 连通分量、节点/边统计
    - 最短路径、最近节点

依赖:`pip install networkx`
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

try:
    import networkx as nx
except ImportError as exc:  # pragma: no cover
    raise ImportError("需要 networkx:pip install networkx") from exc


class NetworkError(RuntimeError):
    """网络分析异常。"""


def _node_key(p: Sequence[float], ndigits: int = 6) -> Tuple[float, float]:
    return (round(float(p[0]), ndigits), round(float(p[1]), ndigits))


def build_graph(features: Sequence[dict], ndigits: int = 6):
    """由线要素构建无向图(按端点连接),边权为欧氏长度。"""
    g = nx.Graph()
    for f in features:
        for ring in f.get("parts") or []:
            for i in range(len(ring) - 1):
                a = _node_key(ring[i], ndigits)
                b = _node_key(ring[i + 1], ndigits)
                if a == b:
                    continue
                length = math.hypot(b[0] - a[0], b[1] - a[1])
                if g.has_edge(a, b):
                    g[a][b]["weight"] = min(g[a][b]["weight"], length)
                else:
                    g.add_edge(a, b, weight=length)
    return g


def summary(features: Sequence[dict]) -> dict:
    """网络概况:节点数、边数、连通分量、总长度。"""
    g = build_graph(features)
    comps = list(nx.connected_components(g)) if g.number_of_nodes() else []
    total = sum(d.get("weight", 0.0) for _, _, d in g.edges(data=True))
    return {
        "nodes": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "components": len(comps),
        "largest_component": max((len(c) for c in comps), default=0),
        "total_length": total,
    }


def shortest_path(features: Sequence[dict], start: Sequence[float],
                  end: Sequence[float]) -> dict:
    """两点间最短路径(自动吸附到最近节点)。"""
    g = build_graph(features)
    if g.number_of_nodes() == 0:
        raise NetworkError("网络为空")

    def nearest(p):
        return min(g.nodes, key=lambda n: (n[0] - p[0]) ** 2 + (n[1] - p[1]) ** 2)

    s, t = nearest(start), nearest(end)
    if not nx.has_path(g, s, t):
        raise NetworkError("两点不连通")
    path = nx.shortest_path(g, s, t, weight="weight")
    length = nx.shortest_path_length(g, s, t, weight="weight")
    return {"start_node": s, "end_node": t, "nodes": len(path),
            "length": length, "path": path}


def largest_component(features: Sequence[dict]) -> dict:
    """取出最大连通分量中的边(用于剔除碎线)。"""
    g = build_graph(features)
    if g.number_of_nodes() == 0:
        return {"parts": [], "attrs": {}}
    comp = max(nx.connected_components(g), key=len)
    keep = set(comp)
    parts = []
    for f in features:
        for ring in f.get("parts") or []:
            kept = [p for p in ring if _node_key(p) in keep]
            if len(kept) >= 2:
                parts.append(kept)
    return {"parts": parts, "attrs": {}}
