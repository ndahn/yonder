from __future__ import annotations
from typing import ClassVar, Callable
from dataclasses import dataclass, field
import pyo

from yonder.hash import calc_hash, Hash
from yonder.enums import PropID, MarkerId
from yonder.util import logger
from yonder.audio import PlayContext, PlaybackState
from .hirc_node import HIRCNode
from .base_types import (
    MusicNodeParams,
    PropBundle,
    Children,
    MusicMarkerWwise,
    RTPC,
    StateChunk,
)
from .music_track import MusicTrack
from .mixins import PropertyMixin, RtpcMixin, StateMixin


@dataclass(repr=False, eq=False)
class MusicSegment(StateMixin, RtpcMixin, PropertyMixin, HIRCNode):
    """Segments are playback elements of determined length that contain one or more music tracks. A segment's tracks will play in parallel, while each track's clips will (usually) play in sequence."""

    body_type: ClassVar[int] = 10
    music_node_params: MusicNodeParams = field(default_factory=MusicNodeParams)
    duration: float = 0.0
    marker_count: int = 0
    markers: list[MusicMarkerWwise] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        nid: Hash,
        tracks: int | list[int] = None,
        markers: list[Hash, float] = None,
        props: dict[PropID, float] = None,
        parent: int | HIRCNode = 0,
    ) -> MusicSegment:
        obj = cls(nid)

        if tracks:
            if isinstance(tracks, int):
                tracks = [tracks]
            obj.music_node_params.children.items = tracks

        if markers:
            for mid, pos in markers:
                obj.set_marker(mid, pos)

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        obj.parent = parent
        return obj

    @property
    def wwise_link(self):
        return "https://www.audiokinetic.com/fr/public-library/2025.1.10_9233/?source=Help&id=what_is_music_segment"

    @property
    def parent(self) -> int:
        return self.music_node_params.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int | HIRCNode) -> None:
        if isinstance(new_parent, HIRCNode):
            new_parent = new_parent.id
        self.music_node_params.node_base_params.direct_parent_id = new_parent

    @property
    def children(self) -> Children:
        return self.music_node_params.children

    @property
    def properties(self) -> list[PropBundle]:
        return self.music_node_params.node_base_params.node_initial_params.prop_initial_values

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.music_node_params.node_base_params.initial_rtpc.rtpcs

    @property
    def states(self) -> StateChunk:
        return self.music_node_params.node_base_params.state_chunk

    def attach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            if not isinstance(other, MusicTrack):
                logger.warning(
                    "Attaching a non-MusicTrack to a MusicSegment is highly unusual and may result in an invalid soundbank!"
                )

            if other.parent not in (0, self.id):
                logger.warning(
                    f"{other} is already parented to {other.parent} and will be detached"
                )
            other.parent = self.id
            other = other.id

        self.children.add(other)

    def detach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            other = other.id

        if other in self.children:
            self.children.remove(other)

    def set_marker(
        self, mid: Hash | MarkerId, pos: float, update: bool = True
    ) -> MusicMarkerWwise:
        if isinstance(mid, str):
            label = mid
            mid = calc_hash(mid)
        else:
            label = ""

        mid = int(mid)

        for marker in self.markers:
            if marker.id == mid:
                if update:
                    marker.position = pos
                else:
                    raise ValueError(f"Marker {mid} ({label}) already exists")

                return marker
        else:
            marker = MusicMarkerWwise(
                mid,
                pos,
                string_length=len(label) + 1 if label else 0,
                string=label,
            )
            self.markers.append(marker)

        return marker

    def get_marker_pos(self, mid: Hash | MarkerId, default: float = 0.0) -> float:
        if isinstance(mid, str):
            mid = calc_hash(mid)

        mid = int(mid)

        for marker in self.markers:
            if marker.id == mid:
                return marker.position

        return default

    def remove_marker(self, mid: Hash, missing_ok: bool = True) -> None:
        if isinstance(mid, str):
            mid = calc_hash(mid)

        for idx, marker in enumerate(self.markers):
            if marker.id == mid:
                self.markers.pop(idx)
                return

        if not missing_ok:
            raise ValueError(f"Marker {mid} not found")

    def _build_pyo(self, my_pyo: PlaybackState) -> pyo.PyoObject:
        ctx = my_pyo.ctx
        out = []

        for child_id in self.children.items:
            child = ctx.bank.get(child_id)
            if child:
                out.append(child.pyo(ctx).output)

        my_pyo.cache["clock"] = pyo.Phasor(1000 / self.duration).stop()
        if out:
            return sum(out)

        return pyo.Sig(0)

    def play(self, ctx: PlayContext) -> None:
        my_pyo = self.pyo(ctx)
        if my_pyo.playing:
            return

        my_pyo.playing = True
        ctx = my_pyo.ctx

        for _, ref in self.get_references():
            node = ctx.bank.get(ref)
            if node:
                node.play(ctx)

        # segments have a fixed duration independent from their tracks' duration
        clock: pyo.Phasor = my_pyo.cache["clock"]
        offset = my_pyo.cache.get("pause_time", 0.0)
        clock.freq = 1000 / self.duration
        clock.phase = offset

        self.register_end_trigger(ctx, self._on_segment_end, 0, 0)

        clock.play()
        my_pyo.play()

    def _on_segment_end(self, ctx: PlayContext) -> None:
        # TODO this will probably cause a gap, but we'll have to change the
        # source/control design to fix this
        self.stop(ctx)
        self.pyo(ctx).cache["pause_time"] = 0.0
        loop = ctx.properties.get(PropID.Loop)

        for child_id in self.children.items:
            child = ctx.bank.get(child_id)
            if child and hasattr(child, "seek"):
                child.seek(ctx, 0)

        if loop is not None:
            self.play(ctx)

    def stop(self, ctx: PlayContext) -> None:
        if not self.is_pyo_initialized():
            return

        super().stop(ctx)

        my_pyo = self.pyo(ctx)
        clock: pyo.Phasor = my_pyo.cache["clock"]
        my_pyo.cache["pause_time"] = clock.get()

    def register_end_trigger(
        self,
        ctx: PlayContext,
        callback: Callable[[PlayContext], None],
        before: float = 0,
        max_triggers: int = 1,
    ):
        if not self.is_pyo_initialized():
            return

        my_pyo = self.pyo(ctx)
        ctx = my_pyo.ctx
        cb_objects: list[pyo.PyoObject] = []
        num_trig = 0

        def on_trigger(ctx: PlayContext) -> None:
            nonlocal num_trig

            callback(ctx)
            num_trig += 1

            # Cleanup the trigger objects if we've been triggered enough times
            if max_triggers > 0 and num_trig >= max_triggers:
                cache = self.pyo(ctx).cache
                objects = cache.get(storage_key, [])

                for obj in objects:
                    obj.stop()

                del cache[storage_key]

        # Trigger when this segment is only x seconds away from its end
        th = (self.duration - abs(before)) / self.duration
        clock: pyo.Phasor = my_pyo.cache["clock"]
        trigger_signal = pyo.Thresh(clock, threshold=th)
        cb_objects.append(trigger_signal)
        cb_objects.append(pyo.TrigFunc(trigger_signal, on_trigger, ctx))

        storage: dict = my_pyo.cache.setdefault("triggers", {})
        storage_key = max(storage.keys(), default=-1) + 1
        storage[storage_key] = cb_objects
