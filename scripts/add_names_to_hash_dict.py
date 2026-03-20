from typing import Iterable
import time
from pathlib import Path
from tqdm import tqdm, trange

from yonder.enums import SoundType


def generate_names() -> Iterable[str]:
    # NOTE Adjust this as needed
    for i in trange(0, 10000, 1):
        yield f"_CL_c{i:04d}"
        yield f"c{i:04d}"


def expand_hash_dict(dict_path: Path, write: bool = True) -> tuple[int, list[str]]:
    lines = set(dict_path.read_text().splitlines())
    prev_size = len(lines)
    lines.update(n for n in generate_names())

    table = sorted(lines)
    if write:
        dict_path.write_text("\n".join(table))

    return (len(table) - prev_size, table)


if __name__ == "__main__":
    res_dir = Path(__file__).parent.parent / "resources"
    input = res_dir / "wwise_ids.txt"

    now = time.time()
    new_lines, total = expand_hash_dict(input, True)
    print(f"Added {new_lines} new entries for a total of {len(total)}, took {time.time() - now}s")
