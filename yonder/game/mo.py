"""Parsers for FromSoft's "musical orchestra" (MO) metadata files.

These sit next to the soundbanks in the game's sound archive and describe the
wwise content from the engine's side:

    eventinfo.eib             a registry of every sound event in the game
    soundbanksinfo.mobnkinfo  which events each soundbank provides
    <bankname>.moaei          per-bank, per-event MO parameters

Everything is little endian, all offsets are absolute file offsets, and all
tables are sorted so the engine can binary search them.

The formats below were reconstructed from the Nightreign files; the layout
sections are what the bytes actually are, the assumptions about what the data
is *used for* are collected at the bottom of this module.
"""

from dataclasses import dataclass, field
from pathlib import Path
import struct

from yonder.hash import Hash, fnv_1a


def _cstr(data: bytes, offset: int) -> str:
    """Read a NUL terminated utf-8 string."""
    return data[offset:data.index(b"\0", offset)].decode("utf-8")


# ---------------------------------------------------------------------------
# <bankname>.moaei
# ---------------------------------------------------------------------------
# Header
#   0x00  u8[4]  magic, "AEI\0"
#   0x04  u32    version, 0x00010000
#   0x08  u32    entry count
#   0x0c  u32    padding, 0
#
# Entry, 24 bytes each, starting at 0x10, sorted ascending by event id
#   0x00  u32    event id (wwise event name hash)
#   0x04  f32    unknown a, -1.0 in every entry observed so far
#   0x08  u64    offset of this entry's property array
#   0x10  u32    property count
#   0x14  f32    unknown b, -1.0 in every entry observed so far
#
# Property, 16 bytes each
#   0x00  u64    offset of the key string
#   0x08  u64    offset of the value string
#
# The strings are NUL terminated utf-8 and live in a blob following the
# property arrays. Values are strings even when they hold a number. A bank
# with no entries still ships a file, consisting of just the 16 byte header
# (e.g. AEG009_200.moaei).
#
# Key strings observed in Nightreign's cs_main.moaei (840 entries):
#   LimitedPlayFrame    819x, values "1" - "120"
#   SfxEnableDist        21x, values "17" - "80"
#   IsLocalPlayerOnly     3x, value "on"
# Entries normally carry a single property; three carry two, and one of those
# (event 3511058196) lists LimitedPlayFrame twice with the same value.


@dataclass
class AeiEntry:
    """One event's MO parameter overrides in a .moaei file."""

    event_id: Hash
    unknown_a: float
    unknown_b: float
    properties: list[tuple[str, str]] = field(default_factory=list)


def parse_moaei(path: Path) -> tuple[int, dict[Hash, AeiEntry]]:
    """Parse a .moaei file, returning its version and entries by event id."""
    data = Path(path).read_bytes()
    if data[:4] != b"AEI\0":
        raise ValueError(f"not a .moaei file: {path}")

    version, entry_count, _padding = struct.unpack_from("<III", data, 4)

    entries = {}
    offset = 0x10
    for _ in range(entry_count):
        event_id, unk_a, prop_offset, prop_count, unk_b = struct.unpack_from(
            "<IfQIf", data, offset
        )
        offset += 24

        properties = []
        for i in range(prop_count):
            key_offset, value_offset = struct.unpack_from(
                "<QQ", data, prop_offset + i * 16
            )
            properties.append((_cstr(data, key_offset), _cstr(data, value_offset)))

        entries[Hash(event_id)] = AeiEntry(Hash(event_id), unk_a, unk_b, properties)

    return version, entries


# ---------------------------------------------------------------------------
# soundbanksinfo.mobnkinfo
# ---------------------------------------------------------------------------
# Header
#   0x00  u8[4]  magic, "SBI\0"
#   0x04  u32    version, 0x00010000
#   0x08  u64    offset of the section table, 0x18
#   0x10  u64    section count, 2 in Nightreign
#
# Section, 32 bytes each
#   0x00  u8[16] guid
#   0x10  u64    bank count
#   0x18  u64    offset of this section's bank array
#
# Bank, 16 bytes each, sorted ascending by bank id
#   0x00  u32    bank id, the fnv1 hash of the bank name and identical to the
#                bank_id in that bank's BKHD section
#   0x04  u32    event count
#   0x08  u64    offset of this bank's event array, 0 when the count is 0
#
# Event, one u64 each, sorted ascending
#   bits  0-31   event id (wwise event name hash)
#   bit     32   flag, see the assumptions below
#   bits 33-63   0 in every entry observed so far
#
# The two sections in Nightreign hold 502 and 43 banks and their bank ids do
# not overlap. Both contain a mix of character (cs_cXXXX), voice (vcXXX) and
# map (cs_mXX) banks.


@dataclass
class SbiSection:
    """One section of a .mobnkinfo file."""

    guid: bytes
    # bank id -> [(event id, flag), ...]
    banks: dict[Hash, list[tuple[Hash, bool]]] = field(default_factory=dict)


def parse_mobnkinfo(path: Path) -> tuple[int, list[SbiSection]]:
    """Parse a .mobnkinfo file, returning its version and sections."""
    data = Path(path).read_bytes()
    if data[:4] != b"SBI\0":
        raise ValueError(f"not a .mobnkinfo file: {path}")

    version = struct.unpack_from("<I", data, 4)[0]
    section_offset, section_count = struct.unpack_from("<QQ", data, 8)

    sections = []
    for i in range(section_count):
        base = section_offset + i * 32
        guid = data[base:base + 16]
        bank_count, bank_offset = struct.unpack_from("<QQ", data, base + 16)

        section = SbiSection(guid)
        for j in range(bank_count):
            bank_id, event_count, event_offset = struct.unpack_from(
                "<IIQ", data, bank_offset + j * 16
            )
            events = (
                struct.unpack_from(f"<{event_count}Q", data, event_offset)
                if event_count
                else ()
            )
            section.banks[Hash(bank_id)] = [
                (Hash(e & 0xFFFFFFFF), bool(e >> 32)) for e in events
            ]

        sections.append(section)

    return version, sections


# ---------------------------------------------------------------------------
# eventinfo.eib
# ---------------------------------------------------------------------------
# Header
#   0x00  u8[4]  magic, "WWEI"
#   0x04  u32    version, 0x00080000
#   0x08  u64    unknown, 2
#   0x10  u64    unknown, 0
#   0x18  u64    file size
#   0x20  u64    section count, 2 in Nightreign
#   0x28  u64[]  one offset per section, pointing at a section header
#
# Section header, 24 bytes
#   0x00  u32    entry count
#   0x04  u32    section index, 0 and 1
#   0x08  u64    offset of the key array, always directly after this header
#   0x10  u64    offset of the flag array
#
# Key, 8 bytes each, sorted ascending when read as a u64, i.e. by sound type
# first and sound id second
#   0x00  u32    sound id, the numeric part of the FromSoft sound name
#   0x04  u32    sound type and flags
#                  bits 0-6   sound type, (letter - 'a') * 4
#                  bit    7   set on every entry of section 1, never on
#                             section 0
#                  bit   15   set on exactly two entries, both in section 0
#                             (sound ids 1023663504 and 1028663504, type c)
#
# Flag array, one u8 per entry, padded to a multiple of 8 bytes
#
# Sound types present in Nightreign's eventinfo.eib
#    0 -> a     8 -> c    20 -> f    24 -> g    32 -> i
#   48 -> m    56 -> o    60 -> p    72 -> s    84 -> v
#
# Combining the type letter and the sound id gives the wwise event name:
# "Play_" or "Stop_" + letter + the sound id padded to 9 digits, for example
# type 72 ('s') with sound id 806740 is Play_s000806740. Every one of the
# 16475 entries in section 0 hashes to an event id that soundbanksinfo
# .mobnkinfo also lists, so the reconstruction is exact.

SOUND_TYPES = {i * 4: chr(ord("a") + i) for i in range(26)}

SOUND_TYPE_MASK = 0x7F
SOUND_TYPE_FLAG_STOP = 0x80
SOUND_TYPE_FLAG_UNKNOWN = 0x8000


@dataclass
class EibEntry:
    """One sound in an eventinfo.eib section."""

    sound_id: int
    sound_type: int
    flag: bool

    @property
    def type_letter(self) -> str:
        return SOUND_TYPES.get(self.sound_type & SOUND_TYPE_MASK, "?")

    def event_name(self, prefix: str = "Play_") -> str:
        """Rebuild the wwise event name, e.g. Play_s000806740."""
        return f"{prefix}{self.type_letter}{self.sound_id:09}"

    def event_id(self, prefix: str = "Play_") -> Hash:
        return fnv_1a(self.event_name(prefix))


def parse_eventinfo(path: Path) -> tuple[int, list[list[EibEntry]]]:
    """Parse an eventinfo.eib file, returning its version and sections."""
    data = Path(path).read_bytes()
    if data[:4] != b"WWEI":
        raise ValueError(f"not an eventinfo.eib file: {path}")

    version = struct.unpack_from("<I", data, 4)[0]
    section_count = struct.unpack_from("<Q", data, 0x20)[0]
    section_offsets = struct.unpack_from(f"<{section_count}Q", data, 0x28)

    sections = []
    for section_offset in section_offsets:
        entry_count, _index, key_offset, flag_offset = struct.unpack_from(
            "<IIQQ", data, section_offset
        )

        entries = []
        for i in range(entry_count):
            sound_id, sound_type = struct.unpack_from("<II", data, key_offset + i * 8)
            entries.append(EibEntry(sound_id, sound_type, bool(data[flag_offset + i])))

        sections.append(entries)

    return version, sections


# ---------------------------------------------------------------------------
# Assumptions
# ---------------------------------------------------------------------------
# Everything below is inference, not observed format.
#
# None of the three files reference HIRC object ids. They are keyed purely on
# events, either by wwise event hash or by FromSoft sound type and id, so
# editing the contents of a soundbank cannot desynchronise them. From
# experience the engine does not care whether they are kept up to date, and
# the shipped files are not fully consistent with the shipped banks either:
# soundbanksinfo.mobnkinfo lists 224 event ids under cs_main that cs_main does
# not define, so the engine evidently tolerates entries that go nowhere.
#
# soundbanksinfo.mobnkinfo looks like FromSoft's binary replacement for
# wwise's SoundbanksInfo.xml, presumably so the engine can resolve an event to
# the bank that provides it and load that bank on demand. The two sections are
# probably two wwise projects, with the 16 byte value being the project guid.
#
# The flag on each event id means "this event starts something that loops and
# will not stop on its own". On cs_main it is set for 1024 events whose play
# target has a Loop property somewhere in its subtree and for none of the 3748
# that do not, the remaining 56 being events whose target is not in the bank
# at all. The engine presumably uses it to decide which playing events it has
# to track so it can stop them later.
#
# eventinfo.eib appears to be the global index of what sound ids exist, with
# section 0 listing the sounds that have a Play_ event and section 1 those
# that have a Stop_ event; bit 7 of the sound type marks the latter. The
# per-entry flag in section 0 is the same "loops forever" flag as in
# soundbanksinfo.mobnkinfo and agrees with it on all 16475 entries. The
# section 1 flag is set on a single entry (Stop_s000675700) and its meaning is
# unknown, as is bit 15 of the sound type.
#
# The .moaei files hold behaviour the engine layers on top of wwise rather
# than anything wwise itself understands:
#   LimitedPlayFrame   refuse to retrigger the event again within this many
#                      frames, which would explain why some sounds cannot be
#                      made to play in rapid succession
#   SfxEnableDist      distance in metres beyond which the event is not
#                      started at all
#   IsLocalPlayerOnly  only play for the local player in multiplayer
# The two floats are -1.0 in every entry seen so far, which most likely means
# "unset"; what they would hold otherwise is unknown.
