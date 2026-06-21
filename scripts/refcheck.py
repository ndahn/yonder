"""List backward and forward references in a deserialized Wwise soundbank.

A "reference" is any leaf integer in an object body that matches the id of
another object in the same bank's HIRC section. A reference is "backward" when
the referenced object appears earlier in the object list than the object that
holds the reference, and "forward" when it appears later.

Most Wwise references must be backward: the referenced object has to be loaded
before the object that points at it (children lists, action targets, in-bank
modulators bound through RTPCs, and so on). Forward references are the usual
cause of a bank that fails to load with a missing reference.

Usage:
    python refcheck.py <soundbank.json> [more.json ...]
"""

import json
import sys
from collections import defaultdict


def fnv1_32(text):
    """Wwise FNV-1 32-bit hash of a name (names are lowercased first)."""
    h = 2166136261
    for byte in text.lower().encode("utf-8"):
        h = (h * 16777619) & 0xFFFFFFFF
        h ^= byte
    return h


def object_id(obj):
    """Return the numeric id of a HIRC object, hashing the name if needed."""
    ident = obj["id"]
    if "Hash" in ident:
        return ident["Hash"]
    return fnv1_32(ident["String"])


def object_kind(obj):
    """Return the body tag of a HIRC object, e.g. 'Sound' or 'TimeModulator'."""
    return next(iter(obj["body"]))


class Reference:
    """A single id reference from one object to another in the same bank."""

    def __init__(
        self, src_id, src_kind, src_pos, dst_id, dst_kind, dst_pos, field, path
    ):
        self.src_id = src_id
        self.src_kind = src_kind
        self.src_pos = src_pos
        self.dst_id = dst_id
        self.dst_kind = dst_kind
        self.dst_pos = dst_pos
        self.field = field
        self.path = path

    @property
    def is_forward(self):
        return self.dst_pos > self.src_pos

    @property
    def direction(self):
        return "FORWARD" if self.is_forward else "backward"

    def __str__(self):
        return (
            "{dir:7s} {sk}({si}) pos {sp} --{field}--> {dk}({di}) pos {dp}  {path}"
        ).format(
            dir=self.direction,
            sk=self.src_kind,
            si=self.src_id,
            sp=self.src_pos,
            field=self.field,
            dk=self.dst_kind,
            di=self.dst_id,
            dp=self.dst_pos,
            path=self.path,
        )


class SoundBank:
    """A deserialized soundbank with its HIRC objects indexed by id and position."""

    def __init__(self, path):
        self.path = path
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        self.objects = self._find_hirc(data)
        self.id_to_pos = {object_id(o): n for n, o in enumerate(self.objects)}
        self.id_to_kind = {object_id(o): object_kind(o) for o in self.objects}

    @staticmethod
    def _find_hirc(data):
        for section in data["sections"]:
            body = next(iter(section["body"]))
            if body == "HIRC":
                return section["body"]["HIRC"]["objects"]
        raise ValueError("no HIRC section found")

    def references(self):
        """Yield every Reference found in the bank, in object order."""
        known = self.id_to_pos
        for obj in self.objects:
            src_id = object_id(obj)
            src_kind = object_kind(obj)
            src_pos = known[src_id]
            for field, value, path in self._walk(obj["body"]):
                if isinstance(value, int) and value in known and value != src_id:
                    yield Reference(
                        src_id,
                        src_kind,
                        src_pos,
                        value,
                        self.id_to_kind[value],
                        known[value],
                        field,
                        path,
                    )

    def _walk(self, node, field=None, path=""):
        """Walk a body tree yielding (leaf_key, leaf_value, json_path) tuples."""
        if isinstance(node, dict):
            for key, value in node.items():
                yield from self._walk(value, key, path + "/" + str(key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                yield from self._walk(value, field, path + "[" + str(index) + "]")
        else:
            yield field, node, path


def report(path):
    """Print every reference in a bank plus a per-field forward/backward summary."""
    bank = SoundBank(path)
    refs = list(bank.references())

    print("=" * 80)
    print(path)
    print("{} objects, {} in-bank references".format(len(bank.objects), len(refs)))
    print("-" * 80)

    forward = [r for r in refs if r.is_forward]
    backward = [r for r in refs if not r.is_forward]

    print("backward references ({}):".format(len(backward)))
    for ref in backward:
        print("  " + str(ref))

    print("forward references ({}):".format(len(forward)))
    for ref in forward:
        print("  " + str(ref))

    print("-" * 80)
    print("per-field summary (field: backward / forward):")
    counts = defaultdict(lambda: [0, 0])
    for ref in refs:
        counts[ref.field][1 if ref.is_forward else 0] += 1
    for field in sorted(counts):
        back, fwd = counts[field]
        mark = "  <-- has forward refs" if fwd else ""
        print("  {:18s} {:4d} / {:<4d}{}".format(field, back, fwd, mark))
    print()


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    for path in argv[1:]:
        report(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
