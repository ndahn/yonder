from pathlib import Path
import json
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
import shutil

from yonder.hash import lookup_name
from yonder.enums import Game, GroupType
from yonder.types.soundbank import Soundbank
from yonder.types.switch_container import SwitchContainer
from yonder.types.mixins import DecisionTreeMixin, StateMixin, RtpcMixin
from yonder.util import unpack_soundbank, resource_dir


def build_bank_gamesync_summary(
    bnk: Soundbank,
) -> tuple[list[str], dict[str, list[str]], dict[str, list[str]]]:
    rtpcs: list[str] = []
    states: dict[str, list[str]] = {}
    switches: dict[str, list[str]] = {}

    for node in bnk:
        if isinstance(node, RtpcMixin):
            for rtpc in node.rtpcs:
                rtpcs.append(rtpc.get_name())

        if isinstance(node, StateMixin):
            for group in node.states.state_group_chunks:
                group_name = lookup_name(
                    group.state_group_id, f"#{group.state_group_id}"
                )
                state_values = [
                    lookup_name(s.state_id, f"#{s.state_id}") for s in group.states
                ]
                states.setdefault(group_name, []).extend(state_values)

        if isinstance(node, DecisionTreeMixin):
            # arg: GameSync
            arguments = [
                lookup_name(arg.group_id, f"#{arg.group_id}") for arg in node.arguments
            ]
            todo = [(n, 0) for n in node.tree.children]

            while todo:
                branch, depth = todo.pop()
                todo.extend((n, depth + 1) for n in branch.children)

                if branch.key > 0:
                    if node.group_types[depth] == GroupType.State:
                        states.setdefault(arguments[depth], []).append(branch.name)
                    else:
                        switches.setdefault(arguments[depth], []).append(branch.name)

        if isinstance(node, SwitchContainer):
            group = lookup_name(node.group_id, f"#{node.group_id}")

            if node.group_type == GroupType.State.value:
                switch_values = states.setdefault(group, [])
            else:
                switch_values = switches.setdefault(group, [])

            default = lookup_name(node.default_switch, f"#{node.default_switch}")
            switch_values.append(default)

            for switch in node.switch_groups:
                switch_values.append(
                    lookup_name(switch.switch_id, f"#{switch.switch_id}")
                )

    return rtpcs, states, switches


def build_gamesync_summary(
    game_path: Path, bnk2json_exe: Path
) -> dict[str, list[str]]:
    all_rtpcs: set[str] = set()
    all_states: dict[str, set[str]] = {}
    all_switches: dict[str, set[str]] = {}
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
                rtpcs, states, switches = build_bank_gamesync_summary(bnk)

                all_rtpcs.update(rtpcs)

                for group, group_values in states.items():
                    all_states.setdefault(group, set()).update(group_values)

                for group, group_values in switches.items():
                    all_switches.setdefault(group, set()).update(group_values)

                if unpacked:
                    shutil.rmtree(bnk_dir)

    return {
        "rtpcs": sorted(all_rtpcs),
        "states": {s: sorted(all_states[s]) for s in sorted(all_states) },
        "switches": {s: sorted(all_switches[s]) for s in sorted(all_switches) },
    }


def load_gamestate_summary(game: Game) -> dict[str, list[str]]:
    if game == Game.EldenRing:
        json_path = resource_dir() / "gamedata" / "er" / "states.json"
    elif game == Game.Nightreign:
        json_path = resource_dir() / "gamedata" / "nr" / "states.json"
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

    summary = build_gamesync_summary(game_path, bnk2json_exe)
    json.dump(summary, outfile.open("w"), indent=2)
