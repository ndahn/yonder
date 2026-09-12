from typing import Any
import time
from bisect import bisect
from threading import Thread
import socket
import json
from dearpygui import dearpygui as dpg

from yonder import lookup_name, calc_hash, HIRCNode
from yonder.types.mixins import StateMixin, RtpcMixin, DecisionTreeMixin
from yonder.game import get_selected_game
from yonder.gui import style
from yonder.gui.icons import Icons
from yonder.gui.localization import µ
from yonder.gui.widgets.dpg_item import DpgItem
from yonder.gui.widgets.hirc_player_widget import add_hirc_player
from yonder.gui.widgets.state_value_input import add_state_value_input


class add_hirc_player_panel(DpgItem):
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
        self._widgets_updating = False
        self._states: dict[int, int] = {}
        self._rtpcs: dict[int, float] = {}
        self._rtpc_rows: dict[str, tuple[int, int]] = {}
        self._state_rows: dict[str, tuple[int, add_state_value_input]] = {}

        self._build()
        hirc_player.set_callback(self._trigger_widgets_update)

    def _build(self) -> None:
        with dpg.child_window(autosize_x=True, autosize_y=True, tag=self.tag):
            # Player info
            dpg.add_separator(label=µ("Info"))
            dpg.add_text(tag=self._t("player_info"))

            # Player settings
            dpg.add_spacer(height=5)
            dpg.add_separator(label=µ("Settings"))

            with dpg.group():
                dpg.add_checkbox(
                    label=µ("Play full hierarchy"),
                    default_value=True,
                    tag=self._t("player_full_hierarchy"),
                )
                dpg.add_checkbox(
                    label=µ("Include AMX hierarchy"),
                    default_value=True,
                    tag=self._t("player_include_amx"),
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

                dpg.add_spacer(height=2)

                with dpg.group(horizontal=True):
                    dpg.add_text(µ("Synchronize"))
                    with dpg.tooltip(dpg.last_item()):
                        dpg.add_text(
                            µ(
                                "Read game syncs from game (requires yonder_live_states.dll)"
                            )
                        )

                    dpg.add_image_button(
                        Icons.game_sync_once,
                        width=18,
                        height=18,
                        callback=self._start_stop_game_sync,
                        tag=self._t("sync_once"),
                        user_data=False,
                    )
                    dpg.add_image_button(
                        Icons.game_sync_auto,
                        width=18,
                        height=18,
                        callback=self._start_stop_game_sync,
                        tag=self._t("sync_auto"),
                        user_data=True,
                    )
                    dpg.add_image_button(
                        Icons.trash,
                        width=18,
                        height=18,
                        callback=self.regenerate,
                        tag=self._t("sync_clear"),
                    )
                    dpg.add_loading_indicator(
                        radius=1,
                        style=2,
                        color=style.red,
                        show=False,
                        tag=self._t("sync_progress"),
                    )
                    dpg.add_text(
                        "",
                        color=style.light_grey,
                        show=False,
                        tag=self._t("sync_status"),
                    )

            dpg.add_spacer(height=3)

            def make_gamesync_table(base_tag: str) -> None:
                with dpg.group(tag=self._t(base_tag)):
                    dpg.add_input_text(
                        hint=µ("Filter"),
                        callback=lambda a, s, u: dpg.set_value(
                            self._t(f"{base_tag}_table"), s
                        ),
                        tag=self._t(f"{base_tag}_filter"),
                    )
                    with dpg.table(
                        header_row=False,
                        borders_outerH=True,
                        borders_outerV=True,
                        tag=self._t(f"{base_tag}_table"),
                    ):
                        dpg.add_table_column(width_stretch=True)

            with dpg.tree_node(
                label=µ("RTPCs"), default_open=True, tag=self._t("tree_rtpcs")
            ):
                make_gamesync_table("sync_rtpcs")

            with dpg.tree_node(
                label=µ("States"), default_open=True, tag=self._t("tree_states")
            ):
                make_gamesync_table("sync_states")

        self.regenerate()

    def regenerate(self) -> None:
        self._set_sync_state(False)
        self._states.clear()
        self._rtpcs.clear()

        # Clean up any of our custom dpg widgets
        # for _, row_value in self._rtpc_rows.values():
        #     ...
        for _, row_value in self._state_rows.values():
            row_value.destroy()

        self._rtpc_rows.clear()
        self._state_rows.clear()

        dpg.delete_item(self._t("sync_rtpcs_table"), slot=1, children_only=True)
        dpg.delete_item(self._t("sync_states_table"), slot=1, children_only=True)
        dpg.set_value(self._t("sync_rtpcs_filter"), "")
        dpg.set_value(self._t("sync_states_filter"), "")
        dpg.hide_item(self._t("sync_status"))

        self._trigger_widgets_update()

    def _collect_control_states(
        self, active_only: bool = True
    ) -> tuple[dict[int, set[int]], list[int]]:
        entrypoint = self._hirc_player.entrypoint
        if not entrypoint:
            return ({}, [])

        # Make sure the playback structure is initialized so we have something to collect
        self._hirc_player.player.init_pyo()

        states: dict[int, set[int]] = {}
        rtpcs: list[int] = []
        todo: list[HIRCNode] = [self._hirc_player.entrypoint]
        bnk = self._hirc_player.bank

        while todo:
            node = todo.pop()

            # Only pyo-initialized nodes will be added to the todo-list
            if isinstance(node, DecisionTreeMixin):
                for group, values in node.get_used_state_values().items():
                    group_states = states.setdefault(group, set())
                    group_states.update(values)

            if isinstance(node, StateMixin):
                for group in node.states.state_group_chunks:
                    group_states = states.setdefault(group.state_group_id, set())
                    group_states.update([s.state_id for s in group.states])

            if isinstance(node, RtpcMixin):
                for rtpc in node.rtpcs:
                    rtpcs.append(rtpc.id)

            if bnk:
                for _, ref in node.get_references():
                    child = bnk.get(ref)
                    if child and (not active_only or child.is_pyo_initialized()):
                        todo.append(child)

        return (states, rtpcs)

    def _trigger_widgets_update(self) -> None:
        if self._widgets_updating:
            return

        def run():
            try:
                self._update_player_tab()
            finally:
                self._widgets_updating = False

        self._widgets_updating = True
        Thread(target=run, daemon=True).start()

    def _update_player_tab(self) -> None:
        is_live = self._is_synchronizing

        # TODO info text, active voices, etc
        dpg.set_value(
            self._t("player_info"), f"voices: {len(self._hirc_player.voices)}"
        )

        # Game syncs that are relevant for playback right now
        # Don't collect all syncs used *somewhere* as this can take multiple seconds
        # for e.g. the main music switch container in cs_smain
        active_states, active_rtpcs = self._collect_control_states(True)

        if active_rtpcs:
            dpg.show_item(self._t("sync_rtpcs"))
            table = self._t("sync_rtpcs_table")
            rtpcs = {
                lookup_name(r, f"#{r}"): self._rtpcs.get(r, 0.0) for r in active_rtpcs
            }

            for param in sorted(rtpcs):
                value = rtpcs[param]

                if param in self._rtpc_rows:
                    # Row exists, just update the value
                    _, row_value = self._rtpc_rows[param]
                    dpg.configure_item(row_value, default_value=value)
                else:
                    # Row does not exist yet, check where to insert it
                    keys = list(self._rtpc_rows)
                    idx = bisect(keys, param)
                    before = 0

                    if keys and idx < len(keys):
                        # Should be inserted before an existing element
                        nxt = keys[idx + 1]
                        before, _ = self._rtpc_rows[nxt]

                    with dpg.table_row(
                        filter_key=param, before=before, parent=table
                    ) as row:
                        row_value = dpg.add_drag_float(
                            label=param,
                            default_value=value,
                            enabled=not is_live,
                            callback=self._on_rtpc_changed,
                            user_data=param,
                        )

                    self._rtpc_rows[param] = (row, row_value)
        else:
            dpg.hide_item(self._t("sync_rtpcs"))

        if active_states:
            dpg.show_item(self._t("sync_states"))
            table = self._t("sync_states_table")

            states = {}
            for group in active_states:
                group_name = lookup_name(group, f"#{group}")
                state_value = self._states.get(group)
                state_name = (
                    lookup_name(state_value, f"#{state_value}") if state_value else "-"
                )
                states[group_name] = state_name

            for group in sorted(states):
                state_value = states[group]

                if group in self._state_rows:
                    _, row_value = self._state_rows[group]
                    row_value.value = state_value
                else:
                    keys = list(self._state_rows)
                    idx = bisect(keys, group)
                    before = 0

                    if keys and idx < len(keys):
                        nxt = keys[idx + 1]
                        before, _ = self._state_rows[nxt]

                    with dpg.table_row(
                        filter_key=group, before=before, parent=table
                    ) as row:
                        known_states = get_selected_game().game_states.get(group, [])
                        row_value = add_state_value_input(
                            group,
                            known_states,
                            self._on_state_changed,
                            default_value=state_value,
                            user_data=group,
                        )

                    self._state_rows[group] = (row, row_value)
        else:
            dpg.hide_item(self._t("sync_states"))

    def _set_sync_state(self, synchronizing: bool) -> None:
        self._is_synchronizing = synchronizing

        if synchronizing:
            dpg.hide_item(self._t("sync_status"))
            dpg.show_item(self._t("sync_progress"))

            if self._contiunous_sync:
                dpg.configure_item(self._t("sync_auto"), tint_color=style.red)
            else:
                dpg.configure_item(self._t("sync_once"), tint_color=style.red)

            # prevent row edits
            for _, row_value in self._rtpc_rows.values():
                dpg.disable_item(row_value)

            for _, row_value in self._state_rows.values():
                row_value.set_enabled(False)
        else:
            dpg.hide_item(self._t("sync_progress"))

            self._contiunous_sync = False
            dpg.configure_item(self._t("sync_once"), tint_color=style.white)
            dpg.configure_item(self._t("sync_auto"), tint_color=style.white)

            # allow row edits once more
            for _, row_value in self._rtpc_rows.values():
                dpg.enable_item(row_value)

            for _, row_value in self._state_rows.values():
                row_value.set_enabled(True)

    def _on_rtpc_changed(self, sender: str, value: float, rtpc: str) -> None:
        h = calc_hash(rtpc)
        self._rtpcs[h] = value
        self._hirc_player.set_game_syncs(self._states, self._rtpcs)

    def _on_state_changed(self, sender: str, value: str, state: str) -> None:
        h = calc_hash(state)
        v = calc_hash(value)
        self._states[h] = v
        self._hirc_player.set_game_syncs(self._states, self._rtpcs)

    def _start_stop_game_sync(
        self, sender: str, app_data: Any, continuous: bool
    ) -> None:
        if self._is_synchronizing:
            # Let the current synchronization time out
            self._contiunous_sync = False
            return

        self._contiunous_sync = continuous
        self._set_sync_state(True)
        Thread(target=self._sync, daemon=True).start()

    def _sync(self) -> None:
        port = dpg.get_value(self._t("player_sync_port"))
        last_update = 0

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1.0)

            attempt = 0
            while True:
                try:
                    sock.bind(("localhost", port))
                    break
                except OSError:
                    if attempt < 3:
                        time.sleep(0.5)
                    else:
                        raise

            while True:
                try:
                    # Wait for submission from dll
                    raw, _ = sock.recvfrom(1024)
                    if not self._is_synchronizing:
                        break

                    data = json.loads(raw.decode("utf-8").strip())

                    # Update the player
                    self._states.update(data.get("states", {}))
                    self._rtpcs.update(data.get("rtpcs", {}))
                    self._hirc_player.set_game_syncs(self._states, self._rtpcs)

                    # Limit gui update rate
                    now = time.time()
                    if (time - last_update) > 0.05:
                        self._trigger_widgets_update()

                    last_update = now
                    if not self._contiunous_sync:
                        break
                except TimeoutError:
                    if not self._contiunous_sync:
                        # Don't show the message if we were already supposed to stop
                        if self._is_synchronizing:
                            dpg.configure_item(
                                self._t("sync_status"),
                                default_value="timeout",
                                show=True,
                            )

                        break
        finally:
            if sock:
                sock.close()

            self._set_sync_state(False)
            self._trigger_widgets_update()
