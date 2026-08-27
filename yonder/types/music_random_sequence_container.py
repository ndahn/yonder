from __future__ import annotations
from typing import ClassVar
import random
import math
from dataclasses import dataclass, field
import networkx as nx
import pyo

from yonder.hash import global_id_generator, Hash
from yonder.enums import PropID, CurveInterpolation, SyncType, RandomSequenceMode
from yonder.util import logger
from yonder.audio import PlayContext
from .hirc_node import HIRCNode, PyoState
from .base_types import (
    MusicRanSeqPlaylistItem,
    MusicTransNodeParams,
    PropBundle,
    Children,
    MusicTransitionRule,
    MusicTransSrcRule,
    MusicTransDstRule,
    RTPC,
    StateChunk,
)
from .mixins import PropertyMixin, RtpcMixin, StateMixin


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


@dataclass(repr=False, eq=False)
class MusicRandomSequenceContainer(StateMixin, RtpcMixin, PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 13
    music_trans_node_params: MusicTransNodeParams = field(
        default_factory=MusicTransNodeParams
    )
    playlist_item_count: int = 0
    playlist_items: list[MusicRanSeqPlaylistItem] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        nid: Hash,
        playlist: list[int, list[int]] = None,
        ers_type: RandomSequenceMode = RandomSequenceMode.ContinuousSequence,
        props: dict[PropID, float] = None,
        parent: int | HIRCNode = 0,
    ) -> MusicRandomSequenceContainer:
        if playlist:
            items = cls.make_playlist(playlist, ers_type=ers_type)
        else:
            items = []

        obj = cls(nid, playlist_items=items)

        obj.music_trans_node_params.music_node_params.children.items = [
            p.segment_id for p in items if p.segment_id > 0
        ]

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        obj.parent = parent
        return obj

    @property
    def parent(self) -> int:
        return self.music_trans_node_params.music_node_params.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int | HIRCNode) -> None:
        if isinstance(new_parent, HIRCNode):
            new_parent = new_parent.id
        self.music_trans_node_params.music_node_params.node_base_params.direct_parent_id = new_parent

    @property
    def children(self) -> Children:
        return self.music_trans_node_params.music_node_params.children

    @property
    def properties(self) -> list[PropBundle]:
        return self.music_trans_node_params.music_node_params.node_base_params.node_initial_params.prop_initial_values

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.music_trans_node_params.music_node_params.node_base_params.initial_rtpc.rtpcs

    @property
    def states(self) -> StateChunk:
        return (
            self.music_trans_node_params.music_node_params.node_base_params.state_chunk
        )

    def set_playlist(
        self,
        items: list,
        ers_type: RandomSequenceMode = RandomSequenceMode.ContinuousSequence,
    ) -> None:
        playlist = self.make_playlist(items, ers_type)
        self.playlist_items = playlist
        self.music_trans_node_params.music_node_params.children.items = [
            p.segment_id for p in playlist if p.segment_id > 0
        ]

    @property
    def root_ers_type(self) -> RandomSequenceMode:
        if not self.playlist_items:
            return RandomSequenceMode.ContinuousSequence

        return self.playlist_items[0].ers_type_enum

    def get_playlist_tree(self) -> nx.DiGraph:
        g = nx.DiGraph()
        idx = 0

        while idx < len(self.playlist_items):
            item = self.playlist_items[idx]
            g.add_node(item.playlist_item_id, item=item)

            for child in self.playlist_items[idx + 1 : idx + 1 + item.child_count]:
                g.add_node(child.playlist_item_id, item=child)
                g.add_edge(
                    item.playlist_item_id,
                    child.playlist_item_id,
                    mode=item.ers_type_enum,
                )
            idx += item.child_count + 1

        return g

    @staticmethod
    def make_playlist(
        items: list,
        ers_type: RandomSequenceMode = RandomSequenceMode.ContinuousSequence,
    ) -> list[MusicRanSeqPlaylistItem]:
        def assemble(
            item: int | list | tuple,
            playlist: list[MusicRanSeqPlaylistItem],
            parent_id: int,
        ) -> None:
            if isinstance(item, int):
                playlist.append(
                    MusicRanSeqPlaylistItem(
                        item,
                        global_id_generator(),
                        ers_type=RandomSequenceMode.Inherit.value,
                        parent=parent_id,
                    )
                )
            else:
                if isinstance(item[0], RandomSequenceMode):
                    group_ers = item[0]
                    item = item[1:]
                elif isinstance(item, list):
                    group_ers = RandomSequenceMode.ContinuousSequence
                else:
                    group_ers = RandomSequenceMode.ContinuousRandom

                group_node = MusicRanSeqPlaylistItem(
                    0,
                    global_id_generator(),
                    ers_type=group_ers.value,
                    parent=parent_id,
                )
                playlist.append(group_node)
                for child in item:
                    assemble(child, playlist, group_node.playlist_item_id)

        playlist = [MusicRanSeqPlaylistItem(0, 0, ers_type=ers_type.value)]
        for child in items:
            assemble(child, playlist, playlist[-1].playlist_item_id)

        return playlist

    def add_playlist_item(
        self,
        playlist_item_id: int,
        segment_id: int | HIRCNode,
        weight: int = 50000,
        use_weight: bool = False,
        shuffle: bool = False,
        avoid_repeat_count: int = 0,
        loop_base: bool = False,
        ers_type: RandomSequenceMode = RandomSequenceMode.Inherit,
        parent: int | MusicRanSeqPlaylistItem = 0,
    ) -> MusicRanSeqPlaylistItem:
        """Associates a segment with this playlist for random/sequential playback. A playlist is actually a flattened tree structure where children inherit settings from their parents. Use the parent parameter to associate child items to their parents.

        Parameters
        ----------
        playlist_item_id : int
            Unique playlist item ID.
        segment_id : int | Node
            Segment node ID.
        weight : int, default=50000
            Relative weight for random selection.
        use_weight : bool, default=False
            Whether to use weight when shuffling. Always True for the first playlist item.
        avoid_repeat : int, default=0
            Number of recent items to avoid repeating.
        ers_type : RandomSequenceMode, default=RandomSequenceMode.Inherit
            Playlist playback type.
        parent : int, default=0
            Which playlist item to associate the new item with (0 - root).
        """
        if isinstance(parent, MusicRanSeqPlaylistItem):
            parent = parent.playlist_item_id

        if isinstance(segment_id, HIRCNode):
            segment_id = segment_id.id

        parent = int(parent)
        segment_id = int(segment_id)

        if len(self.playlist_items) == 0:
            if parent > 0:
                raise ValueError("parent cannot be set for first playlist item")

            if ers_type == RandomSequenceMode.Inherit:
                ers_type = RandomSequenceMode.ContinuousSequence

            use_weight = True

        new_item = MusicRanSeqPlaylistItem(
            segment_id,
            playlist_item_id,
            ers_type=ers_type.value,
            loop_base=1 if loop_base else 0,
            weight=weight,
            use_weight=1 if use_weight else 0,
            avoid_repeat_count=avoid_repeat_count,
            shuffle=1 if shuffle else 0,
        )

        if parent > 0:
            # Insert after parent
            for idx, item in enumerate(self.playlist_items):
                if item.playlist_item_id == parent:
                    insert_idx = idx + 1
                    parent_item = item
                    break
            else:
                raise ValueError(f"No playlist item with key {parent}")

            insert_idx += parent_item.child_count
            self.playlist_items.insert(insert_idx, new_item)
            parent_item.child_count += 1
        else:
            self.playlist_items.append(new_item)

        if segment_id > 0:
            self.children.add(segment_id)

        return new_item

    def add_transition_rule(
        self,
        source_ids: int | list[int] = -1,
        dest_ids: int | list[int] = -1,
        sync_type: SyncType = SyncType.Immediate,
        source_transition_time: int = 0,
        source_fade_offset: int = 0,
        source_fade_curve: CurveInterpolation = CurveInterpolation.Linear,
        source_play_post_exit: bool = False,
        dest_transition_time: int = 0,
        dest_fade_offset: int = 0,
        dest_fade_curve: CurveInterpolation = CurveInterpolation.Linear,
        dest_play_pre_entry: bool = False,
        transition_segment: int = 0,
    ) -> MusicTransitionRule:
        """Add a transition rule between segments.

        Parameters
        ----------
        source_ids : int | list[int], default = -1
            Source segment IDs (-1 = any).
        dest_ids : int | list[int], default = -1
            Destination segment IDs (-1 = any).
        source_transition_time : int, default=0
            Source fade out time in ms.
        source_fade_offset : int, default=0
            Delay in ms before the source starts fading out.
        source_fade_curve : str, default=CurveInterpolation.Linear
            Source fade out curve type.
        sync_type : SyncType, default=SyncType.Immediate
            Marker sync type.
        dest_transition_time : int, default=0
            Destination fade out time in ms.
        dest_fade_offset : int, default=0
            Delay in ms before the destination starts fading in.
        dest_fade_curve : str, default=CurveInterpolation.Linear
            Destination fade in curve type.
        transition_segment: int | Node, default=0
            A MusicSegment to play during the transition.
        """
        if isinstance(source_ids, int):
            source_ids = [source_ids]

        if isinstance(dest_ids, int):
            dest_ids = [dest_ids]

        rule = MusicTransitionRule(
            source_ids=source_ids,
            destination_ids=dest_ids,
            source_transition_rule=MusicTransSrcRule(
                transition_time=source_transition_time,
                fade_curve=source_fade_curve,
                fade_offet=source_fade_offset,
                sync_type=sync_type,
                play_post_exit=1 if source_play_post_exit else 0,
            ),
            destination_transition_rule=MusicTransDstRule(
                transition_time=dest_transition_time,
                fade_curve=dest_fade_curve,
                fade_offet=dest_fade_offset,
                play_pre_entry=1 if dest_play_pre_entry else 0,
            ),
        )

        if transition_segment:
            rule.transition_object.segment_id = transition_segment

        self.music_trans_node_params.transition_rules.append(rule)
        return rule

    def attach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            if other.parent not in (0, self.id):
                logger.warning(
                    f"{other} is already parented to {other.parent} and will be detached"
                )
            other.parent = self.id
            other = other.id

        pid = self.playlist_items[-1] + 1 if self.playlist_items else 0
        self.add_playlist_item(pid, int(other))

        logger.warning("Don't forget to adjust the new playlist item details!")

    def detach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            other = other.id

        if other in self.children:
            self.children.remove(other)

            indices = []
            for idx, item in enumerate(self.playlist_items):
                if item.segment_id:
                    indices.append(idx)

            for idx in reversed(indices):
                self.playlist_items.pop(idx)

    def get_references(self, true_children_only: bool = True) -> list[tuple[str, int]]:
        ret = super().get_references()

        if true_children_only:
            # Some vanilla soundbanks have leftover transition rules that will result
            # in misleading warnings and mess up our gui's tree structure
            ret = [
                (p, i)
                for p, i in ret
                if "transition_rule" not in p or i in self.children
            ]

        return ret

    def _build_pyo(self, my_pyo: PyoState) -> pyo.InputFader:
        return pyo.InputFader(pyo.Sig(0))

    def play(self, ctx: PlayContext) -> None:
        if not self.playlist_items:
            return

        self._play_next(ctx)

    def _play_next(self, ctx: PlayContext) -> None:
        my_pyo = self.pyo(ctx)
        ctx = my_pyo.ctx
        fader: pyo.InputFader = my_pyo.pyo_playback

        state: PlaylistState = my_pyo.cache.get("playlist_state")
        if not state:
            playlist = self.get_playlist_tree()
            state = PlaylistState(playlist)
            my_pyo.cache["playlist_state"] = state

        item = state.current_item
        prev_node = None
        if item:
            prev_node = ctx.bank.get(item.segment_id)

        while not state.finished:
            item = state.get_next_item()
            if not item:
                break

            node = ctx.bank.get(item.segment_id)
            if node:
                # TODO transition rule
                node.register_end_trigger(ctx, self._play_next)
                node.play(ctx)
                fader.setInput(node.pyo(ctx).pyo_playback, 1)

                # Probably have to wait for the fader
                if prev_node:
                    prev_node.reset_pyo(ctx)

                break
            else:
                logger.warning(f"Segment {item.segment_id} not found, skipping")

        if state.finished:
            fader.setInput(pyo.Sig(0))
