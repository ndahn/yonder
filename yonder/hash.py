from typing import Any, Container
from pathlib import Path
from random import randrange

from yonder.util import resource_data


global_hash_dict: dict[int, str] = {}


def calc_hash(input: str) -> int:
    # This is the FNV-1a 32-bit hash taken from rewwise
    # https://github.com/vswarte/rewwise/blob/127d665ab5393fb7b58f1cade8e13a46f71e3972/analysis/src/fnv.rs#L6
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


def load_lookup_table(path: Path = None) -> dict[int, str]:
    if not path:
        pairs = resource_data("wwise_ids.txt").splitlines()
    else:
        pairs = [x.strip() for x in path.read_text().splitlines()]

    table = {}
    for x in pairs:
        if x.startswith("#"):
            continue

        h = calc_hash(x)
        table[h] = x.strip(" \n")

    return table


def lookup_name(h: int, default: Any = None) -> str:
    global global_hash_dict

    if not global_hash_dict:
        global_hash_dict.update(load_lookup_table())

    return global_hash_dict.get(h, default)


class UniqueIdGenerator:
    def __init__(self, invalid_ids: Container[int] = None):
        self.invalid_ids = invalid_ids

    def __call__(self) -> int:
        return self.new_id()

    def new_id(self) -> int:
        while True:
            # IDs should be signed 32bit integers, although in practice
            # I've rarely seen any below 1000000 (expected I guess?)
            id = randrange(2**24, 2**31 - 1)
            if not self.invalid_ids or id not in self.invalid_ids:
                return id


global_id_generator = UniqueIdGenerator()
