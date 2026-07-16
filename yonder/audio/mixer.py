from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import networkx as nx
import pyo
from pyo import sndinfo

from yonder import Soundbank, HIRCNode
from yonder.types import Sound, MusicTrack, MusicSegment
from yonder.types.base_types import RTPC, StateGroup, ClipAutomation, RTPCGraphPoint
from yonder.types.mixins import PropertyMixin, StateMixin
from yonder.enums import PropID, RtpcAccum, MarkerId, ClipAutomationType
from yonder.interpolation import interpolate


def db_to_amp(db: float) -> float:
    # volume properties are stored in dB
    return 10.0 ** (db / 20.0)


def cents_to_speed(cents: float) -> float:
    # pitch properties are stored in cents, applied as playback speed
    return 2.0 ** (cents / 1200.0)


def make_interp_table(sample_rate: int, points: list[RTPCGraphPoint]) -> pyo.DataTable:
    dur = points[-1].from_
    n = dur * sample_rate
    data = [0.0] * n

    # Interval before the first interpolation point
    x0 = points[0].from_ * sample_rate
    data[:x0] = points[0].to

    p_idx = 0
    p = points[0]
    p_next = points[1]

    for i in range(x0, n):
        x = i / sample_rate
        if x >= p_next.from_:
            if p_idx + 1 >= len(points):
                break

            p_idx += 1
            p = p_next
            p_next = points[p_idx + 1]

        data[i] = interpolate(p.interpolation, x, p.to, p_next.to)

    return pyo.DataTable(size=n, init=data)


@dataclass
class Voice:
    audiofile: Path = None
    loop: bool = False
    # loop markers in seconds; end <= start means loop the whole file
    loop_start: float = 0.0
    loop_end: float = 0.0

    # TODO apply on top
    rtpc: dict[RTPC, float] = field(default_factory=dict)
    states: dict[StateGroup, float] = field(default_factory=dict)
    clips: dict[ClipAutomation, float] = field(default_factory=dict)

    # every PyoObject must stay referenced or pyo's gc silences the voice
    chain: list[pyo.PyoObject] = field(default_factory=list)
    # SigTo per parameter so runtime changes glide instead of clicking
    ctrls: dict[PropID, pyo.SigTo] = field(default_factory=dict)

    def set_pitch(self, pitch: float, absolute: bool) -> None:
        if absolute:
            self.ctrls[PropID.Pitch].value = cents_to_speed(pitch)
        else:
            self.ctrls[PropID.Pitch].value += cents_to_speed(pitch)

    def set_highpass(self, hpf: float, absolute: bool) -> None:
        if absolute:
            self.ctrls[PropID.HPF].value = hpf
        else:
            self.ctrls[PropID.HPF].value += hpf

    def set_lowpass(self, lpf: float, absolute: bool) -> None:
        if absolute:
            self.ctrls[PropID.LPF].value = lpf
        else:
            self.ctrls[PropID.LPF].value += lpf

    def set_volume(self, vol: float, absolute: bool) -> None:
        if absolute:
            self.ctrls[PropID.Volume].value = db_to_amp(vol)
        else:
            self.ctrls[PropID.Volume].value += db_to_amp(vol)

    def build(self, fade: float = 0.05) -> pyo.PyoObject:
        # TODO LPF|HPF 0-100 -> Hz curve?
        self.ctrls = {
            PropID.Pitch: pyo.SigTo(cents_to_speed(0.0), fade),
            PropID.HPF: pyo.SigTo(0.0, fade),
            PropID.LPF: pyo.SigTo(0.0, fade),
            PropID.Volume: pyo.SigTo(db_to_amp(0.0), fade),
        }
        c = self.ctrls

        if self.loop:
            if self.loop_end <= self.loop_start:
                self.loop_end = sndinfo(self.audiofile)[1]

            # marker loop: SfPlayer only loops whole files, Looper loops a table region
            table = pyo.SndTable(str(self.audiofile))
            src = pyo.Looper(
                table,
                pitch=c[PropID.Pitch],
                start=self.loop_start,
                dur=self.loop_end - self.loop_start,
                xfade=0,
                startfromloop=True,  # False: play intro once, then loop the region
            )
        else:
            src = pyo.SfPlayer(
                str(self.audiofile), speed=c[PropID.Pitch], loop=self.loop
            )

        # fixed order for all branches: source -> HPF -> LPF -> gain
        hp = pyo.ButHP(src, freq=c[PropID.HPF])
        lp = pyo.ButLP(hp, freq=c[PropID.LPF])
        tail = lp * c[PropID.Volume]

        self.chain = [src, hp, lp, tail]
        return tail

    def start(self) -> None:
        for obj in self.chain:
            obj.play()

    def stop(self) -> None:
        for obj in self.chain:
            obj.stop()


class NewPlayer:
    def __init__(self):
        self._default_fade_time = 0.05
        self._voices: list[Voice] = []

        self._server = pyo.Server().boot()
        # mixes the voice branches; time smooths per-voice amp changes
        self._mixer = pyo.Mixer(outs=1, chnls=1, time=self._default_fade_time)
        # final volume adjustment
        self._gate = pyo.SigTo(value=1.0, time=self._default_fade_time)
        # master chain: mixer -> gate -> dac
        self._master = self._mixer[0] * self._gate
        self._master.out()

    def __del__(self):
        self._server.stop()
        self._server.shutdown()
        self._server = None

    def start(self) -> None:
        self._server.start()

    def stop(self) -> None:
        self._server.stop()

    def play(self) -> None:
        for voice in self._voices:
            voice.start()

    def set_volume(self, vol: float) -> None:
        self._gate.setValue(vol, time=self._default_fade_time)

    def set_muted(self, muted: bool) -> None:
        self._gate.setValue(0.0 if muted else 1.0, time=self._default_fade_time)

    def fade(self, target_vol: float, duration: float) -> None:
        self._gate.setValue(target_vol, time=duration)

    def __getitem__(self, idx: int) -> Voice:
        return self._voices[idx]

    def __len__(self) -> int:
        return len(self._voices)

    def from_hierarchy(
        self, bnk: Soundbank, root: int | HIRCNode, full_tree: bool = False
    ) -> NewPlayer:
        self.stop()

        if isinstance(root, HIRCNode):
            root = root.id

        if full_tree:
            root, tree = next(bnk.find_event_subgraphs_for(root))
        else:
            tree = bnk.get_subtree(root, True)

        leafs = [n for (n, d) in tree.out_degree if d == 0]
        voices: dict[int, Voice] = {}

        for branch in nx.all_simple_paths(tree, root, leafs):
            leaf_id = branch[-1]

            if leaf_id not in voices:
                voice = Voice()
                voices[leaf_id] = voice
                leaf_node = bnk.get(leaf_id)

                if isinstance(leaf_node, Sound):
                    voice.audiofile = bnk.get_wem_path(
                        leaf_node.source_id, leaf_node.bank_source_data.source_type
                    )
                elif isinstance(leaf_node, MusicTrack):
                    # TODO what to do with tracks that have multiple sources?
                    voice.audiofile = bnk.get_wem_path(
                        leaf_node.source_ids[0], leaf_node.sources[0].source_type
                    )
                    # TODO trims
                    for clip in leaf_node.clip_items:
                        table = make_interp_table(
                            self._server.getSampleRate(), clip.graph_points
                        )
                        if clip.auto_type == ClipAutomationType.Volume:
                            # TODO
                            pass

            voice = voices[leaf_id]

            for nid in reversed(branch[:-1]):
                node = bnk[nid]
                if isinstance(node, PropertyMixin):
                    for bundle in node.properties:
                        if bundle.prop_enum == PropID.Volume:
                            voice.set_volume(bundle.value, False)
                        elif bundle.prop_enum == PropID.HPF:
                            voice.set_highpass(bundle.value, False)
                        elif bundle.prop_enum == PropID.LPF:
                            voice.set_lowpass(bundle.value, False)
                        elif bundle.prop_enum == PropID.Pitch:
                            voice.set_pitch(bundle.value, False)
                        elif bundle.prop_enum == PropID.Loop:
                            voice.loop = True
                        else:
                            # Other properties are ignored for now
                            pass

                if isinstance(node, StateMixin):
                    # TODO collect states
                    pass

                if hasattr(node, "rtpcs"):
                    # TODO collect rtpcs
                    pass

                # TODO attenuations

                if isinstance(node, MusicSegment):
                    voice.loop_start = node.get_marker_pos(MarkerId.LoopStart)
                    voice.loop_end = node.get_marker_pos(MarkerId.LoopEnd)

        # build one pyo chain per leaf and register it as a mixer voice
        for idx, voice in enumerate(voices.values()):
            if voice.audiofile is None:
                continue

            tail = voice.build(self._default_fade_time)
            voice.stop()
            self._mixer.addInput(idx, tail)
            self._mixer.setAmp(idx, 0, 0.0)

        self._voices = list(voices.values())
        return self
