from pathlib import Path
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
import shutil

from yonder import Soundbank, lookup_name
from yonder.types.base_types import StateChunk, DecisionTreeNode
from yonder.util import unpack_soundbank, resource_dir
from yonder.gamedata import Game


def build_bank_states_summary(bnk: Soundbank) -> dict[str, list[str]]:
    summary: dict[str, list[str]] = {}

    for node in bnk:
        if hasattr(node, "states") and isinstance(node.states, StateChunk):
            chunk: StateChunk = node.states
            for group in chunk.state_group_chunks:
                group_name = lookup_name(group.state_group_id, f"#{group.state_group_id}")
                states = [lookup_name(s.state_id, f"#{s.state_id}") for s in group.states]
                summary.setdefault(group_name, []).extend(states)

        if hasattr(node, "tree") and isinstance(node.tree, DecisionTreeNode):
            # arg: GameSync
            arguments = [lookup_name(arg.group_id, f"#{arg.group_id}") for arg in node.arguments]
            todo: list[tuple[DecisionTreeNode, int]] = [(n, 0) for n in node.tree.children]
            
            while todo:
                branch, depth = todo.pop()
                todo.extend((n, depth + 1) for n in branch.children)

                if branch.key > 0:
                    summary.setdefault(arguments[depth], []).append(branch.name)

    return summary


def build_gamestate_summary(game_path: Path, bnk2json_exe: Path) -> dict[str, list[str]]:
    summary = {}
    banks = list(game_path.glob("**/*.bnk"))

    with logging_redirect_tqdm():
        with tqdm(banks) as t:
            for bnk_file in t:
                t.set_description(bnk_file.stem)
                bnk_dir = bnk_file.parent / bnk_file.stem

                unpacked = False
                if not bnk_dir.is_dir():
                    bnk_file = unpack_soundbank(bnk2json_exe, bnk_file)
                    unpacked = True

                bnk = Soundbank.load(bnk_file)
                found = build_bank_states_summary(bnk)
                for group, states in found.items():
                    summary.setdefault(group, set()).update(states)

                if unpacked:
                    shutil.rmtree(bnk_dir)

    return {k: sorted(v) for k, v in summary.items()}


def load_gamestate_summary(game: Game) -> dict[str, list[str]]:
    if game == Game.EldenRing:
        json_path = resource_dir() / "gamedata" / "er" / "amx.json"
    elif game == Game.Nightreign:
        json_path = resource_dir() / "gamedata" / "nr" / "amx.json"
    else:
        raise ValueError(f"Game {game} is not supported yet")

    return json.load(json_path.open())


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <bnk2json.exe> <path/to/game/sd> <outfile.json>")
        sys.exit(1)

    bnk2json_exe = Path(sys.argv[1])
    game_path = Path(sys.argv[2])
    outfile = Path(sys.argv[3])

    summary = build_gamestate_summary(game_path, bnk2json_exe)
    json.dump(summary, outfile.open("w"), indent=2)
