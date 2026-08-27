from __future__ import annotations
import random
import math
from dataclasses import dataclass, field
import networkx as nx

from yonder.enums import RandomSequenceMode
from yonder.types.base_types import MusicRanSeqPlaylistItem


@dataclass
class PlaylistState:
    playlist: nx.DiGraph
    current: int = None
    finished: bool = False
    cache: dict = field(default_factory=dict)

    def get_playlist_item(self, item_id: int) -> MusicRanSeqPlaylistItem:
        return self.playlist[item_id]["item"]

    @property
    def current_item(self) -> MusicRanSeqPlaylistItem:
        if self.finished or self.current is None:
            return None

        return self.get_playlist_item(self.current)

    def get_ers_type(self, item: int | MusicRanSeqPlaylistItem) -> RandomSequenceMode:
        if isinstance(item, MusicRanSeqPlaylistItem):
            item = item.playlist_item_id

        item = self.get_playlist_item(item)

        while item.ers_type_enum == RandomSequenceMode.Inherit:
            item = next(self.playlist.predecessors(item))
            item = self.get_playlist_item(item)

        return item.ers_type_enum

    def get_next_item(self) -> MusicRanSeqPlaylistItem:
        if self.finished:
            return None

        if self.current is None:
            node = next(n for n in self.playlist if self.playlist.in_degree(n) == 0)
            selected = self._descend(node)
            self.current = selected
            return self.get_playlist_item(selected)

        selected = self._advance(self.current)
        if selected is None:
            self.finished = True
            self.current = None
            return None

        self.current = selected
        return self.get_playlist_item(selected)

    def reset(self) -> None:
        self.current = None
        self.finished = False
        self.cache.clear()

    def _roll_budget(self, node: int) -> float:
        """how many units (plays/child-picks/passes) this node gets before yielding to its parent."""
        item = self.get_playlist_item(node)
        count = (
            random.randint(item.loop_min, item.loop_max)
            if item.loop_min or item.loop_max
            else item.loop_base
        )
        return math.inf if count <= 0 else count

    def _enter(self, node: int) -> None:
        """(re)roll a node's repeat budget on every fresh entry; history persists across entries."""
        state = self.cache.setdefault(node, {"history": []})
        state["repeats_left"] = self._roll_budget(node)
        state["pass_pos"] = 0

    def _weighted_pick(self, candidates: list[int]) -> int:
        weights = [
            self.get_playlist_item(c).weight
            for c in candidates
        ]
        return random.choices(candidates, weights=weights, k=1)[0]

    def _avoid_repeats(
        self, item: MusicRanSeqPlaylistItem, pool: list[int], history: list[int]
    ) -> list[int]:
        if not item.avoid_repeat_count:
            return pool

        recent = set(history[-item.avoid_repeat_count :])
        filtered = [c for c in pool if c not in recent]
        return filtered or pool

    def _pick_child(self, node: int) -> int:
        """select the next child per ers_type, tracking position/pool history for later picks."""
        item = self.get_playlist_item(node)
        ers = self.get_ers_type(node)
        succ = list(self.playlist.successors(node))
        state = self.cache[node]
        history = state["history"]

        if ers in (
            RandomSequenceMode.StepSequence,
            RandomSequenceMode.ContinuousSequence,
        ):
            selected = succ[len(history) % len(succ)]
        else:
            pool = (
                [c for c in succ if c not in history[-len(succ) :]]
                if item.shuffle
                else succ
            )
            pool = pool or succ
            pool = self._avoid_repeats(item, pool, history)
            if item.use_weight:
                selected = self._weighted_pick(pool)
            else:
                selected = random.choice(pool)

        history.append(selected)
        state["pass_pos"] += 1
        return selected

    def _descend(self, node: int) -> int:
        """enter a node and go down until we reach a leaf."""
        succ = list(self.playlist.successors(node))
        self._enter(node)
        if not succ:
            return node

        selected = self._pick_child(node)
        return self._descend(selected)

    def _advance(self, node: int) -> int:
        """node's own activation just finished; repeat it (leaf) or bubble to its parent."""
        if self.playlist.out_degree(node) == 0:
            state = self.cache[node]
            state["repeats_left"] -= 1
            if state["repeats_left"] > 0:
                return node  # replay the same leaf

        parents = list(self.playlist.predecessors(node))
        if not parents:
            return None

        return self._advance_group(parents[0])

    def _advance_group(self, node: int) -> int:
        """one of node's children just finished; continue its pass/pick or close out its unit."""
        succ = list(self.playlist.successors(node))
        ers = self.get_ers_type(node)
        continuous = ers in (
            RandomSequenceMode.ContinuousSequence,
            RandomSequenceMode.ContinuousRandom,
        )
        state = self.cache[node]

        if continuous and state["pass_pos"] < len(succ):
            # mid-pass: more children owed before this counts as one unit
            selected = self._pick_child(node)
            return self._descend(selected)

        # one unit complete: one child (step) or one full pass (continuous)
        state["repeats_left"] -= 1
        parents = list(self.playlist.predecessors(node))

        if state["repeats_left"] > 0:
            state["pass_pos"] = 0
            selected = self._pick_child(node)
            return self._descend(selected)

        if not parents:
            return None

        return self._advance_group(parents[0])
