from __future__ import annotations
from typing import TYPE_CHECKING
import random
import math
from dataclasses import dataclass, field

from yonder.enums import RandomSequenceMode
from yonder.types.base_types import MusicRanSeqPlaylistItem

if TYPE_CHECKING:
    from yonder.types.music_random_sequence_container import PlaylistTreeItem


@dataclass
class PlaylistState:
    """Walks a MusicRandomSequenceContainer's playlist tree one segment at a time."""

    playlist: PlaylistTreeItem
    current: PlaylistTreeItem = None
    finished: bool = False
    cache: dict = field(default_factory=dict)

    @property
    def current_item(self) -> MusicRanSeqPlaylistItem:
        if self.finished or self.current is None:
            return None

        return self.current.item

    def get_next_item(self) -> MusicRanSeqPlaylistItem:
        if self.finished:
            return None

        if self.current is None:
            self.current = self._descend(self.playlist)
            return self.current.item

        selected = self._advance(self.current)
        if selected is None:
            self.finished = True
            self.current = None
            return None

        self.current = selected
        return selected.item

    def reset(self) -> None:
        self.current = None
        self.finished = False
        self.cache.clear()

    def _roll_budget(self, node: PlaylistTreeItem) -> float:
        """how many units (plays/child-picks/passes) this node gets before yielding to its parent."""
        item = node.item
        count = (
            random.randint(item.loop_min, item.loop_max)
            if item.loop_min or item.loop_max
            else item.loop_base
        )
        return math.inf if count <= 0 else count

    def _enter(self, node: PlaylistTreeItem) -> None:
        """(re)roll a node's repeat budget on every fresh entry; history persists across entries."""
        state = self.cache.setdefault(node, {"history": []})
        state["repeats_left"] = self._roll_budget(node)
        state["pass_pos"] = 0

    def _weighted_pick(self, candidates: list[PlaylistTreeItem]) -> PlaylistTreeItem:
        weights = [c.item.weight for c in candidates]
        return random.choices(candidates, weights=weights, k=1)[0]

    def _avoid_repeats(
        self,
        item: MusicRanSeqPlaylistItem,
        pool: list[PlaylistTreeItem],
        history: list[PlaylistTreeItem],
    ) -> list[PlaylistTreeItem]:
        if not item.avoid_repeat_count:
            return pool

        recent = set(history[-item.avoid_repeat_count :])
        filtered = [c for c in pool if c not in recent]
        return filtered or pool

    def _pick_child(self, node: PlaylistTreeItem) -> PlaylistTreeItem:
        """select the next child per ers_type, tracking position/pool history for later picks."""
        item = node.item
        ers = node.ers_type
        succ = node.children
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

    def _descend(self, node: PlaylistTreeItem) -> PlaylistTreeItem:
        """enter a node and go down until we reach a leaf."""
        self._enter(node)
        if node.is_leaf():
            return node

        return self._descend(self._pick_child(node))

    def _advance(self, node: PlaylistTreeItem) -> PlaylistTreeItem:
        """node's own activation just finished; repeat it (leaf) or bubble to its parent."""
        if node.is_leaf():
            state = self.cache[node]
            state["repeats_left"] -= 1
            if state["repeats_left"] > 0:
                return node  # replay the same leaf

        if not node.parent:
            return None

        return self._advance_group(node.parent)

    def _advance_group(self, node: PlaylistTreeItem) -> PlaylistTreeItem:
        """one of node's children just finished; continue its pass/pick or close out its unit."""
        ers = node.ers_type
        continuous = ers in (
            RandomSequenceMode.ContinuousSequence,
            RandomSequenceMode.ContinuousRandom,
        )
        state = self.cache[node]

        if continuous and state["pass_pos"] < len(node.children):
            # mid-pass: more children owed before this counts as one unit
            return self._descend(self._pick_child(node))

        # one unit complete: one child (step) or one full pass (continuous)
        state["repeats_left"] -= 1

        if state["repeats_left"] > 0:
            state["pass_pos"] = 0
            return self._descend(self._pick_child(node))

        if not node.parent:
            return None

        return self._advance_group(node.parent)
