from typing import Any, Callable
from pathlib import Path
from copy import deepcopy
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.util import logger
from yonder.types import MusicSwitchContainer
from yonder.types.base_types import MusicTransitionRule
from yonder.enums import CurveInterpolation, SyncType
from yonder.hash import calc_hash
from yonder.convenience import create_boss_bgm, BossBgm, BgmTrack
from yonder.wem import wav2wem
from yonder.game import GameObjects
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.config import get_config
from yonder.gui.widgets import (
    DpgItem,
    add_select_node,
    add_paragraphs,
    add_player_table,
    add_properties_table,
    add_transition_matrix,
    loading_indicator,
    yay,
)
from yonder.gui.widgets.select_node import get_details_musicswitchcontainer
from .edit_state_path_dialog import edit_state_path_dialog


class create_boss_track_dialog(DpgItem):
    def __init__(
        self,
        bnk: Soundbank,
        on_boss_track_created: Callable[[str, list[HIRCNode]], None],
        *,
        title: str = "New Boss Bgm",
        tag: str = None,
    ) -> str:
        super().__init__(tag)

        self.bnk = bnk
        self.on_boss_track_created = on_boss_track_created
        self.msc: MusicSwitchContainer = None
        self.bgm_enemy_type_hash = calc_hash("BgmEnemyType")
        self.bgm_enemy_type_idx: int = -1
        self.current_state_path: list[str] = []
        self.bgm_tracks: list[BossBgm] = []
        self.phase_transitions: list[MusicTransitionRule] = [
            MusicTransitionRule().configure(
                src_transition_time=1500,
                src_fade_offset=1500,
                src_fade_curve=CurveInterpolation.Sine,
                dst_transition_time=500,
                dst_fade_offset=-500,
                dst_fade_curve=CurveInterpolation.Log1,
                dst_play_pre_entry=True,
            )
        ]

        self._build(title)

    # === Helpers =================================================

    @staticmethod
    def get_phase_label(phase: int) -> str:
        return f"Heatup {phase}" if phase > 0 else "Normal"

    def _get_music_switch_containers(self, filt: str) -> list[MusicSwitchContainer]:
        filt = f"type=MusicSwitchContainer arguments:*/group_id={self.bgm_enemy_type_hash} {filt}"
        return list(self.bnk.query(filt))

    def _edit_state_path(self) -> None:
        if not self.msc:
            self.show_message(µ("Select MusicSwitchContainer first", "msg"))
            return

        edit_state_path_dialog(
            self.bnk,
            self.msc.arguments,
            self._on_statepath_selected,
            state_path=self.current_state_path,
            hide_node_id=True,
        )

    def _regenerate_per_track_widgets(self) -> None:
        dpg.delete_item(self._t("per_track_settings"), children_only=True, slot=0)
        dpg.delete_item(self._t("per_track_settings"), children_only=True, slot=1)

        dpg.push_container_stack(self._t("per_track_settings"))

        dpg.add_table_column(width_fixed=True)
        for i, _ in enumerate(self.bgm_tracks):
            dpg.add_table_column(
                label=self.get_phase_label(i),
                angled_header=True,
                width_fixed=True,
            )

        with dpg.table_row():
            dpg.add_text(µ("Play intro"), tag=self._t("intro_enabled"))
            with dpg.tooltip(dpg.last_item()):
                dpg.add_text(µ("Play intro based on regular track's loop_start"))

            for i, bgm in enumerate(self.bgm_tracks):
                dpg.add_checkbox(
                    default_value=bgm.intro_length > 0,
                    callback=self._update_play_intro,
                    tag=self._t(f"play_intro:{i}"),
                    user_data=i,
                )

        dpg.pop_container_stack()

        # NOTE not using format to make sure the # survives for later
        targets = [µ("Track ") + f"#{i}" for i in range(len(self.bgm_tracks))]
        self.phase_transition_matrix.targets = targets
        self.phase_transition_matrix.regenerate()

    # === DPG callbacks =================================================

    def _on_music_switch_container_selected(
        self, sender: str, selected_msc: int | MusicSwitchContainer, user_data: Any
    ) -> None:
        if isinstance(selected_msc, int):
            selected_msc = self.bnk.get(selected_msc)

        for i, arg in enumerate(selected_msc.arguments):
            if arg.group_id == self.bgm_enemy_type_hash:
                self.bgm_enemy_type_idx = i
                break
        else:
            self.show_message(
                µ(
                    "MSC does not have a BgmEnemyType argument",
                    "msg",
                )
            )
            return

        self.msc = selected_msc
        self.current_state_path = ["*" for _ in self.msc.arguments]
        self.current_state_path[self.bgm_enemy_type_idx] = dpg.get_value(
            self._t("bgm_enemy_type")
        )
        self.show_message()

    def _on_bgmenemytype_changed(self, sender: str, value: str, user_data: Any) -> None:
        if not value or value == "*":
            self.show_message(µ("BgmEnemyType not set", "msg"))
            return

        if self.msc:
            self.current_state_path[self.bgm_enemy_type_idx] = value

        dpg.set_value(self._t("bgm_enemy_type"), value)
        self.show_message()

    def _on_statepath_selected(
        self, sender: str, state_path: list[str], user_data: Any
    ) -> None:
        self.current_state_path.clear()
        self.current_state_path.extend(state_path)
        dpg.set_value(self._t("bgm_enemy_type"), state_path[self.bgm_enemy_type_idx])
        self.show_message()

    def _on_track_added(self, sender: str, path: Path, user_data: Any) -> None:
        self.bgm_tracks.append(BossBgm(BgmTrack(path), 0.0))
        self._regenerate_per_track_widgets()

    def _on_track_removed(self, sender: str, idx: int, user_data: Any) -> None:
        self.bgm_tracks.pop(idx)
        self._regenerate_per_track_widgets()

    def _on_track_changed(
        self, sender: str, info: tuple[int, Path], user_data: Any
    ) -> None:
        idx, path = info
        self.bgm_tracks[idx].track.track = path

    def _update_loop_infos(
        self, sender: str, data: tuple[int, tuple[float, float, bool]], user_data: Any
    ) -> None:
        idx, loop_info = data
        self.bgm_tracks[idx].track.loop_info = loop_info

    def _update_trim_infos(
        self, sender: str, data: tuple[int, tuple[float, float]], user_data: Any
    ) -> None:
        idx, trim = data
        self.bgm_tracks[idx].track.trims = trim

    def _update_play_intro(self, sender: str, enabled: bool, idx: int) -> None:
        # length will be taken from loop_start in on_okay
        self.bgm_tracks[idx].intro_length = enabled

    def _on_phase_transitions_changed(
        self, sender: str, transitions: list[MusicTransitionRule], user_data: Any
    ) -> None:
        self.phase_transitions = transitions
        self._regenerate_per_track_widgets()

    def _on_okay(self) -> None:
        if not self.msc:
            self.show_message(µ("Select MusicSwitchContainer first", "msg"))
            return

        bgm_enemy_type = dpg.get_value(self._t("bgm_enemy_type"))
        if not bgm_enemy_type or bgm_enemy_type == "*":
            self.show_message(µ("BgmEnemyType not set", "msg"))
            return

        if not self.bgm_tracks:
            self.show_message(µ("No tracks added", "msg"))
            return

        for track in self.bgm_tracks:
            if track.intro_length > 0 and track.track.loop_info[0] <= 0:
                self.show_message(
                    µ("Track #{idx} has intro enabled but loop_start is 0")
                )
                return

        self.show_message()

        with loading_indicator(µ("Working")):
            waves = {
                i: bgm.track.track
                for i, bgm in enumerate(self.bgm_tracks)
                if bgm.track.track.suffix == ".wav"
            }
            if waves:
                wwise = get_config().locate_wwise()
                converted_wavs = wav2wem(wwise, list(waves.values()))
                for wem, idx in zip(converted_wavs, waves.keys()):
                    self.bgm_tracks[idx].track.track = wem

            # Replace transition placeholders
            phase_transitions = []
            for trans in self.phase_transitions:
                trans = deepcopy(trans)

                for idx, track_ref in enumerate(trans.source_ids):
                    if isinstance(track_ref, str):
                        track_idx = int(track_ref.split("#")[-1])
                        trans.source_ids[idx] = track_idx

                for idx, track_ref in enumerate(trans.destination_ids):
                    if isinstance(track_ref, str):
                        track_idx = int(track_ref.split("#")[-1])
                        trans.destination_ids[idx] = track_idx

                phase_transitions.append(trans)

            # Fix up intro lengths
            for track in self.bgm_tracks:
                if track.intro_length > 0:
                    track.intro_length = track.track.loop_info[0]
                    # loop markers are relative to the begin trim
                    track.track.loop_info = (0.0, track.track.loop_info[1])

            nodes = create_boss_bgm(
                self.bnk,
                self.msc,
                self.current_state_path,
                self.bgm_tracks,
                phase_transitions=phase_transitions,
            )

        if self.on_boss_track_created:
            self.on_boss_track_created(bgm_enemy_type, nodes)

        logger.info(f"Created new boss bgm {bgm_enemy_type}")
        dpg.delete_item(self.tag)
        yay()

    # === Build =========================================================

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
            with dpg.tab_bar():
                self._build_tab_tracks()
                self._build_tab_settings()

            dpg.add_separator()
            dpg.add_spacer(height=2)
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Bring the heat!", "button"),
                    callback=self._on_okay,
                    tag=self._t("button_okay"),
                )

    def _build_tab_tracks(self) -> None:
        with dpg.tab(label=µ("Tracks")):
            add_select_node(
                self._get_music_switch_containers,
                "MusicSwitchContainer",
                self._on_music_switch_container_selected,
                get_node_details=get_details_musicswitchcontainer,
                node_type=MusicSwitchContainer,
            )

            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    callback=self._on_bgmenemytype_changed,
                    default_value="*",
                    tag=self._t("bgm_enemy_type"),
                )
                dpg.add_combo(
                    [
                        x
                        for x in GameObjects.GameStates["BgmEnemyType"]
                        if "reserved" in x.lower()
                    ],
                    no_preview=True,
                    callback=self._on_bgmenemytype_changed,
                )
                dpg.add_text("BgmEnemyType")
            dpg.add_button(
                label=µ("State Path", "button"),
                callback=self._edit_state_path,
                tag=self._t("state_path"),
            )

            self._players = add_player_table(
                [],
                get_row_label=self.get_phase_label,
                on_track_added=self._on_track_added,
                on_track_removed=self._on_track_removed,
                on_track_changed=self._on_track_changed,
                on_loop_changed=self._update_loop_infos,
                on_trims_changed=self._update_trim_infos,
            )

            dpg.add_separator()
            add_paragraphs(
                µ(
                    """\
                        - Boss tracks need to be added to cs_Smain (sssss!)
                        - Use the main music controller (1001573296 in ER/NR)
                        - Additional tracks will be used for 'heatup' phases
                        - BgmEnemyType corresponds to BgmBossChrIdConv in Smithbox
                        - Without the dll you can ONLY use vanilla strings!
                        - Add a 6-digit row to BgmBossChrIdConv with your value
                    """,
                    "tips",
                ),
                color=style.light_blue,
            )

    def _build_tab_settings(self) -> None:
        with dpg.tab(label=µ("Settings")):
            self._properties = add_properties_table({}, None)

            dpg.add_spacer(height=4)
            with dpg.table(tag=self._t("per_track_settings")):
                dpg.add_table_column(width_fixed=True)
                with dpg.table_row():
                    dpg.add_text(
                        µ("Add a track first to adjust per-track settings"),
                        color=style.orange,
                    )

            self.phase_transition_matrix = add_transition_matrix(
                self.phase_transitions,
                [],
                self._on_phase_transitions_changed,
                label=µ("Phase Transitions"),
                fixed_sync_type=SyncType.ExitMarker,
            )

    # === Public ========================================================

    def show_message(self, msg: str = None, color: style.RGBA = style.red) -> None:
        """Show or hide the notification label below the separator.

        Pass ``msg=None`` to hide it.
        """
        if not msg:
            dpg.hide_item(self._t("notification"))
            return

        dpg.configure_item(
            self._t("notification"),
            default_value=msg,
            color=color,
            show=True,
        )
