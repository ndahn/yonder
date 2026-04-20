from typing import Any
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.types import Event
from yonder.transfer import copy_wwise_events
from yonder.hash import calc_hash
from yonder.util import repack_soundbank
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.widgets import DpgItem, add_generic_widget, add_paragraphs
from yonder.gui.helpers import shorten_path, dpg_section
from yonder.gui.config import get_config
from .select_nodes_dialog import select_nodes_of_type


class mass_transfer_dialog(DpgItem):
    def __init__(
        self,
        *,
        title: str = "Transfer Sounds",
        tag: str = None,
    ) -> str:
        super().__init__(tag)

        self._src_bnk: Soundbank = None
        self._dst_bnk: Soundbank = None

        self._build(title)

    def _on_source_bnk_selected(self, sender: str, path: Path, user_data: Any) -> None:
        self._src_bnk = Soundbank.from_file(path)

    def _on_dest_bnk_selected(self, sender: str, path: Path, user_data: Any) -> None:
        self._dst_bnk = Soundbank.from_file(path)

    def _select_nodes(self) -> None:
        if not self._src_bnk:
            self.show_message("Select source bank first")
            return

        self.show_message()
        select_nodes_of_type(
            self._src_bnk,
            Event,
            self._on_nodes_selected,
            get_node_label=lambda n: n.get_name(f"#{n.id}"),
            multiple=True,
            return_labels=True,
        )

    def _swap_banks(self) -> None:
        if not self._src_bnk:
            self.show_message(µ("No source bank selected", "msg"))
            return

        if not self._dst_bnk:
            self.show_message(µ("No destination bank selected", "msg"))
            return

        self.show_message()
        self._src_bnk, self._dst_bnk = self._dst_bnk, self._src_bnk

        dpg.set_value(self._t("source_bnk"), shorten_path(self._src_bnk.json_path))
        dpg.set_value(self._t("dest_bnk"), shorten_path(self._dst_bnk.json_path))

    def _swap_ids(self) -> None:
        src_labels = dpg.get_value(self._t("source_ids"))
        dst_labels = dpg.get_value(self._t("dest_ids"))
        dpg.set_value(self._t("source_ids"), dst_labels)
        dpg.set_value(self._t("dest_ids"), src_labels)

    def _on_nodes_selected(
        self, sender: str, selected: list[str], user_data: Any
    ) -> None:
        src_labels: list[str] = dpg.get_value(self._t("source_ids")).splitlines()
        src_ids = set()
        new_items = []

        for line in src_labels:
            h = self._line_to_hash(line)
            if h is not None:
                src_ids.add(h)

        for label in selected:
            h = self._line_to_hash(label)
            if h not in src_ids:
                new_items.append(label)

        # Update the source ids text box
        src_labels.extend(new_items)
        dpg.set_value(self._t("source_ids"), "\n".join(src_labels))

        # Update the dest ids text box
        dst_labels: list[str] = dpg.get_value(self._t("dest_ids")).splitlines()

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

        dpg.set_value(self._t("dest_ids"), "\n".join(dst_labels))

    @staticmethod
    def _line_to_hash(line: str) -> int:
        line: str = line.strip()
        if not line:
            return None

        if line.startswith("#"):
            return int(line[1:])

        if not line.startswith(("Play_", "Stop_")):
            line = "Play_" + line
        return calc_hash(line)

    @staticmethod
    def _prune_ids(ids: list[str]) -> list[str]:
        # NOTE it's important to maintain the order
        pruned = []
        seen = set()

        for line in ids:
            h = mass_transfer_dialog._line_to_hash(line)
            if h is not None and h not in seen:
                seen.add(h)
                pruned.append(line)

        return pruned

    def show_message(self, msg: str = None, color: style.RGBA = style.red) -> None:
        if not msg:
            dpg.hide_item(self._t("notification"))
            return

        dpg.configure_item(
            self._t("notification"),
            default_value=msg,
            color=color,
            show=True,
        )

    def _on_okay(self) -> None:
        dpg.hide_item(self._t("button_save"))
        dpg.hide_item(self._t("button_repack"))

        if not self._src_bnk:
            self.show_message(µ("No source bank selected", "msg"))
            return

        if not self._dst_bnk:
            self.show_message(µ("No destination bank selected", "msg"))
            return

        src_ids = self._prune_ids(dpg.get_value(self._t("source_ids")).splitlines())
        dst_ids = self._prune_ids(dpg.get_value(self._t("dest_ids")).splitlines())

        if not src_ids:
            self.show_message(µ("No source IDs selected", "msg"))
            return

        if len(src_ids) != len(dst_ids):
            self.show_message(
                µ(
                    "Source and destination IDs not balanced",
                    "msg",
                )
            )
            return

        for line in src_ids:
            src_play_id = self._line_to_hash(line)
            if src_play_id not in self._src_bnk:
                self.show_message(
                    µ("{name} not found in source bank", "msg").format(name=line)
                )
                return

        for line in dst_ids:
            if line.startswith("#"):
                self.show_message(
                    µ(
                        "Destination IDs cannot be hashes",
                        "msg",
                    )
                )
                return

            dst_play_id = self._line_to_hash(line)
            if dst_play_id in self._dst_bnk:
                self.show_message(
                    µ("{name} already exists in destination bank", "msg").format(
                        name=line
                    )
                )
                return

        # Resolve the user inputs to specific events
        event_map = {}
        for sid, did in zip(src_ids, dst_ids):
            src_explicit = sid.startswith(("Play_", "Stop_", "#"))
            dst_explicit = did.startswith(("Play_", "Stop_"))
            if src_explicit != dst_explicit:
                self.show_message(
                    µ(
                        "Cannot pair explicit with implicit event names",
                        "msg",
                    )
                )
                return

            if src_explicit:
                event_map[self._line_to_hash(sid)] = did
            else:
                play_evt = f"Play_{sid}"
                if play_evt in self._src_bnk:
                    event_map[play_evt] = f"Play_{did}"

                stop_evt = f"Stop_{sid}"
                if stop_evt in self._src_bnk:
                    event_map[stop_evt] = f"Stop_{did}"

        self.show_message()
        copy_wwise_events(self._src_bnk, self._dst_bnk, event_map)
        self.show_message("Yay!", color=style.blue)

        dpg.show_item(self._t("button_save"))
        dpg.show_item(self._t("button_repack"))

    def _on_save(self) -> None:
        self._dst_bnk.save()

    def _on_repack(self) -> None:
        try:
            bnk2json = get_config().locate_bnk2json()
        except Exception:
            self.show_message(
                µ(
                    "bnk2json is required for repacking",
                    "msg",
                )
            )
        else:
            repack_soundbank(bnk2json, self._dst_bnk.bnk_dir)

    def _build(self, title: str):
        with dpg.window(
            label=title,
            width=400,
            height=400,
            autosize=True,
            no_saved_settings=True,
            tag=self.tag,
            on_close=lambda: dpg.delete_item(window),
        ) as window:
            add_generic_widget(
                Path,
                µ("Source Soundbank"),
                self._on_source_bnk_selected,
                filetypes={
                    µ("Soundbanks (.bnk, .json)", "filetypes"): ["*.bnk", "*.json"]
                },
                tag=self._t("mass_transfer/source_bnk"),
            )
            add_generic_widget(
                Path,
                µ("Destination Soundbank"),
                self._on_dest_bnk_selected,
                filetypes={
                    µ("Soundbanks (.bnk, .json)", "filetypes"): ["*.bnk", "*.json"]
                },
                tag=self._t("mass_transfer/dest_bnk"),
            )

            with dpg.group(horizontal=True):
                with dpg.group():
                    dpg_section(
                        label=µ("Source Wwise IDs"),
                        color=style.muted_orange,
                        spacer=0,
                    )
                    dpg.add_input_text(
                        multiline=True,
                        height=300,
                        tag=self._t("mass_transfer/source_ids"),
                    )
                with dpg.group():
                    dpg_section(
                        label=µ("Destination Wwise IDs"),
                        color=style.muted_teal,
                        spacer=0,
                    )
                    dpg.add_input_text(
                        multiline=True,
                        height=300,
                        tag=self._t("mass_transfer/dest_ids"),
                    )

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Select IDs..."),
                    callback=self._select_nodes,
                    tag=self._t("mass_transfer/button_select_ids"),
                )
                dpg.add_button(
                    label=µ("Swap Banks"),
                    callback=self._swap_banks,
                    tag=self._t("mass_transfer/button_swap_banks"),
                )
                dpg.add_button(
                    label=µ("Swap IDs"),
                    callback=self._swap_ids,
                    tag=self._t("mass_transfer/button_swap_ids"),
                )

            dpg.add_separator()
            add_paragraphs(
                µ(
                    """\
                    - Transfer sound structures between soundbanks
                    - Specify by full name (Play_x123456789), hash (#102591249), or wwise name (x123456789)
                    - Wwise names will be resolved to Play_ and Stop_ events
                    - You cannot pair a name/hash with a wwise name
                    """,
                    "mass_transfer/tips",
                ),
                color=style.light_blue,
            )

            dpg.add_separator()
            dpg.add_spacer(height=2)
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Scotty, beam them!", "button"),
                    callback=self._on_okay,
                    tag=self._t("mass_transfer/button_okay"),
                )
                dpg.add_button(
                    label=µ("Save", "button"),
                    callback=self._on_save,
                    show=False,
                    tag=self._t("button_save"),
                )
                dpg.add_button(
                    label=µ("Repack", "button"),
                    callback=self._on_repack,
                    show=False,
                    tag=self._t("button_repack"),
                )
