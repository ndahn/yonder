from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar, Callable
from pathlib import Path
import pyo

from yonder.hash import Hash
from yonder.enums import SourceType, PropID
from yonder.wem import get_wem_metadata, wem2wav
from yonder.audio import PlayContext
from yonder.audio.multi_track_stream import MultiTrackStream
from .hirc_node import HIRCNode, PyoState
from .base_types import (
    NodeBaseParams,
    BankSourceData,
    PropBundle,
    MediaInformation,
    RTPC,
    StateChunk,
)
from .mixins import PropertyMixin, RtpcMixin, StateMixin


@dataclass(repr=False, eq=False)
class Sound(StateMixin, RtpcMixin, PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 2
    bank_source_data: BankSourceData = field(default_factory=BankSourceData)
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)

    @classmethod
    def new(
        cls,
        nid: Hash,
        wem: Path = None,
        source_type: SourceType = SourceType.Embedded,
        props: dict[PropID, float] = None,
        parent: int | HIRCNode = 0,
    ) -> Sound:
        obj = cls(nid)

        if wem:
            obj.set_source_from_wem(wem, source_type)

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

    @property
    def source_id(self) -> int:
        return self.bank_source_data.media_information.source_id

    @property
    def source_type(self) -> SourceType:
        return self.bank_source_data.source_type

    def set_source_from_wem(
        self,
        wem: Path,
        source_type: SourceType = SourceType.Embedded,
    ) -> BankSourceData:
        try:
            wem_id = int(wem.stem)
        except ValueError:
            raise ValueError(f"Invalid sound filename {wem.stem}, must be numbers only")

        meta = get_wem_metadata(wem)
        size = meta["in_memory_size"]

        self.set_source(
            wem_id,
            size,
            source_type=source_type,
        )

    def set_source(
        self,
        source_id: int,
        media_size: int,
        source_type: SourceType = SourceType.Embedded,
    ) -> BankSourceData:
        self.bank_source_data = BankSourceData(
            source_type=source_type,
            media_information=MediaInformation(int(source_id), media_size),
        )

    def _build_pyo(self, my_pyo: PyoState) -> MultiTrackStream:
        ctx = my_pyo.ctx

        props = ctx.properties
        path = ctx.bank.get_wem_path(
            self.source_id, self.source_type, ctx.wem_search_paths
        )

        if path.suffix == ".wem":
            path = wem2wav(ctx.vgmstream_exe, path)[0]

        # TODO save wem search paths in bank, pass vgmstream_exe to MultiTrackStream

        return MultiTrackStream.from_paths(
            ctx.bank,
            path,
            loop=(PropID.Loop in props),
            volume_db=props.get(PropID.Volume, 0.0),
            hpf_cents=props.get(PropID.HPF, 0.0),
            lpf_cents=props.get(PropID.LPF, 0.0),
            pitch_semitones=props.get(PropID.Pitch, 0.0),
            attenuation=ctx.attenuation,
            distance=ctx.distance,
            angle=ctx.angle,
        )

    def play(self, ctx: PlayContext) -> None:
        my_pyo = self.pyo(ctx)
        if my_pyo.playing:
            return

        my_pyo.playing = True
        self.update_playback(ctx)
        self.register_end_trigger(ctx, self._on_sound_end, 0, 0)
        my_pyo.play()

    def _on_sound_end(self, ctx: PlayContext) -> None:
        self.stop(ctx)
        self.seek(ctx, 0)

    def seek(self, ctx: PlayContext, pos: float) -> None:
        self.pyo(ctx).playback.seek(pos)

    def update_playback(self, ctx: PlayContext) -> None:
        if not self.is_pyo_initialized():
            return

        my_pyo = self.pyo(ctx)
        ctx = my_pyo.ctx
        stream: MultiTrackStream = my_pyo.playback
        props = ctx.properties

        stream.loop = PropID.Loop in props

        loop_start = props.get(PropID.LoopStart, stream.loop_start)
        loop_end = props.get(PropID.LoopEnd, stream.loop_end)
        stream.set_loop_points(loop_start, loop_end)

        begin_trim = props.get(PropID.TrimInTime, stream.begin_trim)
        end_trim = props.get(PropID.TrimOutTime, stream.end_trim)
        stream.set_trims(begin_trim, end_trim)

        xfade = props.get(PropID.LoopCrossfadeDuration)
        if xfade is not None:
            stream.xfade = xfade

        vol = props.get(PropID.Volume)
        if vol is not None:
            stream.volume = vol

        hpf = props.get(PropID.HPF)
        if hpf is not None:
            stream.hpf = hpf

        lpf = props.get(PropID.LPF)
        if lpf is not None:
            stream.lpf = lpf

        pitch = props.get(PropID.Pitch)
        if pitch is not None:
            stream.pitch = pitch

        super().update_playback(ctx)

    def register_end_trigger(
        self,
        ctx: PlayContext,
        callback: Callable[[PlayContext], None],
        before: float = 0,
        max_triggers: int = 1,
    ) -> None:
        my_pyo = self.pyo(ctx)
        ctx = my_pyo.ctx
        stream: MultiTrackStream = my_pyo.playback
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

        if before == 0:
            trigger_signal = stream["trig"]
        else:
            # Trigger when the stream is only x seconds away from its end
            th = (stream.duration - abs(before)) / stream.duration
            trigger_signal = pyo.Thresh(stream._overall_clock, threshold=th)
            cb_objects.append(trigger_signal)

        cb_objects.append(pyo.TrigFunc(trigger_signal, on_trigger, ctx))

        storage: dict = my_pyo.cache.setdefault("triggers", {})
        storage_key = max(storage.keys(), default=-1) + 1
        storage[storage_key] = cb_objects

    def release_pyo(self, ctx: PlayContext, delay: float = 0.1) -> None:
        if self.is_pyo_initialized():
            my_pyo = self.pyo(ctx)
            for cb_objects in my_pyo.cache.get("triggers", {}).values():
                for obj in cb_objects:
                    obj.stop()

        super().release_pyo(ctx, delay)
