from typing import Any
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.node_types import Event
from yonder.transfer import copy_wwise_events
from yonder.hash import calc_hash
from yonder.util import repack_soundbank
from yonder.gui import style
from yonder.gui.widgets import add_generic_widget, add_paragraphs
from yonder.gui.helpers import shorten_path
from yonder.gui.config import get_config
from .select_nodes_dialog import select_nodes_of_type


def mass_transfer_dialog(
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

        show_message()
        select_nodes_of_type(
            src_bnk,
            Event,
            on_nodes_selected,
            multiple=True,
            get_node_label=lambda n: n.get_wwise_id(f"#{n.id}"),
            return_labels=True,
        )

    def swap_banks() -> None:
        nonlocal src_bnk, dst_bnk

        if not src_bnk:
            show_message("No source bank selected")
            return

        if not dst_bnk:
            show_message("No destination bank selected")
            return

        show_message()
        src_bnk, dst_bnk = dst_bnk, src_bnk

        dpg.set_value(f"{tag}_source_bnk", shorten_path(src_bnk.bnk_file))
        dpg.set_value(f"{tag}_dest_bnk", shorten_path(dst_bnk.bnk_file))

    def swap_ids() -> None:
        src_labels = dpg.get_value(f"{tag}_source_ids")
        dst_labels = dpg.get_value(f"{tag}_dest_ids")
        dpg.set_value(f"{tag}_source_ids", dst_labels)
        dpg.set_value(f"{tag}_dest_ids", src_labels)

    def on_nodes_selected(sender: str, selected: list[str], user_data: Any) -> None:
        src_labels: list[str] = dpg.get_value(f"{tag}_source_ids").splitlines()
        src_ids = set()
        new_items = []

        for line in src_labels:
            h = line_to_hash(line)
            if h is not None:
                src_ids.add(h)

        for label in selected:
            h = line_to_hash(label)
            if h not in src_ids:
                new_items.append(label)

        # Update the source ids text box
        src_labels.extend(new_items)
        dpg.set_value(f"{tag}_source_ids", "\n".join(src_labels))

        # Update the dest ids text box
        dst_labels: list[str] = dpg.get_value(f"{tag}_dest_ids").splitlines()

        # Remove empty lines at the end
        last_nonempty = 0
        for i, label in enumerate(reversed(dst_labels)):
            if label.strip():
                last_nonempty = -i
                break

        if last_nonempty == 0:
            last_nonempty = None

        dst_labels = dst_labels[:last_nonempty]

        # Add the new labels, keep empty lines where the user has not specified anything yet
        if len(dst_labels) < len(src_labels):
            empty = len(src_labels) - len(dst_labels) - len(new_items)
            dst_labels.extend([""] * empty)
            dst_labels.extend(new_items)

        dpg.set_value(f"{tag}_dest_ids", "\n".join(dst_labels))

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

    def show_message(
        msg: str = None, color: tuple[int, int, int, int] = style.red
    ) -> None:
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
        dpg.hide_item(f"{tag}_button_save")
        dpg.hide_item(f"{tag}_button_repack")

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

        # Resolve the user inputs to specific events
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

        show_message()
        copy_wwise_events(src_bnk, dst_bnk, event_map)
        show_message("Yay!", color=style.blue)

        dpg.show_item(f"{tag}_button_save")
        dpg.show_item(f"{tag}_button_repack")

    def on_save() -> None:
        dst_bnk.save()

    def on_repack() -> None:
        try:
            bnk2json = get_config().locate_bnk2json()
        except Exception:
            show_message("bnk2json is required for repacking")

        try:
            repack_soundbank(bnk2json, dst_bnk.bnk_dir)
        except Exception:
            show_message("bnk2json failed, check logs!")

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

        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Select IDs...",
                callback=select_nodes,
            )
            dpg.add_button(
                label="Swap Banks",
                callback=swap_banks,
            )
            dpg.add_button(
                label="Swap IDs",
                callback=swap_ids,
            )

        add_paragraphs("""\
            - Transfer sound structures between soundbanks
            - Specify by full name (Play_x123456789), hash (#102591249), or wwise name (x123456789)
            - Wwise names will be resolved to Play_ and Stop_ events
            - You cannot pair a name/hash with a wwise name
""",
        color=style.light_blue
        )

        dpg.add_spacer(height=3)
        dpg.add_separator()
        dpg.add_text(show=False, tag=f"{tag}_notification", color=style.red)

        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Scotty, beam them!", callback=on_okay, tag=f"{tag}_button_okay"
            )
            dpg.add_button(
                label="Save",
                callback=on_save,
                show=False,
                tag=f"{tag}_button_save",
            )
            dpg.add_button(
                label="Repack",
                callback=on_repack,
                show=False,
                tag=f"{tag}_button_repack",
            )

    return tag
