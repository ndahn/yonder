from __future__ import annotations
from typing import ClassVar
import numpy
import random
from dataclasses import dataclass, field
import pyo

from yonder.hash import Hash
from yonder.enums import PropID, RandomMode, PlaybackMode
from yonder.util import logger
from yonder.audio import PlayContext
from .hirc_node import HIRCNode, PyoState
from .base_types import (
    NodeBaseParams,
    Children,
    PropBundle,
    Playlist,
    PlaylistItem,
    RTPC,
    StateChunk,
)
from .mixins import PropertyMixin, RtpcMixin, StateMixin


@dataclass(repr=False, eq=False)
class RandomSequenceContainer(StateMixin, RtpcMixin, PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 5
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    loop_count: int = 1
    loop_mod_min: int = 0
    loop_mod_max: int = 0
    transition_time: float = 1000.0
    transition_time_mod_min: float = 0.0
    transition_time_mod_max: float = 0.0
    avoid_repeat_count: int = 1
    transition_mode: int = 0
    random_mode: int = 0
    mode: int = 0
    flags: int = 18
    children: Children = field(default_factory=Children)
    playlist: Playlist = field(default_factory=Playlist)

    @classmethod
    def new(
        cls,
        nid: Hash,
        nodes: int | list[int],
        playback_mode: PlaybackMode = PlaybackMode.Random,
        random_mode: RandomMode = RandomMode.Standard,
        loop_count: int = 1,
        avoid_repeat_count: int = 0,
        props: dict[PropID, float] = None,
        parent: int | HIRCNode = 0,
    ) -> RandomSequenceContainer:
        obj = cls(
            nid,
            mode=playback_mode.value,
            random_mode=random_mode.value,
            loop_count=loop_count,
            avoid_repeat_count=avoid_repeat_count,
        )

        if nodes:
            for node in nodes:
                obj.add_playlist_item(node)

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        obj.parent = parent
        return obj

    @property
    def parent(self) -> int:
        return self.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int | HIRCNode) -> None:
        if isinstance(new_parent, HIRCNode):
            new_parent = new_parent.id
        self.node_base_params.direct_parent_id = new_parent

    @property
    def properties(self) -> list[PropBundle]:
        return self.node_base_params.node_initial_params.prop_initial_values

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.node_base_params.initial_rtpc.rtpcs

    @property
    def states(self) -> StateChunk:
        return self.node_base_params.state_chunk

    def add_playlist_item(self, child_id: int | HIRCNode) -> None:
        if isinstance(child_id, HIRCNode):
            child_id = child_id.id

        child_id = int(child_id)
        self.children.add(child_id)
        self.playlist.add(PlaylistItem(child_id))

    def pick_random_child(self) -> tuple[int, PlaylistItem]:
        # TODO respect random mode, no repeats, etc
        weights = [p.weight for p in self.playlist]
        idx = random.choices(self.playlist, weights)
        return (idx, self.playlist[idx])

    def attach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            if other.parent not in (0, self.id):
                logger.warning(
                    f"{other} is already parented to {other.parent} and will be detached"
                )
            other.parent = self.id
            other = other.id

        self.add_playlist_item(other)

    def detach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            other = other.id

        if other in self.children:
            self.children.remove(other)

            indices = []
            for idx, item in enumerate(self.playlist):
                if item.play_id == other:
                    indices.append(idx)

            for idx in reversed(indices):
                self.playlist.pop(idx)

    @property
    def mode_enum(self) -> PlaybackMode:
        return PlaybackMode(self.mode)

    @property
    def random_mode_enum(self) -> RandomMode:
        return RandomMode(self.random_mode)

    def _build_pyo(self, my_pyo: PyoState) -> pyo.InputFader:
        sig = pyo.Sig(0)
        my_pyo.cache["pyo_placeholder"] = sig
        return pyo.InputFader(sig)

    def play(self, ctx: PlayContext, force_playlist_idx: int = -1) -> None:
        if not self.playlist:
            return

        my_pyo = self.pyo(ctx)
        ctx = my_pyo.ctx
        fader: pyo.InputFader = my_pyo.playback
        prev_node: HIRCNode = ctx.bank.get(my_pyo.cache.get("prev_node", -1))

        if force_playlist_idx >= 0:
            playlist_item = self.playlist[force_playlist_idx]
        else:
            # TODO need to keep state depending on random mode
            _, playlist_item = self.pick_random_child()

        child = ctx.bank.get(playlist_item.play_id)
        if child:
            xfade = (
                max(
                    [
                        ctx.properties.get(PropID.FadeOutTime, 0.0),
                        ctx.properties.get(PropID.FadeInTime, 0.0),
                        50,
                    ]
                )
                / 1000
            )

            child.play(ctx)
            fader.setInput(child.pyo(ctx).playback, xfade)
            my_pyo.cache["prev_node"] = child.id
        else:
            xfade = 0.5
            fader.setInput(my_pyo.cache["pyo_placeholder"], xfade)

        if prev_node:
            prev_node.release_pyo(ctx, xfade + 0.1)
