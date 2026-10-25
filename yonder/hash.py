from typing import Any, Container, NewType, TYPE_CHECKING
from pathlib import Path
import re
from random import Random

if TYPE_CHECKING:
    from yonder import Soundbank


Hash = NewType("Hash", int)


class LookupTable:
    """Names for Wwise hashes, backed by a plain one-name-per-line text file.

    Wwise stores only the FNV-1a hash of every name, so a soundbank on its own
    is a wall of numbers. A table maps those back: the shipped `wwise_ids.txt`
    for names common to the game, plus one file per bank for the names the
    user types in themselves.

    Besides the names it was given, a table can answer with *fuzzy* ones:
    guesses derived from the known names (neighbouring numbers, Play_ <-> Stop_)
    that only ever surface when their hash matches exactly, so a guess can
    never be wrong, only absent. They are kept apart from the real entries and
    are never written to the file.

    Parameters
    ----------
    data : dict of (int to str), or Path, optional
        Entries to start with, or the file to read them from. The file is
        remembered and becomes the target of `save`; it need not exist yet.
    enable_write : bool
        Allow new names to be recorded. Writing is refused outright otherwise,
        so a shared dictionary cannot pick up one bank's names by accident.
    fuzzy : bool
        Derive the guessed variants described above.
    """

    def __init__(
        self,
        data: "dict[Hash, str] | Path" = None,
        enable_write: bool = False,
        fuzzy: bool = True,
    ):
        self._table: dict[Hash, str] = {}
        self._fuzzy_table: dict[Hash, str] = {}
        self.file: Path = None
        self.enable_write = enable_write
        self.fuzzy = fuzzy

        if isinstance(data, dict):
            self._table.update(data)
        elif data is not None:
            self.file = Path(data)
            self._table.update(_read_table_file(self.file))

        if fuzzy:
            self.fuzzify()

    # === Lookup ========================================================

    def lookup_name(self, h: Hash, default: Any = None) -> str:
        """The name for a hash, a fuzzy guess for it, or `default`."""
        ret = self._table.get(h)
        if ret is not None:
            return ret

        return self._fuzzy_table.get(h, default)

    def __len__(self) -> int:
        return len(self._table)

    def __contains__(self, item: Hash) -> bool:
        return self.lookup_name(item) is not None

    def __getitem__(self, key: Hash) -> str:
        return self.lookup_name(key)

    def __setitem__(self, key: Hash, value: str) -> None:
        """Record a name, appending it to the file if there is one.

        Appending rather than rewriting: `calc_hash` lands here once for every
        name the user has never typed before, and rewriting the whole file
        each time would make a session's worth of renames quadratic.
        """
        if not self.enable_write:
            raise ValueError("Write is disabled for this lookup table")

        if not value or self._table.get(key) == value:
            return

        self._table[key] = value
        if self.fuzzy:
            self._fuzzy_table.update(_fuzzy_variants(value))

        if self.file:
            _append_table_file(self.file, value)

    # === Maintenance ===================================================

    def fuzzify(self) -> None:
        """Rebuild the guessed variants from the real entries."""
        self._fuzzy_table = {}
        for name in self._table.values():
            self._fuzzy_table.update(_fuzzy_variants(name))

    def prune(self, corpus: str) -> None:
        """Drop every entry the bank has no use for.

        Keeps only names whose hash actually turns up in `corpus` (the bank's
        json) and that no other loaded table already knows, so a bank's file
        ends up holding exactly what is unique to that bank.
        """
        used = {int(x) for x in re.findall(r"\d+", corpus)}
        known = _known_elsewhere(self)

        self._table = {
            h: name for h, name in self._table.items() if h in used and h not in known
        }

        if self.fuzzy:
            self.fuzzify()

    def save(self, path: Path = None) -> None:
        """Write the table out, one name per line.

        A table with nothing in it gets no file: a bank whose names are all
        known already has nothing to remember, and writing an empty one only
        litters the bank folder. An existing file is removed in that case, so
        a table pruned down to nothing leaves no stale content behind either.
        """
        path = Path(path) if path else self.file
        if not path:
            raise ValueError(
                "Path was None and this lookup table was not loaded from a file"
            )

        self.file = path

        if not self._table:
            path.unlink(missing_ok=True)
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(self._table.values()) + "\n", encoding="utf-8")


class UniqueIdGenerator:
    def __init__(self, invalid_ids: Container[Hash] = None):
        self.invalid_ids = invalid_ids
        self.rng = Random()

    def __call__(self) -> Hash:
        return self.new_id()

    def new_id(self) -> Hash:
        while True:
            # IDs should be signed 32bit integers, although in practice
            # I've rarely seen any below 1000000 (expected I guess?)
            id = self.rng.randrange(2**24, 2**31 - 1)
            if not self.invalid_ids or id not in self.invalid_ids:
                return id


# ---------------------------------------------------------------- file format


def _read_table_file(path: Path) -> dict[Hash, str]:
    """Read a name-per-line file. Blank lines and # comments are skipped."""
    if not path.is_file():
        return {}

    names = (line.strip() for line in path.read_text("utf-8").splitlines())

    # NOTE: not calc_hash, which would record the name straight back again
    return {fnv_1a(n): n for n in names if n and not n.startswith("#")}


def _append_table_file(path: Path, name: str) -> None:
    """Add one name to the end of a table file, creating it if need be."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as f:
        if _ends_mid_line(path):
            f.write("\n")  # a file from an older version may have no final newline
        f.write(name + "\n")


def _ends_mid_line(path: Path) -> bool:
    """Whether appending to the file would glue two names together."""
    try:
        with path.open("rb") as f:
            if f.seek(0, 2) == 0:
                return False  # empty, nothing to separate from

            f.seek(-1, 2)
            return f.read(1) != b"\n"
    except OSError:
        return False


def _fuzzy_variants(name: str) -> dict[Hash, str]:
    """Guesses derived from one name: neighbouring numbers, Play_ <-> Stop_."""
    variations = [name]
    if name.startswith("Play_"):
        variations.append(f"Stop_{name[5:]}")
    elif name.startswith("Stop_"):
        variations.append(f"Play_{name[5:]}")

    fuzz = set()
    for variant in variations:
        end = re.search(r"\d+$", variant)
        if not end:
            continue

        pad = len(end.group(0))
        number = int(end.group(0))
        if number > 0:
            fuzz.add(f"{variant[:-pad]}{number - 1:>0{pad}}")

        fuzz.add(f"{variant[:-pad]}{number + 1:>0{pad}}")

    return {fnv_1a(v): v for v in fuzz}


# ---------------------------------------------------------------- table paths


def get_default_lookup_table_path() -> Path:
    from yonder.util import resource_dir

    return resource_dir() / "wwise_ids.txt"


def get_bank_lookup_table_path(bnk: "str | Soundbank") -> Path:
    from yonder import Soundbank

    if isinstance(bnk, Soundbank):
        name = bnk.name
    else:
        name = str(bnk)

    return bnk.bnk_dir.parent / f"{name}_strings.txt"


# ---------------------------------------------------------------- the registry
#
# Every loaded table is searched, most recently loaded first, so a bank's own
# names win over the shipped dictionary. At most one of them is *active*: the
# one new names are recorded into, which is the open bank's.


def get_active_lookup_table() -> LookupTable:
    return _active_table


def load_lookup_table(path: Path, mark_active: bool = False) -> LookupTable:
    global _active_table

    # Reload it instead of doing nothing
    unload_lookup_table(path)
    table = LookupTable(path, enable_write=mark_active)
    _lookup_tables.insert(0, table)

    if mark_active:
        _active_table = table

    return table


def unload_lookup_table(path: Path) -> LookupTable:
    """Drop a table from the search path. Returns it, or None if not loaded."""
    global _active_table

    for t in _lookup_tables:
        if t.file == path:
            _lookup_tables.remove(t)

            # Or calc_hash would go on recording into a table nothing reads
            if t is _active_table:
                _active_table = None

            return t

    return None


def add_lookup_name(path: Path, name: str) -> None:
    """Record one name in a table file without loading it into the search path."""
    if name:
        _append_table_file(Path(path), name)


def _known_elsewhere(table: LookupTable) -> set[Hash]:
    """Hashes that some *other* loaded table can already name."""
    known = set()
    for t in _lookup_tables:
        if t is not table:
            known.update(t._table)
            known.update(t._fuzzy_table)

    return known


# ---------------------------------------------------------------- hashing


def fnv_1a(input: str) -> Hash:
    # This is the FNV-1a 32-bit hash
    FNV_BASE = 2166136261
    FNV_PRIME = 16777619

    input_bytes = input.lower().encode()

    result = FNV_BASE
    for byte in input_bytes:
        result *= FNV_PRIME
        # Ensure it stays within 32-bit range
        result &= 0xFFFFFFFF
        result ^= byte

    return result


def calc_hash(input: int | str) -> Hash:
    """The hash of a name, recording it if nothing can name it yet.

    Hashing is one way, so a name is only ever recoverable because someone
    wrote it down. Names that *any* loaded table already knows are left alone:
    copying those into the bank's file would just duplicate the shipped
    dictionary into every bank the user opens.
    """
    if isinstance(input, int):
        return input

    if input.startswith("#") and input[1:].isdigit():
        return int(input[1:])

    h = fnv_1a(input)

    if _active_table is not None and _active_table.enable_write:
        if lookup_name(h) is None:
            _active_table[h] = input

    return h


def lookup_name(h: Hash, default: Any = None) -> str:
    for table in _lookup_tables:
        res = table.lookup_name(h)
        if res is not None:
            return res

    return default


_global_id_generator = UniqueIdGenerator()
_lookup_tables: list[LookupTable] = []
_active_table: LookupTable = None

random_hash = _global_id_generator.new_id

# Load our default hash lookup dict
load_lookup_table(get_default_lookup_table_path(), False)
