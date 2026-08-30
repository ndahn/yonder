from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar, Callable
from pathlib import Path
import pyo

from yonder.hash import Hash
from yonder.wem import get_wem_metadata
from yonder.enums import ClipAutomationType, PropID, SourceType, MusicTrackType
from yonder.util import logger
from yonder.audio import PlayContext, PlaybackState
from yonder.audio.multi_track_stream import MultiTrackStream
from .hirc_node import HIRCNode
from .base_types import (
    NodeBaseParams,
    BankSourceData,
    MediaInformation,
    RTPCGraphPoint,
    PropBundle,
    ClipAutomation,
    TrackSrcInfo,
    RTPC,
    StateChunk,
)
from .mixins import PropertyMixin, RtpcMixin, StateMixin


@dataclass(repr=False, eq=False)
class MusicTrack(StateMixin, RtpcMixin, PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 11
    flags: int = 0
    source_count: int = 0
    sources: list[BankSourceData] = field(default_factory=list)
    playlist_item_count: int = 0
    playlist: list[TrackSrcInfo] = field(default_factory=list)
    subtrack_count: int = 1
    clip_item_count: int = 0
    clip_items: list[ClipAutomation] = field(default_factory=list)
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    track_type: int = MusicTrackType.Normal.value
    look_ahead_time: int = 0

    @classmethod
    def new(
        cls,
        nid: Hash,
        wem: Path = None,
        begin_trim: float = 0.0,
        end_trim: float = 0.0,
        source_type: SourceType = SourceType.Streaming,
        props: dict[PropID, float] = None,
        parent: int | HIRCNode = 0,
    ) -> MusicTrack:
        obj = cls(nid)

        if wem:
            obj.add_source_from_wem(wem, begin_trim, end_trim, source_type=source_type)

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        obj.parent = parent
        return obj

    @property
    def wwise_link(self) -> str:
        return "https://www.audiokinetic.com/fr/public-library/2025.1.10_9233/?source=Help&id=defining_playback_behavior_for_music_tracks"

    @property
    def track_type_enum(self) -> MusicTrackType:
        return MusicTrackType(self.track_type)

    @property
    def duration(self) -> float:
        # TODO depends on the music track type
        return sum(
            x.play_at + x.source_duration - x.begin_trim_offset - x.end_trim_offset
            for x in self.playlist
        )

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
    def source_ids(self) -> list[int]:
        return [s.media_information.source_id for s in self.sources]

    def set_source(self, idx: int, wem: Path) -> None:
        try:
            wem_id = int(wem.stem)
        except ValueError:
            raise ValueError(f"Invalid sound filename {wem.stem}, must be numbers only")

        meta = get_wem_metadata(wem)
        size = meta["filesize"]
        duration = meta["duration"] * 1000

        media = self.sources[idx]
        media.source_id = wem_id
        media.media_information.in_memory_media_size = size

        item = self.playlist[idx]
        item.source_id = wem_id
        item.source_duration = duration

    def add_source_from_wem(
        self,
        wem: Path,
        event: int | HIRCNode = 0,
        begin_trim: float = 0.0,
        end_trim: float = 0.0,
        source_type: SourceType = SourceType.Embedded,
    ) -> BankSourceData:
        try:
            wem_id = int(wem.stem)
        except ValueError:
            raise ValueError(f"Invalid sound filename {wem.stem}, must be numbers only")

        meta = get_wem_metadata(wem)
        size = meta["filesize"]
        duration = meta["duration"] * 1000

        self.add_source(
            wem_id,
            size,
            duration,
            event=event,
            begin_trim=begin_trim,
            end_trim=end_trim,
            source_type=source_type,
        )

    def add_source(
        self,
        source_id: int,
        media_size: int,
        duration_ms: float,
        event: int | HIRCNode = 0,
        begin_trim: float = 0.0,
        end_trim: float = 0.0,
        source_type: SourceType = SourceType.Embedded,
    ) -> BankSourceData:
        if duration_ms < 500.0:
            logger.warning(
                f"{self}: duration of new source {source_id} is very short, not in ms?"
            )

        if self.playlist and not event:
            logger.warning(
                f"{self}: additional tracks should have an event ID associated"
            )

        if isinstance(event, HIRCNode):
            event = event.id
        elif not event:
            event = 0

        self.sources.append(
            BankSourceData(
                source_type=source_type,
                media_information=MediaInformation(int(source_id), media_size),
            )
        )

        begin_trim = abs(begin_trim)
        self.playlist.append(
            TrackSrcInfo(
                # track_id is always 0
                track_id=0,
                source_id=source_id,
                event_id=event,
                play_at=-begin_trim,  # TODO is play_at global?
                begin_trim_offset=begin_trim,
                end_trim_offset=-abs(end_trim),
                source_duration=duration_ms,
            )
        )

    def add_clip_automation(
        self,
        clip_type: ClipAutomationType,
        points: list[RTPCGraphPoint],
    ) -> ClipAutomation:
        clip = ClipAutomation(
            len(self.clip_items),
            clip_type,
            graph_points=points,
        )
        self.clip_items.append(clip)
        return clip

    def get_trims(self, idx: int = 0) -> tuple[float, float]:
        return (
            self.playlist[idx].begin_trim_offset,
            self.playlist[idx].end_trim_offset,
        )

    def set_trims(self, begin_trim: float, end_trim: float, idx: int = 0) -> None:
        if begin_trim < 0:
            raise ValueError("begin_trim must be > 0")

        if end_trim > 0:
            raise ValueError("end_trim must be <= 0")

        self.playlist[idx].begin_trim_offset = begin_trim
        self.playlist[idx].play_at = -begin_trim
        self.playlist[idx].end_trim_offset = end_trim

    def _build_pyo(self, my_pyo: PlaybackState) -> pyo.PyoObject:
        ctx = my_pyo.ctx
        props = ctx.properties

        return MultiTrackStream(
            list(self.playlist),
            ctx.get_wav_for_source,
            loop=(PropID.Loop in props),
            volume_db=props.get(PropID.Volume, 0.0),
            hpf_cents=props.get(PropID.HPF, 0.0),
            lpf_cents=props.get(PropID.LPF, 0.0),
            pitch_semitones=props.get(PropID.Pitch, 0.0),
            loop_start=props.get(PropID.LoopStart, 0.0),
            loop_end=props.get(PropID.LoopEnd, 0.0),
            xfade=props.get(PropID.LoopCrossfadeDuration, 0.05),
            attenuation=ctx.attenuation,
            distance=ctx.distance,
            angle=ctx.angle,
        )

    def play(self, ctx: PlayContext) -> None:
        # TODO Once we support different track_types we will have to do this differently
        my_pyo = self.pyo(ctx)
        if my_pyo.playing:
            return

        my_pyo.playing = True
        self.update_playback(ctx)
        self.register_end_trigger(ctx, self._on_track_end, 0, 0)
        my_pyo.play()

    def _on_track_end(self, ctx: PlayContext) -> None:
        self.stop(ctx)
        self.seek(ctx, 0)

    def seek(self, ctx: PlayContext, pos: float) -> None:
        self.pyo(ctx).output.seek(pos)

    def update_playback(self, ctx: PlayContext) -> None:
        if not self.is_pyo_initialized():
            return

        my_pyo = self.pyo(ctx)
        ctx = my_pyo.ctx
        stream: MultiTrackStream = my_pyo.output
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
        if not self.is_pyo_initialized():
            return

        my_pyo = self.pyo(ctx)
        ctx = my_pyo.ctx
        stream: MultiTrackStream = my_pyo.output
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
