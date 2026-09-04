from typing import Any
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.types import Event
from yonder.transfer import copy_wwise_events
from yonder.hash import calc_hash
from yonder.util import repack_soundbank, logger, unpack_soundbank
from yonder.enums import Game, ActionType
from yonder.game import get_game_objects
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.widgets import (
    DpgItem,
    add_generic_widget,
    add_paragraphs,
    loading_indicator,
    yay,
)
from yonder.gui.helpers import shorten_path, dpg_section
from yonder.gui.config import get_config
from .select_nodes_dialog import select_nodes_dialog


class mass_transfer_dialog(DpgItem):
    def __init__(
        self,
        src_bnk: Soundbank = None,
        dst_bnk: Soundbank = None,
        *,
        title: str = "Transfer Sounds",
        tag: str = None,
    ) -> str:
        super().__init__(tag)

        self._src_bnk: Soundbank = src_bnk
        self._dst_bnk: Soundbank = dst_bnk

        self._build(title)

    def _on_source_bnk_selected(self, sender: str, path: Path, user_data: Any) -> None:
        with loading_indicator(µ("Loading")):
            if path.suffix == ".bnk":
                bnk2json = get_config().locate_bnk2json()
                path = unpack_soundbank(bnk2json, path)

            self._src_bnk = Soundbank.load(path)

    def _on_dest_bnk_selected(self, sender: str, path: Path, user_data: Any) -> None:
        with loading_indicator(µ("Loading")):
            if path.suffix == ".bnk":
                bnk2json = get_config().locate_bnk2json()
                path = unpack_soundbank(bnk2json, path)

            self._dst_bnk = Soundbank.load(path)

    def _select_nodes(self) -> None:
        if not self._src_bnk:
            self.show_message("Select source bank first")
            return

        self.show_message()
        select_nodes_dialog(
            lambda s: self._src_bnk.query(s, node_type=Event),
            self._on_nodes_selected,
            get_node_label=lambda n: n.get_name(),
            multiple=True,
            return_labels=True,
        )

    def _swap_banks(self) -> None:
        if not self._src_bnk and not self._dst_bnk:
            return

        self._src_bnk, self._dst_bnk = self._dst_bnk, self._src_bnk

        dpg.set_value(
            self._t("source_bnk"),
            shorten_path(self._src_bnk.json_path) if self._src_bnk else "",
        )
        dpg.set_value(
            self._t("dest_bnk"),
            shorten_path(self._dst_bnk.json_path) if self._dst_bnk else "",
        )

    def _swap_ids(self) -> None:
        src_labels = dpg.get_value(self._t("source_ids"))
        dst_labels = dpg.get_value(self._t("dest_ids"))
        dpg.set_value(self._t("source_ids"), dst_labels)
        dpg.set_value(self._t("dest_ids"), src_labels)

    def _collect_events(self) -> None:
        src_labels: list[str] = dpg.get_value(self._t("source_ids")).splitlines()
        dst_labels: list[str] = dpg.get_value(self._t("dest_ids")).splitlines()

        src_ids = []
        for line in src_labels:
            if not line.startswith(("Play_", "Stop_", "#")):
                line = "Play_" + line

            src_ids.append(self._line_to_hash(line))

        num = max(len(src_labels), len(dst_labels))
        src_labels += [""] * (num - len(src_labels))
        dst_labels += [""] * (num - len(dst_labels))

        for nid in src_ids:
            obj = self._src_bnk.get(nid)
            target_id = None

            if isinstance(obj, Event):
                for action in obj.get_action_nodes(self._src_bnk):
                    if action.action_type_enum in (
                        ActionType.Play,
                        ActionType.StopEO,
                        ActionType.StopE,
                    ):
                        target_id = action.external_id
                        break
            else:
                target_id = obj.id

            if target_id:
                for evt in self._src_bnk.find_events_for(target_id):
                    play_actions = evt.get_action_nodes(self._src_bnk, ActionType.Play)

                    if play_actions:
                        for pa in play_actions:
                            if pa.external_id == target_id:
                                # Explicitly plays our target_id, should be included
                                break
                        else:
                            if evt.has_action_type(
                                self._src_bnk, ActionType.StopEO, ActionType.StopE
                            ):
                                # Has a play action targeting a different node, don't include it
                                continue

                    if evt.id not in src_ids:
                        name = evt.get_name()
                        src_labels.append(name)
                        dst_labels.append(name)

        dpg.set_value(self._t("source_ids"), "\n".join(src_labels))
        dpg.set_value(self._t("dest_ids"), "\n".join(dst_labels))

    def _get_event_map(self, skip_invalid: bool) -> dict[str, str]:
        event_map = {}
        src_ids = self._prune_ids(dpg.get_value(self._t("source_ids")).splitlines())
        dst_ids = self._prune_ids(dpg.get_value(self._t("dest_ids")).splitlines())

        if len(src_ids) != len(dst_ids):
            if skip_invalid:
                num = min(len(src_ids), len(dst_ids))
                src_ids = src_ids[:num]
                dst_ids = dst_ids[:num]
            else:
                raise ValueError(µ("Source and destination IDs not balanced"))

        if not src_ids:
            return {}

        if not skip_invalid and not self._src_bnk:
            raise ValueError(µ("no source bank selected"))

        skip = set()

        for idx, line in enumerate(src_ids):
            src_play_id = self._line_to_hash(line)
            if src_play_id not in self._src_bnk:
                if skip_invalid:
                    skip.add(idx)
                else:
                    raise ValueError(
                        µ("{name} not found in source bank").format(name=line)
                    )

        if not skip_invalid and not self._dst_bnk:
            raise ValueError(µ("no destination bank selected"))

        for idx, line in enumerate(dst_ids):
            if line.startswith("#"):
                if skip_invalid:
                    skip.add(idx)
                else:
                    raise ValueError(µ("Destination IDs cannot be hashes"))

            dst_play_id = self._line_to_hash(line)
            if dst_play_id in self._dst_bnk:
                if skip_invalid:
                    skip.add(idx)
                else:
                    raise ValueError(
                        µ("{name} already exists in destination bank").format(name=line)
                    )

        for idx, (sid, did) in enumerate(zip(src_ids, dst_ids)):
            if idx in skip:
                continue

            src_explicit = sid.startswith(("Play_", "Stop_", "#"))
            dst_explicit = did.startswith(("Play_", "Stop_"))
            if src_explicit != dst_explicit:
                if not skip_invalid:
                    raise ValueError(
                        µ("Cannot pair explicit with implicit event names")
                    )

            if src_explicit:
                event_map[self._line_to_hash(sid)] = did
            else:
                play_evt = f"Play_{sid}"
                if play_evt in self._src_bnk:
                    event_map[play_evt] = f"Play_{did}"

                stop_evt = f"Stop_{sid}"
                if stop_evt in self._src_bnk:
                    event_map[stop_evt] = f"Stop_{did}"

        return event_map

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

        # Resolve the user inputs to specific events
        try:
            event_map = self._get_event_map(False)
        except ValueError as e:
            self.show_message(str(e))
            return

        if not event_map:
            self.show_message(µ("No events to transfer", "msg"))
            return

        self.show_message()
        with loading_indicator(µ("Transferring")):
            known_objects = set()

            # Skip any AMX (and busses) known to already exist in that game
            if dpg.get_value(self._t("skip_known_objects")):
                game = Game[dpg.get_value(self._t("game"))]

                if dpg.get_value(self._t("skip_main_bank_objects")):
                    for nid, amx in get_game_objects(
                        game
                    ).amx_summary.actormixers.items():
                        if amx.bank in ("init", "cs_main", "cs_smain", "vcmain"):
                            known_objects.add(nid)
                else:
                    known_objects = set(
                        get_game_objects(game).amx_summary.actormixers.keys()
                    )

            copy_wwise_events(
                self._src_bnk, self._dst_bnk, event_map, known_objects=known_objects
            )

        logger.info(f"Transferred {len(event_map)} sounds to {self._dst_bnk.name}")
        dpg.show_item(self._t("button_save"))
        dpg.show_item(self._t("button_repack"))
        yay()

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
                default=self._src_bnk.json_path if self._src_bnk else None,
                filetypes={
                    µ("Soundbanks (.bnk, .json)", "filetypes"): ["*.bnk", "*.json"]
                },
                tag=self._t("source_bnk"),
            )
            add_generic_widget(
                Path,
                µ("Destination Soundbank"),
                self._on_dest_bnk_selected,
                default=self._dst_bnk.json_path if self._dst_bnk else None,
                filetypes={
                    µ("Soundbanks (.bnk, .json)", "filetypes"): ["*.bnk", "*.json"]
                },
                tag=self._t("dest_bnk"),
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
                        tag=self._t("source_ids"),
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
                        tag=self._t("dest_ids"),
                    )

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Select IDs..."),
                    callback=self._select_nodes,
                    tag=self._t("button_select_ids"),
                )
                dpg.add_button(
                    label=µ("Swap Banks"),
                    callback=self._swap_banks,
                    tag=self._t("button_swap_banks"),
                )
                dpg.add_button(
                    label=µ("Swap IDs"),
                    callback=self._swap_ids,
                    tag=self._t("button_swap_ids"),
                )
                dpg.add_button(
                    label=µ("Collect Events"),
                    callback=self._collect_events,
                    tag=self._t("collect_events"),
                )
                with dpg.tooltip(dpg.last_item()):
                    dpg.add_text(
                        µ(
                            "Pull in events with actions targeting the same structures as the ones you have selected above"
                        ),
                        wrap=440,
                    )

            with dpg.tree_node(label=µ("Advanced")):
                with dpg.group(horizontal=True):
                    dpg.add_checkbox(
                        default_value=True,
                        label=µ("Skip known playback objects for"),
                        tag=self._t("skip_known_objects"),
                    )
                    with dpg.tooltip(dpg.last_item()):
                        dpg.add_text(
                            µ(
                                "ActorMixers and busses are stored in cs_main/init. Enabling this will not transfer objects already known to exist in the specified game."
                            ),
                            wrap=440,
                        )

                    dpg.add_combo(
                        [g.name for g in Game],
                        default_value=Game.EldenRing.name,
                        width=110,
                        tag=self._t("game"),
                    )

                dpg.add_checkbox(
                    label=µ("Skip objects from main banks only"),
                    default_value=True,
                    tag=µ(self._t("skip_main_bank_objects")),
                )
                with dpg.tooltip(dpg.last_item()):
                    dpg.add_text(
                        µ(
                            "When skipping known objects, only skip objects from init, cs_main, cs_smain, and vcmain."
                        ),
                        wrap=440,
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
                    "tips",
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
                    tag=self._t("button_okay"),
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
