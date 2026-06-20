from typing import Any, Container, NewType, TYPE_CHECKING
from pathlib import Path
import re
from random import randrange

if TYPE_CHECKING:
    from yonder import Soundbank


Hash = NewType("Hash", int)


class LookupTable:
    def __init__(self, data: dict[int, str] | Path = None, enable_write: bool = False):
        self._table = {}
        self.file = None
        self.enable_write = enable_write

        if isinstance(data, dict):
            self._table.update(data)
        elif isinstance(data, Path):
            self.file = data

            if data.is_file():
                for x in data.read_text("utf-8").splitlines():
                    x = x.strip()
                    if x.startswith("#"):
                        continue

                    h = calc_hash(x)
                    self._table[h] = x.strip(" \n")

    def prune(self, corpus: str) -> None:
        # Reduce to the hashes that are actually found in the corpus
        all_ints = set(int(x) for x in re.findall(r"\d+", corpus))

        base_hashes = set()
        if _lookup_tables and _lookup_tables[-1] != self:
            base_hashes = set(_lookup_tables[-1]._table.keys())

        self._table = {
            k: v
            for k, v in self._table.items()
            if k in all_ints and k not in base_hashes
        }

    def save(self, path: Path = None) -> None:
        if not path:
            path = self.file

        if not path:
            raise ValueError(
                "Path was None and this lookup table was not loaded from a file"
            )

        path.write_text("\n".join(list(self._table.values())))
        self.file = path

    def lookup_name(self, h: Hash, default: Any = None) -> str:
        return self._table.get(h, default)

    def __len__(self) -> int:
        return len(self._table)

    def __contains__(self, item: Hash) -> bool:
        return bool(self.lookup_name(item))

    def __getitem__(self, key: Hash) -> str:
        return self.lookup_name(key)

    def __setitem__(self, key: Hash, value: str) -> None:
        if not self.enable_write:
            raise ValueError("Write is disabled for this lookup table")

        self._table[key] = value
        if self.file:
            self.save()


class UniqueIdGenerator:
    def __init__(self, invalid_ids: Container[Hash] = None):
        self.invalid_ids = invalid_ids

    def __call__(self) -> Hash:
        return self.new_id()

    def new_id(self) -> Hash:
        while True:
            # IDs should be signed 32bit integers, although in practice
            # I've rarely seen any below 1000000 (expected I guess?)
            id = randrange(2**24, 2**31 - 1)
            if not self.invalid_ids or id not in self.invalid_ids:
                return id


def get_default_lookup_table_path() -> Path:
    from yonder.util import resource_dir

    return resource_dir() / "wwise_ids.txt"


def get_bank_lookup_table_path(bnk: "str | Soundbank") -> Path:
    from yonder import Soundbank

    if isinstance(bnk, Soundbank):
        name = bnk.get_name()
        if not name:
            name = bnk.bnk_dir.name
    else:
        name = str(bnk)

    return bnk.bnk_dir.parent / f"{name}_strings.txt"


def get_active_lookup_table() -> LookupTable:
    return _active_table


def load_lookup_table(path: Path, mark_active: bool = False) -> LookupTable:
    global _active_table

    # Reload it instead of doing nothing
    unload_lookup_table(path)

    # The active table will be used to calculate unknown hashes
    table = LookupTable(path, mark_active)
    _lookup_tables.insert(0, table)

    if mark_active:
        _active_table = table

    return table


def unload_lookup_table(path: Path) -> LookupTable:
    for t in _lookup_tables:
        if t.file == path:
            _lookup_tables.remove(t)
            return t


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


def calc_hash(input: str) -> Hash:
    h = fnv_1a(input)

    if _active_table is not None and h not in _active_table:
        _active_table[h] = input

    return h


def lookup_name(h: Hash, default: Any = None) -> str:
    for table in _lookup_tables:
        res = table.lookup_name(h)
        if res:
            return res

    return default


global_id_generator = UniqueIdGenerator()
_lookup_tables: list[LookupTable] = []
_active_table: LookupTable = None

# Load our default hash lookup dict
load_lookup_table(get_default_lookup_table_path(), False)
