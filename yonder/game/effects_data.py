from __future__ import annotations
import base64
import re
import struct
from dataclasses import dataclass
from enum import IntEnum

from yonder.enums import EffectPlugin, EffectPluginType


# matches either:
#   a repeat group:      (<subscheme>)*<ref>      e.g. "(1i3f)*@0" or "(1i3f)*4"
#   a plain field group:  <count><type>            e.g. "4f", "i", "3i"
_TOKEN_RE = re.compile(
    r"\((?P<sub>[^()]*)\)\*(?P<ref>@?\d+)|(?P<count>\d*)(?P<type>[if])"
)
_PLAIN_RE = re.compile(r"(\d*)([if])")


def _parse_plain(scheme: str) -> list[tuple[int, str]]:
    # "1i3f" -> [(1, "i"), (3, "f")]
    return [(int(c) if c else 1, t) for c, t in _PLAIN_RE.findall(scheme)]


@dataclass
class EffectInfo:
    fxid: int
    byte_pattern: str
    fields: list[str]
    description: str = ""

    @classmethod
    def get(cls, effect: int | EffectPlugin) -> EffectInfo:
        if isinstance(effect, int):
            effect = EffectPlugin(effect)
        
        return EffectInfo(effect.value, *plugin_info[effect])

    @property
    def plugin_id(self) -> int:
        return self.fxid >> 16

    @property
    def plugin_enum(self) -> EffectPlugin:
        return EffectPlugin(self.plugin_id)

    @property
    def name(self) -> str:
        return self.plugin_enum.name

    @property
    def company_id(self) -> int:
        return self.fxid >> 4 & 0xFF

    @property
    def plugin_type(self) -> EffectPluginType:
        return EffectPluginType(self.fxid & 0xF)

    def decode_params(self, data: str) -> tuple[dict, bytes]:
        """Decode a base64 params blob according to self.byte_pattern.

        Pattern grammar:
          <count><type>       plain group, e.g. "4f" = 4 float32, "i" = 1 int32
          (<sub>)*<ref>       repeat group: <sub> is a plain pattern (e.g. "1i3f") repeated
                               either a literal number of times ("(1i3f)*4") or a number of
                               times equal to an earlier field's first value
                               ("(1i3f)*@0" repeats pattern[0] times)

        One entry is appended to `values` per top-level token, zipped against `self.fields`, so a repeat group counts as a single field whose value is a list oF values. Leftover bytes that don't fill a full word, or aren't consumed by the pattern, are returned as the second tuple element.
        """
        # our soundbank jsons never contain base64 padding, so we need to restore it
        padding = "=" * (-len(data) % 4)
        decoded = base64.b64decode(data + padding)
        n_words = len(decoded) // 4

        values = []
        word = 0

        for m in _TOKEN_RE.finditer(self.byte_pattern):
            if m.group("sub") is not None:
                sub_tokens = _parse_plain(m.group("sub"))
                ref = m.group("ref")
                if ref.startswith("@"):
                    idx = int(ref[1:])
                    if idx >= len(values):
                        raise ValueError(
                            f"repeat ref @{idx} refers to a field not yet decoded"
                        )
                    repeat_count = int(values[idx][0])
                else:
                    repeat_count = int(ref)

                group_rows = []
                for _ in range(repeat_count):
                    row = []
                    for count, typ in sub_tokens:
                        count = min(count, n_words - word)
                        if count <= 0:
                            break
                        row.extend(
                            struct.unpack(
                                f"<{count}{typ}", decoded[word * 4 : (word + count) * 4]
                            )
                        )
                        word += count

                    if not row:
                        break

                    group_rows.append(row)

                values.append(group_rows)
            else:
                count = int(m.group("count")) if m.group("count") else 1
                typ = m.group("type")
                count = min(count, n_words - word)

                if count <= 0:
                    raise ValueError("ran out of data while decoding effect params")

                values.append(
                    list(
                        struct.unpack(
                            f"<{count}{typ}", decoded[word * 4 : (word + count) * 4]
                        )
                    )
                )

                word += count

        trailing_bytes = decoded[word * 4 :]
        params = dict(zip(self.fields, values))
        return params, trailing_bytes

    def encode_params(self, params: dict | list, trailing: bytes = bytes()) -> str:
        """Inverse of decode_params. Re-packs field values back into a base64 params blob.

        `params` can be the dict decode_params returns (field_name -> values/rows), or a plain or a plain list of the same values in `self.fields` order. `trailing` is any bytes that didn't fill a full word (e.g. `self.trailing_bytes` from a prior decode) and is appended verbatim after the packed data.
        """
        if not self.byte_pattern or not self.fields:
            raise ValueError(f"{self.name} has no known decoder scheme yet")

        if isinstance(params, dict):
            try:
                values = [params[f] for f in self.fields]
            except KeyError as e:
                raise ValueError(f"missing field {e} for {self.name}") from e
        else:
            values = list(params)

        if len(values) != len(self.fields):
            raise ValueError(
                f"expected {len(self.fields)} field(s) for {self.name}, got {len(values)}"
            )

        chunks = []
        value_iter = iter(values)

        for m in _TOKEN_RE.finditer(self.byte_pattern):
            value = next(value_iter)

            if m.group("sub") is not None:
                sub_tokens = _parse_plain(m.group("sub"))
                ref = m.group("ref")
                if ref.startswith("@"):
                    idx = int(ref[1:])
                    expected_repeats = int(values[idx][0])
                else:
                    expected_repeats = int(ref)

                if len(value) != expected_repeats:
                    raise ValueError(
                        f"{self.name}: repeat group expected {expected_repeats} row(s) "
                        f"(from {ref}), got {len(value)}"
                    )

                for row in value:
                    row_iter = iter(row)
                    for count, typ in sub_tokens:
                        row_values = []
                        for _ in range(count):
                            try:
                                row_values.append(next(row_iter))
                            except StopIteration:
                                break

                        if not row_values:
                            break  # row ran out mid-group, same point decode_params stopped

                        chunks.append(
                            struct.pack(f"<{len(row_values)}{typ}", *row_values)
                        )

                        if len(row_values) < count:
                            break  # partial group consumed the rest of this row's data
            else:
                count = int(m.group("count")) if m.group("count") else 1
                typ = m.group("type")

                if len(value) > count:
                    raise ValueError(
                        f"{self.name}: field expected at most {count} value(s), got {len(value)}"
                    )

                if value:
                    chunks.append(struct.pack(f"<{len(value)}{typ}", *value))

        encoded = b"".join(chunks) + trailing
        # source params strings in our banks never carry base64 padding
        return base64.b64encode(encoded).decode("ascii").rstrip("=")


plugin_info = {
    EffectPlugin.None_: ("", [], ""),

    # --- source/codec markers: not effect params, left as placeholders ---
    EffectPlugin.BANK: ("", [], ""),
    EffectPlugin.PCM: ("", [], ""),
    EffectPlugin.ADPCM: ("", [], ""),
    EffectPlugin.XMA: ("", [], ""),
    EffectPlugin.VORBIS: ("", [], ""),
    EffectPlugin.WIIADPCM: ("", [], ""),
    EffectPlugin.PCMEX: ("", [], ""),
    EffectPlugin.EXTERNALSOURCE: ("", [], ""),
    EffectPlugin.XWMA: ("", [], ""),
    EffectPlugin.AAC: ("", [], ""),
    EffectPlugin.FILEPACKAGE: ("", [], ""),
    EffectPlugin.ATRAC9: ("", [], ""),
    EffectPlugin.VAGHEVAG: ("", [], ""),
    EffectPlugin.PROFILERCAPTURE: ("", [], ""),
    EffectPlugin.ANALYSISFILE: ("", [], ""),
    EffectPlugin.MIDI: ("", [], ""),
    EffectPlugin.OPUSNX: ("", [], ""),
    EffectPlugin.CAF: ("", [], ""),
    EffectPlugin.OPUS: ("", [], ""),
    EffectPlugin.OPUSWEM1: ("", [], ""),
    EffectPlugin.OPUSWEM2: ("", [], ""),
    EffectPlugin.SONY360: ("", [], ""),

    # --- confirmed against real params blobs ---
    EffectPlugin.WwiseSine: (
                "4f",
        ["frequency", "gain", "duration", "reserved"],
        "Pure sine tone at a fixed frequency and gain for a set duration",
    ),
    EffectPlugin.WwiseSilence: (
                "3f",
        ["duration", "random_min", "random_max"],
        "Silence for a duration, optionally randomized within a min/max range",
    ),
    EffectPlugin.WwiseToneGenerator: (
                "17f",
        ["gain", "freq"] + [f"unk{i}" for i in range(2, 17)],
        "Configurable tone/sweep generator",
    ),
    EffectPlugin.WwiseUnk1: ("", [], ""),
    EffectPlugin.WwiseUnk2: ("", [], ""),
    # TODO only band[0] decodes to sane values on my one sample; band[1]+ come out garbage, meaning band_count is probably NOT the real repeat source
    EffectPlugin.WwiseParametricEQ: (
                "1i(3f1i)*@0",
        ["band_count", "bands"],
        "band_count int32, followed by that many (gain:float, freq:float, "
        "q:float, flags:int) groups, repeated band_count times",
    ),
    EffectPlugin.WwiseDelay: (
                "4f",
        ["feedback", "delay_time_ms", "unk2", "flags"],
        "Single-tap delay",
    ),
    EffectPlugin.WwiseCompressor: ("", [], ""),
    EffectPlugin.WwiseExpander: ("", [], ""),
    EffectPlugin.WwisePeakLimiter: (
                "5f",
        ["threshold_db", "release_time", "lookahead", "unk3", "unk4"],
        "Limits peaks above threshold_db using release_time and lookahead",
    ),
    EffectPlugin.WwiseUnk3: ("", [], ""),
    EffectPlugin.WwiseUnk4: ("", [], ""),
    EffectPlugin.WwiseMatrixReverb: (
                "7f",
        ["predelay", "size", "unk2", "decay_db", "unk4", "unk5", "unk6"],
        "Matrix reverb",
    ),
    EffectPlugin.SoundSeedImpact: ("", [], ""),
    # TODO the remaining 26 words did not decode as sane floats in my samples
    EffectPlugin.WwiseRoomVerb: (
                "20f26i",
        [f"unk_f{i}" for i in range(20)] + [f"unk_i{i}" for i in range(26)],
        "Large multi-parameter room reverb (size, decay, HF/LF damping, early "
        "reflections, density, etc)",
    ),
    EffectPlugin.SoundSeedAirWind: ("", [], ""),
    EffectPlugin.SoundSeedAirWoosh: ("", [], ""),
    EffectPlugin.WwiseFlanger: ("", [], ""),
    EffectPlugin.WwiseGuitarDistortion: ("", [], ""),
    EffectPlugin.WwiseConvolutionReverb: (
                "14f",
        [f"unk{i}" for i in range(14)],
        "Convolves with an attached impulse-response sample",
    ),
    EffectPlugin.WwiseMeter: (
                "5f",
        ["attack_time", "release_time", "trigger_threshold_db", "unk3", "hold_time"],
        "Envelope-follower/meter, not an audible effect; drives RTPCs/threshold triggers",
    ),
    EffectPlugin.WwiseTimeStretch: ("", [], ""),
    EffectPlugin.WwiseTremolo: ("", [], ""),
    EffectPlugin.WwiseRecorder: ("", [], ""),
    EffectPlugin.WwiseStereoDelay: (
                "15f",
        [
            "filter_freq_l",
            "feedback_l",
            "filter_freq_r",
            "feedback_r",
            "unk4",
            "unk5",
            "delay_time_l_ms",
            "delay_time_r_ms",
            "wet_dry_mix",
            "output_floor_db",
            "unk10",
            "unk11",
            "unk12",
            "output_min_db",
            "output_max_db",
        ],
        "Independent per-channel delay/filter/feedback",
    ),
    EffectPlugin.WwisePitchShifter: ("", [], ""),
    EffectPlugin.WwiseHarmonizer: ("", [], ""),
    EffectPlugin.WwiseGain: (
                "2f",
        ["gain_db", "lfe_gain_db"],
        "Static gain stage with a separate LFE channel gain",
    ),
    EffectPlugin.WwiseSynthOne: ("", [], ""),
    EffectPlugin.WwiseReflect: ("", [], ""),
    EffectPlugin.System: ("", [], ""),
    EffectPlugin.Communication: ("", [], ""),
    EffectPlugin.ControllerHeadphones: ("", [], ""),
    EffectPlugin.ControllerSpeaker: ("", [], ""),
    EffectPlugin.NoOutput: ("", [], ""),
    EffectPlugin.WwiseSystemOutputSettings: ("", [], ""),
    EffectPlugin.SoundSeedGrain: ("", [], ""),
    EffectPlugin.MasteringSuite: ("", [], ""),
    EffectPlugin.WwiseAudioInput: ("", [], ""),
    EffectPlugin.WwiseMotionGenerator1: ("", [], ""),
    EffectPlugin.WwiseMotionGenerator2: ("", [], ""),
    EffectPlugin.WwiseMotionSource1: ("", [], ""),
    EffectPlugin.WwiseMotionSource2: ("", [], ""),
    EffectPlugin.WwiseMotion: ("", [], ""),
    EffectPlugin.AuroHeadphone: ("", [], ""),
    EffectPlugin.McDSPML1: ("", [], ""),
    EffectPlugin.McDSPFutzBox: ("", [], ""),
    EffectPlugin.IZotopeHybridReverb: ("", [], ""),
    EffectPlugin.IZotopeTrashDistortion: ("", [], ""),
    EffectPlugin.IZotopeTrashDelay: ("", [], ""),
    EffectPlugin.IZotopeTrashDynamicsMono: ("", [], ""),
    EffectPlugin.IZotopeTrashFilters: ("", [], ""),
    EffectPlugin.IZotopeTrashBoxModeler: ("", [], ""),
    EffectPlugin.IZotopeTrashMultibandDistortion: ("", [], ""),
    EffectPlugin.PlatinumMatrixSurroundMk2: ("", [], ""),
    EffectPlugin.PlatinumLoudnessMeter: ("", [], ""),
    EffectPlugin.PlatinumSpectrumViewer: ("", [], ""),
    EffectPlugin.PlatinumEffectCollection: ("", [], ""),
    EffectPlugin.PlatinumMeterWithFilter: ("", [], ""),
    EffectPlugin.PlatinumSimple3D: ("", [], ""),
    EffectPlugin.PlatinumUpmixer: ("", [], ""),
    EffectPlugin.PlatinumReflection: ("", [], ""),
    EffectPlugin.PlatinumDownmixer: ("", [], ""),
    EffectPlugin.PlatinumFlex: ("", [], ""),
    EffectPlugin.CodemastersEffect: ("", [], ""),
    EffectPlugin.Ubisoft: ("", [], ""),
    EffectPlugin.UbisoftEffect1: ("", [], ""),
    EffectPlugin.UbisoftMixer: ("", [], ""),
    EffectPlugin.UbisoftEffect2: ("", [], ""),
    EffectPlugin.MicrosoftSpatialSound: ("", [], ""),
    EffectPlugin.CPRimpleDelay: ("", [], ""),
    EffectPlugin.CPRVoiceBroadcastReceive1: ("", [], ""),
    EffectPlugin.CPRVoiceBroadcastSend1: ("", [], ""),
    EffectPlugin.CPRVoiceBroadcastReceive2: ("", [], ""),
    EffectPlugin.CPRVoiceBroadcastSend2: ("", [], ""),
    EffectPlugin.CrankcaseREVModelPlayer: ("", [], "")
}
