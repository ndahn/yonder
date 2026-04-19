from typing import Any, Callable
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.types import MusicSwitchContainer
from yonder.hash import calc_hash, lookup_name
from yonder.convenience import create_boss_bgm
from yonder.wem import wav2wem
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.config import get_config
from yonder.gui.widgets import (
    DpgItem,
    add_node_reference,
    add_paragraphs,
    add_player_table,
)
from .edit_state_path_dialog import edit_state_path_dialog


class create_boss_track_dialog(DpgItem):
    def __init__(
        self,
        bnk: Soundbank,
        on_boss_track_created: Callable[[str, list[HIRCNode]], None],
        *,
        title: str = "New Boss BGM",
        tag: str = None,
    ) -> str:
        if not tag:
            tag = dpg.generate_uuid()
        elif dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        self.bnk = bnk
        self.on_boss_track_created = on_boss_track_created
        self.msc: MusicSwitchContainer = None
        self.bgm_enemy_type_hash = calc_hash("BgmEnemyType")
        self.bgm_enemy_type_idx: int = -1
        self.current_state_path: list[str] = []
        self.bgm_tracks: list[Path] = []
        self.bgm_loop_infos: list[tuple[float, float, bool]] = []
        self.bgm_trim_infos: list[tuple[float, float]] = []
        self.play_intro_enabled: list[bool] = []

        self._build(title)

    # === Helpers =================================================

    @staticmethod
    def get_phase_label(phase: int) -> str:
        return f"Heatup {phase}" if phase > 0 else "Normal"

    def _get_music_switch_containers(self, filt: str) -> list[MusicSwitchContainer]:
        filt = f"type=MusicSwitchContainer arguments:*/group_id={self.bgm_enemy_type_hash} {filt}"
        return list(self.bnk.query(filt))

    def _get_music_switch_container_details(
        self, msc: MusicSwitchContainer
    ) -> list[str]:
        return [lookup_name(s.group_id, f"#{s.group_id}") for s in msc.arguments]

    def _edit_state_path(self) -> None:
        if not self.msc:
            self.show_message(µ("Select MusicSwitchContainer first", "msg"))
            return

        edit_state_path_dialog(
            self.bnk,
            self.msc,
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
            dpg.add_text(
                "Play intro before loop_start", tag=self._t("boss_bgm/intro_enabled")
            )
            for i, _ in enumerate(self.bgm_tracks):
                dpg.add_checkbox(
                    default_value=self.play_intro_enabled[i],
                    callback=self._update_play_intro,
                    tag=self._t(f"play_intro:{i}"),
                    user_data=i,
                )

        dpg.pop_container_stack()

    # === DPG callbacks =================================================

    def _on_music_switch_container_selected(
        self, sender: str, selected_msc: int | MusicSwitchContainer, user_data: Any
    ) -> None:
        if isinstance(selected_msc, int):
            selected_msc = self.bnk.get(selected_msc)

        for i, arg in enumerate(selected_msc.arguments):
            if arg.group_id == self.bgm_enemy_type_hash:
                bgm_enemy_type_idx = i
                break
        else:
            self.show_message(
                µ(
                    "MSC does not have a BgmEnemyType argument",
                    "msg",
                )
            )
            return

        msc = selected_msc
        current_state_path = ["*" for _ in msc.arguments]
        current_state_path[bgm_enemy_type_idx] = dpg.get_value(
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

    def _on_bgm_tracks_changed(
        self, sender: str, data: tuple[list[Path], tuple, tuple, tuple], user_data: Any
    ) -> None:
        self.bgm_tracks = data[0]
        self.bgm_loop_infos = data[1]
        self.bgm_trim_infos = data[2]

        if len(self.bgm_tracks) < len(self.play_intro_enabled):
            self.play_intro_enabled[:] = self.play_intro_enabled[: len(self.bgm_tracks)]
        elif len(self.bgm_tracks) > len(self.play_intro_enabled):
            self.play_intro_enabled.extend(
                [False] * (len(self.bgm_tracks) - len(self.play_intro_enabled))
            )

        self._regenerate_per_track_widgets()

    def _update_loop_infos(
        self, sender: str, data: tuple[int, tuple[float, float, bool]], user_data: Any
    ) -> None:
        idx, loop_info = data
        self.bgm_loop_infos[idx] = loop_info

    def _update_trim_infos(
        self, sender: str, data: tuple[int, tuple[float, float]], user_data: Any
    ) -> None:
        idx, trim = data
        self.bgm_trim_infos[idx] = trim

    def _update_play_intro(self, sender: str, enabled: bool, idx: int) -> None:
        self.play_intro_enabled[idx] = enabled

    def _on_okay(self) -> None:
        if not self.msc:
            self.show_message(µ("Select MusicSwitchContainer first", "msg"))
            return

        bgm_enemy_type = dpg.get_value(self._t("bgm_enemy_type"))
        if not bgm_enemy_type or bgm_enemy_type == "*":
            self.show_message(µ("BgmEnemyType not set", "msg"))
            return

        if not self.bgm_tracks:
            self.show_message(µ("Must add at least one BGM track", "msg"))
            return

        self.show_message()

        waves = [f for f in self.bgm_tracks if f.name.endswith(".wav")]
        if waves:
            wwise = get_config().locate_wwise()
            converted_wavs = wav2wem(wwise, waves)
            for wem in converted_wavs:
                for idx, f in enumerate(self.bgm_tracks):
                    if f.stem == wem.stem:
                        self.bgm_tracks[idx] = wem

        # TODO transition rules?
        loop_info = [(li[0] * 1000, li[1] * 1000) for li in self.bgm_loop_infos]
        nodes = create_boss_bgm(
            self.bnk,
            self.msc,
            self.current_state_path,
            self.bgm_tracks,
            loop_info,
            self.play_intro_enabled,
        )
        if self.on_boss_track_created:
            self.on_boss_track_created(bgm_enemy_type, nodes)

        self.show_message(µ("Yay!", "msg"), color=style.blue)
        dpg.set_item_label(self._t("boss_bgm/button_okay"), µ("Again?"))

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
            add_node_reference(
                self._get_music_switch_containers,
                "MusicSwitchContainer",
                self._on_music_switch_container_selected,
                get_node_details=self._get_music_switch_container_details,
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
                        "EventBoss_Reserved15",
                        "EventBoss_Reserved14",
                        "EventBoss_Reserved13",
                        "EventBoss_Reserved12",
                        "EventBoss_Reserved11",
                        "EventBoss_Reserved10",
                        "EventBoss_Reserved09",
                        "EventBoss_Reserved08",
                        "Reserved",
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

            add_player_table(
                [],
                self._on_bgm_tracks_changed,
                get_row_label=self.get_phase_label,
                on_loop_changed=self._update_loop_infos,
                on_trim_changed=self._update_trim_infos,
            )

            dpg.add_table(tag=self._t("per_track_settings"))

            dpg.add_separator()
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            add_paragraphs(
                µ(
                    """\
                        - Boss tracks need to be added to cs_smain
                        - Use the main MusicSwitchContainer (1001573296 in Elden Ring)
                        - Additional tracks will be used for 'heatup' phases
                        - BgmEnemyType corresponds to BgmBossChrIdConv in Smithbox
                        - Only already existing BgmEnemyType strings can be used!
                        - BgmBossChrIdConv params mus be 6-digit for EMEVD
                    """,
                    "tips",
                ),
                color=style.light_blue,
            )
            dpg.add_spacer(height=5)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Bring the heat!", "button"),
                    callback=self._on_okay,
                    tag=self._t("boss_bgm/button_okay"),
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
