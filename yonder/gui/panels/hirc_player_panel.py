from typing import Any, Callable
import time
from bisect import bisect
from threading import Thread
import socket
import json
from dearpygui import dearpygui as dpg

from yonder import lookup_name, calc_hash
from yonder.gui import style
from yonder.gui.icons import Icons
from yonder.gui.localization import µ
from yonder.gui.widgets.dpg_item import DpgItem
from yonder.gui.widgets.hirc_player_widget import add_hirc_player


class add_hirc_player_widget(DpgItem):
    def __init__(
        self,
        hirc_player: add_hirc_player,
        *,
        tag: str = None,
    ) -> None:
        super().__init__(tag)

        self._hirc_player: add_hirc_player = hirc_player
        self._is_synchronizing = False
        self._contiunous_sync = False
        self._rtpcs: dict[int, float] = {}
        self._states: dict[int, int] = {}
        self._rtpc_rows: dict[str, tuple[int, int]] = {}
        self._state_rows: dict[str, tuple[int, int]] = {}

        self._build()

    def _build(self) -> None:
        with dpg.child_window(autosize_x=True, autosize_y=True, tag=self.tag):
            dpg.add_separator(label=µ("Info"))
            dpg.add_text(tag=self._t("player_info"))

            # Player settings
            dpg.add_spacer(height=5)
            dpg.add_separator(label=µ("Settings"))

            dpg.add_checkbox(
                label=µ("Play from hierarchy head"),
                default_value=True,
                tag=self._t("player_play_hierarchy_head"),
            )
            dpg.add_checkbox(
                label=µ("Include AMX hierarchy"),
                default_value=True,
                tag=self._t("player_include_amx"),
            )
            dpg.add_checkbox(
                label=µ("Show relevant game syncs only"),
                default_value=True,
                tag=self._t("player_active_game_syncs_only"),
            )

            # Game syncs
            dpg.add_spacer(height=5)
            dpg.add_separator(label=µ("Game Syncs"))

            with dpg.child_window(autosize_x=True, auto_resize_y=True):
                dpg.add_input_int(
                    label=µ("Port"),
                    default_value=27172,
                    width=200,
                    tag=self._t("player_sync_port"),
                )

                with dpg.group(horizontal=True):
                    dpg.add_text(µ("Synchronize"))
                    with dpg.tooltip(dpg.last_item()):
                        dpg.add_text(µ("Read game syncs from game (requires yonder_live_states.dll)"))

                    dpg.add_image_button(
                        Icons.game_sync_once,
                        width=18,
                        height=18,
                        callback=self._start_game_sync,
                        tag=self._t("player_sync_once"),
                        user_data=False,
                    )
                    dpg.add_image_button(
                        Icons.game_sync_auto,
                        width=18,
                        height=18,
                        callback=self._start_game_sync,
                        tag=self._t("player_sync_auto"),
                        user_data=True,
                    )
                    dpg.add_loading_indicator(
                        radius=0.8,
                        style=1,
                        color=style.red,
                        show=False,
                        tag=self._t("player_sync_progress"),
                    )

            dpg.add_spacer(height=3)

            def make_gamesync_table(base_tag: str) -> None:
                with dpg.group(tag=self._t(base_tag)):
                    dpg.add_input_text(
                        callback=lambda a, s, u: dpg.set_value(self._t(f"{base_tag}_table"), s),
                        tag=self._t(f"{base_tag}_filter"),
                    )
                    with dpg.table(
                        header_row=False,
                        tag=self._t(f"{base_tag}_table")
                    ):
                        dpg.add_table_column(width_stretch=True)
                        dpg.add_table_column(width_stretch=True)

            with dpg.tree_node(label=µ("RTPCs")):
                make_gamesync_table("player_rtpcs")

            with dpg.tree_node(label=µ("Switches")):
                make_gamesync_table("player_switches")

            with dpg.tree_node(label=µ("States")):
                make_gamesync_table("player_states")

        self._update_player_tab()

    def _update_player_tab(self) -> None:
        is_live = self._is_synchronizing

        # TODO info text

        if self._rtpcs:
            dpg.show_item(self._t("player_rtpcs"))
            table = self._t("player_rtpcs_table")
            rtpcs = {lookup_name(r, f"#{r}"): v for r, v in self._rtpcs.items()}

            for r in sorted(rtpcs):
                value = rtpcs[r]

                if r in self._rtpc_rows:
                    # Row exists, just update the value
                    _, row_value = self._rtpc_rows[r]
                    dpg.set_value(dpg.get_item_children(row_value, slot=1)[1], value)
                else:
                    # Row does not exist yet, check where to insert it
                    keys = list(self._rtpc_rows)
                    idx = bisect(keys, r)
                    before = 0

                    if keys and idx < len(keys):
                        # Should be inserted before an existing element
                        nxt = keys[idx + 1]
                        before, _ = self._rtpc_rows[nxt]

                    with dpg.table_row(filter_key=r, before=before, parent=table) as row:
                        dpg.add_text(r)
                        row_value = dpg.add_drag_float(
                            default_value=value,
                            enabled=not is_live,
                            callback=self._on_rtpc_changed,
                            user_data=r,
                        )

                    self._rtpc_rows[r] = (row, row_value)
        else:
            dpg.hide_item(self._t("player_rtpcs"))

        if self._states:
            dpg.show_item(self._t("player_states"))
            dpg.show_item(self._t("player_switches"))
        else:
            dpg.hide_item(self._t("player_states"))
            dpg.hide_item(self._t("player_switches"))

    def _set_sync_state(self, synchronizing: bool) -> None:
        self._is_synchronizing = synchronizing
        self._contiunous_sync = False

        if synchronizing:
            dpg.show_item(self._t("player_sync_progress"))
            
            if self._contiunous_sync:
                dpg.configure_item(self._t("player_sync_auto"), tint_color=style.red)
            else:
                dpg.configure_item(self._t("player_sync_once"), tint_color=style.red)

            # TODO disable all row edits
        else:
            dpg.configure_item(self._t("player_sync_once"), tint_color=style.white)
            dpg.configure_item(self._t("player_sync_auto"), tint_color=style.white)
            dpg.hide_item(self._t("player_sync_progress"))
            # TODO enable all row edits

    def _on_rtpc_changed(self, sender: str, value: float, rtpc: str) -> None:
        h = calc_hash(rtpc.removeprefix("#"))
        self._rtpcs[h] = value
        self._hirc_player.update_context(self._states, self._rtpcs)

    def _on_state_changed(self, sender: str, value: float, state: str) -> None:
        h = calc_hash(state.removeprefix("#"))
        self._states[h] = value
        self._hirc_player.update_context(self._states, self._rtpcs)

    def _start_game_sync(self, sender: str, app_data: Any, continuous: bool) -> None:
        if self._is_synchronizing:
            return
        
        self._contiunous_sync = continuous
        self._set_sync_state(True)
        Thread(target=self._sync, daemon=True)

    def _sync(self) -> None:
        port = dpg.get_value(self._t("player_sync_port"))
        last_update = 0

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1.0)
            sock.bind(("localhost", port))

            while True:
                try:
                    # Wait for submission from dll
                    raw, _ = sock.recvfrom(1024)
                    data = json.loads(raw.decode("utf-8").strip())
                    self._rtpcs.update(data.get("rtpcs", {}))
                    self._states.update(data.get("states", {}))

                    now = time.time()
                    if (time - last_update) > 0.1:
                        self._update_player_tab()

                    last_update = now
                    if not self._contiunous_sync:
                        break
                except TimeoutError:
                    break
        finally:
            if sock:
                sock.close()

            self._set_sync_state(False)
            self._update_player_tab()
