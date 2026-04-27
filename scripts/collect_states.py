"""Collect {state_group_id: [state_id, ...]} from a Wwise JSON file.

Harvests state IDs from two sources:
  1. state_group_chunks entries (existing behaviour).
  2. MusicSwitchContainer decision trees: each depth level corresponds to
     arguments[depth].group_id, and every node's key is a state_id.

Usage:
    python collect_states.py <file.json> [output.json]
"""
import sys
import json
from yonder.hash import lookup_name


def _walk_tree(node: dict, arguments: list[dict], depth: int, result: dict) -> None:
    """Recurse into an MSC tree node, collecting keys by argument depth."""
    if depth < len(arguments):
        group_id = arguments[depth]["group_id"]
        key = node.get("key", 0)
        if key != 0:
            result.setdefault(group_id, set()).add(key)

    for child in node.get("children", []):
        _walk_tree(child, arguments, depth + 1, result)


def collect(
    data: object,
    result: dict[int, list[int]] = None,
    reverse: bool = True,
) -> dict[int, list[int]]:
    if result is None:
        result = {}

    # raw sets during collection to avoid duplicates cheaply
    raw: dict[int, set[int]] = {}

    def _collect(data: object) -> None:
        if isinstance(data, dict):
            # source 1: state_group_chunks
            if "state_group_id" in data:
                gid = data["state_group_id"]
                for s in data.get("states", []):
                    raw.setdefault(gid, set()).add(s["state_id"])

            # source 2: MusicSwitchContainer decision tree
            msc = data.get("MusicSwitchContainer")
            if isinstance(msc, dict):
                arguments = msc.get("arguments", [])
                tree = msc.get("tree")
                if arguments and isinstance(tree, dict):
                    # root node sits above depth 0 — its children are depth 0
                    for child in tree.get("children", []):
                        _walk_tree(child, arguments, 0, raw)

            for v in data.values():
                _collect(v)

        elif isinstance(data, list):
            for item in data:
                _collect(item)

    _collect(data)

    # resolve names and sort
    for gid, ids in raw.items():
        key   = lookup_name(gid, f"#{gid}") if reverse else gid
        vals  = sorted(lookup_name(x, f"#{x}") if reverse else x for x in ids)
        result.setdefault(key, [])
        result[key] = sorted(set(result[key]) | set(vals))

    return result


def main(infile: str = None, outfile: str = None, reverse: bool = True) -> None:
    if not infile:
        if len(sys.argv) < 2:
            print(f"Usage: {sys.argv[0]} <file.json> [output.json]")
            sys.exit(1)
        infile = sys.argv[1]
    if not outfile and len(sys.argv) > 2:
        outfile = sys.argv[2]

    print(f"Loading {infile} ...")
    with open(infile, encoding="utf-8") as f:
        data = json.load(f)

    groups = collect(data, reverse=reverse)
    print(
        f"Found {len(groups)} state group(s), "
        f"{sum(len(v) for v in groups.values())} state id(s) total."
    )

    out = json.dumps(groups, indent=2)
    if outfile:
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"Written to {outfile}")
    else:
        print(out)


if __name__ == "__main__":
    infile = "E:/Games/Elden Ring/Modding/Tools/yonder/test/cs_main/soundbank.json"
    #infile = "E:/Games/Elden Ring/Modding/Tools/yonder/test/mod/sd/cs_smain/soundbank.json"
    outfile = "states.json"
    main(infile, outfile, True)
