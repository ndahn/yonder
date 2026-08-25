from __future__ import annotations
from typing import Any
import base64
import re
import struct
from dataclasses import dataclass
from enum import Enum, IntEnum


class EffectPluginType(IntEnum):
    Source = 2
    Effect = 3


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
    decoder_scheme: str
    fields: list[str]
    description: str = ""

    @property
    def plugin_id(self) -> int:
        return self.fxid >> 16

    @property
    def company_id(self) -> int:
        return self.fxid >> 4 & 0xFF

    @property
    def plugin_type(self) -> EffectPluginType:
        return EffectPluginType(self.fxid & 0xF)

    def decode_params(self, data: str) -> tuple[dict, bytes]:
        """decode a base64 params blob according to self.decoder_scheme.

        scheme grammar:
          <count><type>       plain group, e.g. "4f" = 4 float32, "i" = 1 int32
          (<sub>)*<ref>       repeat group: <sub> is a plain scheme (e.g. "1i3f") repeated
                               either a literal number of times ("(1i3f)*4") or a number of
                               times equal to an earlier field's first value
                               ("(1i3f)*@0" repeats scheme[0] times)

        one entry is appended to `values` per top-level token, zipped against `self.fields`,
        so a repeat group counts as a single field whose value is a list oF values.
        leftover bytes that don't fill a full word, or aren't consumed by the scheme, are
        kept in `self.trailing_bytes` rather than silently dropped.
        """
        # our soundbank jsons never contain base64 padding, so we need to restore it
        padding = "=" * (-len(data) % 4)
        decoded = base64.b64decode(data + padding)
        n_words = len(decoded) // 4

        values = []
        word = 0

        for m in _TOKEN_RE.finditer(self.decoder_scheme):
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
        """inverse of decode_params. re-packs field values back into a base64 params blob.

        `params` can be the dict decode_params returns (field_name -> values/rows), or a plain or a plain list of the same values in `self.fields` order. `trailing` is any bytes that didn't fill a full word (e.g. `self.trailing_bytes` from a prior decode) and is appended verbatim after the packed data.
        """
        if not self.decoder_scheme or not self.fields:
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

        for m in _TOKEN_RE.finditer(self.decoder_scheme):
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


class EffectPlugin(EffectInfo, Enum):
    None_ = 0x00000000, "", [], ""

    # --- source/codec markers: not effect params, left as placeholders ---
    BANK = 0x00000001, "", [], ""
    PCM = 0x00010001, "", [], ""
    ADPCM = 0x00020001, "", [], ""
    XMA = 0x00030001, "", [], ""
    VORBIS = 0x00040001, "", [], ""
    WIIADPCM = 0x00050001, "", [], ""
    PCMEX = 0x00070001, "", [], ""
    EXTERNALSOURCE = 0x00080001, "", [], ""
    XWMA = 0x00090001, "", [], ""
    AAC = 0x000A0001, "", [], ""
    FILEPACKAGE = 0x000B0001, "", [], ""
    ATRAC9 = 0x000C0001, "", [], ""
    VAGHEVAG = 0x000D0001, "", [], ""
    PROFILERCAPTURE = 0x000E0001, "", [], ""
    ANALYSISFILE = 0x000F0001, "", [], ""
    MIDI = 0x00100001, "", [], ""
    OPUSNX = 0x00110001, "", [], ""
    CAF = 0x00120001, "", [], ""
    OPUS = 0x00130001, "", [], ""
    OPUSWEM1 = 0x00140001, "", [], ""
    OPUSWEM2 = 0x00150001, "", [], ""
    SONY360 = 0x00160001, "", [], ""

    # --- confirmed against real params blobs ---
    WwiseSine = (
        0x00640002,
        "4f",
        ["frequency", "gain", "duration", "reserved"],
        "Pure sine tone at a fixed frequency and gain for a set duration",
    )
    WwiseSilence = (
        0x00650002,
        "3f",
        ["duration", "random_min", "random_max"],
        "Silence for a duration, optionally randomized within a min/max range",
    )
    WwiseToneGenerator = (
        0x00660002,
        "17f",
        ["gain", "freq"] + [f"unk{i}" for i in range(2, 17)],
        "Configurable tone/sweep generator",
    )
    WwiseUnk1 = 0x00670003, "", [], ""
    WwiseUnk2 = 0x00680003, "", [], ""
    # TODO only band[0] decodes to sane values on my one sample; band[1]+ come out garbage, meaning band_count is probably NOT the real repeat source
    WwiseParametricEQ = (
        0x00690003,
        "1i(3f1i)*@0",
        ["band_count", "bands"],
        "band_count int32, followed by that many (gain:float, freq:float, "
        "q:float, flags:int) groups, repeated band_count times",
    )
    WwiseDelay = (
        0x006A0003,
        "4f",
        ["feedback", "delay_time_ms", "unk2", "flags"],
        "Single-tap delay",
    )
    WwiseCompressor = 0x006C0003, "", [], ""
    WwiseExpander = 0x006D0003, "", [], ""
    WwisePeakLimiter = (
        0x006E0003,
        "5f",
        ["threshold_db", "release_time", "lookahead", "unk3", "unk4"],
        "Limits peaks above threshold_db using release_time and lookahead",
    )
    WwiseUnk3 = 0x006F0003, "", [], ""
    WwiseUnk4 = 0x00700003, "", [], ""
    WwiseMatrixReverb = (
        0x00730003,
        "7f",
        ["predelay", "size", "unk2", "decay_db", "unk4", "unk5", "unk6"],
        "Matrix reverb",
    )
    SoundSeedImpact = 0x00740003, "", [], ""
    # TODO the remaining 26 words did not decode as sane floats in my samples
    WwiseRoomVerb = (
        0x00760003,
        "20f26i",
        [f"unk_f{i}" for i in range(20)] + [f"unk_i{i}" for i in range(26)],
        "Large multi-parameter room reverb (size, decay, HF/LF damping, early "
        "reflections, density, etc)",
    )
    SoundSeedAirWind = 0x00770002, "", [], ""
    SoundSeedAirWoosh = 0x00780002, "", [], ""
    WwiseFlanger = 0x007D0003, "", [], ""
    WwiseGuitarDistortion = 0x007E0003, "", [], ""
    WwiseConvolutionReverb = (
        0x007F0003,
        "14f",
        [f"unk{i}" for i in range(14)],
        "Convolves with an attached impulse-response sample",
    )
    WwiseMeter = (
        0x00810003,
        "5f",
        ["attack_time", "release_time", "trigger_threshold_db", "unk3", "hold_time"],
        "Envelope-follower/meter, not an audible effect; drives RTPCs/threshold triggers",
    )
    WwiseTimeStretch = 0x00820003, "", [], ""
    WwiseTremolo = 0x00830003, "", [], ""
    WwiseRecorder = 0x00840003, "", [], ""
    WwiseStereoDelay = (
        0x00870003,
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
    )
    WwisePitchShifter = 0x00880003, "", [], ""
    WwiseHarmonizer = 0x008A0003, "", [], ""
    WwiseGain = (
        0x008B0003,
        "2f",
        ["gain_db", "lfe_gain_db"],
        "Static gain stage with a separate LFE channel gain",
    )
    WwiseSynthOne = 0x00940002, "", [], ""
    WwiseReflect = 0x00AB0003, "", [], ""
    System = 0x00AE0007, "", [], ""
    Communication = 0x00B00007, "", [], ""
    ControllerHeadphones = 0x00B10007, "", [], ""
    ControllerSpeaker = 0x00B30007, "", [], ""
    NoOutput = 0x00B50007, "", [], ""
    WwiseSystemOutputSettings = 0x03840009, "", [], ""
    SoundSeedGrain = 0x00B70002, "", [], ""
    MasteringSuite = 0x00BA0003, "", [], ""
    WwiseAudioInput = 0x00C80002, "", [], ""
    WwiseMotionGenerator1 = 0x01950002, "", [], ""
    WwiseMotionGenerator2 = 0x01950005, "", [], ""
    WwiseMotionSource1 = 0x01990002, "", [], ""
    WwiseMotionSource2 = 0x01990005, "", [], ""
    WwiseMotion = 0x01FB0007, "", [], ""
    AuroHeadphone = 0x044C1073, "", [], ""
    McDSPML1 = 0x00671003, "", [], ""
    McDSPFutzBox = 0x006E1003, "", [], ""
    IZotopeHybridReverb = 0x00021033, "", [], ""
    IZotopeTrashDistortion = 0x00031033, "", [], ""
    IZotopeTrashDelay = 0x00041033, "", [], ""
    IZotopeTrashDynamicsMono = 0x00051033, "", [], ""
    IZotopeTrashFilters = 0x00061033, "", [], ""
    IZotopeTrashBoxModeler = 0x00071033, "", [], ""
    IZotopeTrashMultibandDistortion = 0x00091033, "", [], ""
    PlatinumMatrixSurroundMk2 = 0x006E0403, "", [], ""
    PlatinumLoudnessMeter = 0x006F0403, "", [], ""
    PlatinumSpectrumViewer = 0x00710403, "", [], ""
    PlatinumEffectCollection = 0x00720403, "", [], ""
    PlatinumMeterWithFilter = 0x00730403, "", [], ""
    PlatinumSimple3D = 0x00740403, "", [], ""
    PlatinumUpmixer = 0x00750403, "", [], ""
    PlatinumReflection = 0x00760403, "", [], ""
    PlatinumDownmixer = 0x00770403, "", [], ""
    PlatinumFlex = 0x00780403, "", [], ""
    CodemastersEffect = 0x00020403, "", [], ""
    Ubisoft = 0x00640332, "", [], ""
    UbisoftEffect1 = 0x04F70803, "", [], ""
    UbisoftMixer = 0x04F80806, "", [], ""
    UbisoftEffect2 = 0x04F90803, "", [], ""
    MicrosoftSpatialSound = 0x00AA1137, "", [], ""
    CPRimpleDelay = 0x000129A3, "", [], ""
    CPRVoiceBroadcastReceive1 = 0x000229A2, "", [], ""
    CPRVoiceBroadcastSend1 = 0x000329A3, "", [], ""
    CPRVoiceBroadcastReceive2 = 0x000429A2, "", [], ""
    CPRVoiceBroadcastSend2 = 0x000529A3, "", [], ""
    CrankcaseREVModelPlayer = 0x01A01052, "", [], ""

    @classmethod
    def _missing_(cls, value: Any) -> EffectPlugin:
        if isinstance(value, int):
            for pid in cls:
                if pid.fxid == value:
                    return pid

        return super()._missing_(value)
