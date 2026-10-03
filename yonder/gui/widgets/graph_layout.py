from __future__ import annotations
from typing import TypeVar, Callable
import math
import networkx as nx


T = TypeVar("T")


class GraphLayout[T]:
    def __init__(
        self,
        store_node: Callable[[int, tuple[float, float]], T],
        g: nx.DiGraph = None,
        *,
        horizontal: bool = False,
        node_spacing: float = 60.0,
        hidden_branches: dict[int, list[int]] = None,
    ):
        self._store_node = store_node
        self.horizontal = horizontal
        self.node_spacing = node_spacing
        self.hidden_branches = hidden_branches or {} # parent id -> collapsed siblings
        self.nodes: dict[int, T] = {}

        if g:
            self.regenerate(g)

    def regenerate(self, g: nx.DiGraph) -> None:
        self.nodes = self._make_layout(g)

    def _make_layout(self, g: nx.DiGraph) -> dict[int, T]:
        """place nodes on a half-ring: depth -> radius, subtree size -> angle.

        Roots sit at the center; each generation forms a wider ring around
        it, opening downward (vertical) or rightward (horizontal). Siblings
        share their parent's wedge proportional to subtree size, so a chain
        of single-child nodes forms a straight ray.
        """
        layout: dict[int, T] = {}
        if g.number_of_nodes() == 0:
            return layout

        leafs = self._leaf_counts(g)
        roots = [n for n in g if g.in_degree(n) == 0]
        total = sum(leafs[r] for r in roots) or 1

        half_sweep = math.pi / 4  # 45 degrees either side of center
        lo = -half_sweep

        for root in roots:
            share = 2 * half_sweep * leafs[root] / total
            self._place(g, root, 0, lo, lo + share, leafs, layout)
            lo += share

        return layout

    def _place(
        self,
        g: nx.DiGraph,
        nid: int,
        depth: int,
        lo: float,
        hi: float,
        leafs: dict[int, int],
        layout: dict[int, T],
    ) -> None:
        """give nid a ring position, then split its wedge among its children."""
        theta = (lo + hi) / 2
        pos = self._polar_to_pos(depth * self.node_spacing, theta)
        layout[nid] = self._store_node(nid, pos)

        children = list(g.successors(nid))
        total = leafs[nid] or 1
        cur = lo
        for child in children:
            share = (hi - lo) * leafs[child] / total
            self._place(g, child, depth + 1, cur, cur + share, leafs, layout)
            cur += share

    def _polar_to_pos(self, radius: float, theta: float) -> tuple[float, float]:
        """convert (radius, angle) to plot coords. theta=0 is straight ahead."""
        if self.horizontal:
            return radius * math.cos(theta), radius * math.sin(theta)
        return radius * math.sin(theta), -radius * math.cos(theta)

    def _leaf_counts(self, g: nx.DiGraph) -> dict[int, int]:
        """number of leaf descendants under each node, used to size wedges."""
        counts: dict[int, int] = {}
        for nid in reversed(list(nx.topological_sort(g))):
            children = list(g.successors(nid))
            counts[nid] = sum(counts[c] for c in children) if children else 1
        return counts

    def __getitem__(self, key: str) -> T:
        return self.nodes[key]

    def __len__(self) -> int:
        return len(self.nodes)

    def __bool__(self) -> bool:
        return bool(self.nodes)
