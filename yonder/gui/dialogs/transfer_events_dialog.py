from typing import Any
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.node_types import Event
from yonder.transfer import copy_wwise_events
from yonder.hash import calc_hash
from yonder.gui import style
from yonder.gui.widgets import add_generic_widget
from .select_nodes_dialog import select_nodes_of_type


def transfer_events_dialog(
    *,
    title: str = "Transfer Sounds",
    tag: str = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()
    elif dpg.does_item_exist(tag):
        dpg.delete_item(tag)

    src_bnk: Soundbank = None
    dst_bnk: Soundbank = None

    def on_source_bnk_selected(sender: str, path: Path, user_data: Any) -> None:
        nonlocal src_bnk
        src_bnk = Soundbank.load(path)

    def on_dest_bnk_selected(sender: str, path: Path, user_data: Any) -> None:
        nonlocal dst_bnk
        dst_bnk = Soundbank.load(path)

    def select_nodes() -> None:
        if not src_bnk:
            show_message("Select source bank first")
            return

        select_nodes_of_type(src_bnk, Event, on_nodes_selected, multiple=True)

    def on_nodes_selected(sender: str, nodes: list[Event], user_data: Any) -> None:
        selected: list[str] = dpg.get_value(f"{tag}_source_ids").splitlines()
        src_ids = set()

        for line in selected:
            h = line_to_hash(line)
            if h is not None:
                src_ids.add(h)

        for n in nodes:
            if n.id not in src_ids:
                name = n.lookup_name(f"#{n.id}")
                selected.append(name)

        dpg.set_value(f"{tag}_source_ids", "\n".join(selected))

    def line_to_hash(line: str) -> int:
        line: str = line.strip()
        if not line:
            return None

        if line.startswith("#"):
            return int(line[1:])

        if not line.startswith(("Play_", "Stop_")):
            line = "Play_" + line
        return calc_hash(line)

    def prune_ids(ids: list[str]) -> list[str]:
        # NOTE it's important to maintain the order
        pruned = []
        seen = set()

        for line in ids:
            h = line_to_hash(line)
            if h is not None and h not in seen:
                seen.add(h)
                pruned.append(line)

        return pruned

    def show_message(msg: str = None, color: tuple[int, int, int, int] = style.red) -> None:
        if not msg:
            dpg.hide_item(f"{tag}_notification")
            return

        dpg.configure_item(
            f"{tag}_notification",
            default_value=msg,
            color=color,
            show=True,
        )

    def on_okay() -> None:
        if not src_bnk:
            show_message("No source bank selected")
            return

        if not dst_bnk:
            show_message("No destination bank selected")
            return

        src_ids = prune_ids(dpg.get_value(f"{tag}_source_ids").splitlines())
        dst_ids = prune_ids(dpg.get_value(f"{tag}_dest_ids").splitlines())

        if not src_ids:
            show_message("No source IDs selected")
            return

        if len(src_ids) != len(dst_ids):
            show_message("Source and destination IDs not balanced")
            return

        for line in src_ids:
            src_play_id = line_to_hash(line)
            if src_play_id not in src_bnk:
                show_message(f"{line} not found in source bank")
                return

        for line in dst_ids:
            if line.startswith("#"):
                show_message("Destination IDs cannot be hashes")
                return

            dst_play_id = line_to_hash(line)
            if dst_play_id in dst_bnk:
                show_message(f"{line} already exists in destination bank")
                return

        event_map = {}
        for sid, did in zip(src_ids, dst_ids):
            src_explicit = sid.startswith(("Play_", "Stop_", "#"))
            dst_explicit = did.startswith(("Play_", "Stop_"))
            if src_explicit != dst_explicit:
                show_message("Cannot pair explicit with implicit event names")
                return

            if src_explicit:
                event_map[line_to_hash(sid)] = did
            else:
                play_evt = f"Play_{sid}"
                if play_evt in src_bnk:
                    event_map[play_evt] = f"Play_{did}"

                stop_evt = f"Stop_{sid}"
                if stop_evt in src_bnk:
                    event_map[stop_evt] = f"Stop_{did}"

        copy_wwise_events(src_bnk, dst_bnk, event_map)
        show_message("Yay!", color=style.blue)

    with dpg.window(
        label=title,
        width=400,
        height=400,
        autosize=True,
        no_saved_settings=True,
        tag=tag,
        on_close=lambda: dpg.delete_item(window),
    ) as window:
        add_generic_widget(
            Path,
            "Source Soundbank",
            on_source_bnk_selected,
            filetypes={"Soundbanks (.bnk, .json)": ["*.bnk", "*.json"]},
            tag=f"{tag}_source_bnk",
        )
        add_generic_widget(
            Path,
            "Destination Soundbank",
            on_dest_bnk_selected,
            filetypes={"Soundbanks (.bnk, .json)": ["*.bnk", "*.json"]},
            tag=f"{tag}_dest_bnk",
        )

        with dpg.group(horizontal=True):
            with dpg.group():
                dpg.add_text("Source Wwise IDs")
                dpg.add_input_text(
                    multiline=True,
                    height=300,
                    tag=f"{tag}_source_ids",
                )
            with dpg.group():
                dpg.add_text("Destination Wwise IDs")
                dpg.add_input_text(
                    multiline=True,
                    height=300,
                    tag=f"{tag}_dest_ids",
                )

        dpg.add_button(
            label="Select IDs...",
            callback=select_nodes,
        )

        dpg.add_text(
            """\
Transfer event structures from one soundbank to another. Usually you'll enter a wwise ID (x123456789) to copy all events associated with it. You may also use a #Hash or full name to copy individual events instead.""",
            wrap=580,
            color=style.light_blue,
        )

        dpg.add_spacer(height=3)
        dpg.add_separator()
        dpg.add_text(show=False, tag=f"{tag}_notification", color=style.red)

        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Scotty, beam them!", callback=on_okay, tag=f"{tag}_button_okay"
            )

    return tag
