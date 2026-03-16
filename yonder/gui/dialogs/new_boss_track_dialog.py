from typing import Any, Callable
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder import Soundbank, Node
from yonder.node_types import MusicSwitchContainer
from yonder.hash import calc_hash, lookup_name
from yonder.util import logger
from yonder.convenience import create_boss_bgm
from yonder.wem import wav2wem
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.widgets import (
    add_node_widget,
    add_paragraphs,
    add_player_table,
    add_transition_matrix,
)
from .create_state_path_dialog import create_state_path_dialog


def new_boss_track_dialog(
    bnk: Soundbank,
    on_boss_track_created: Callable[[str, list[Node]], None],
    *,
    title: str = "New Boss BGM",
    tag: str = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()
    elif dpg.does_item_exist(tag):
        dpg.delete_item(tag)

    msc: MusicSwitchContainer = None
    bgm_enemy_type_hash = calc_hash("BgmEnemyType")
    bgm_enemy_type_idx: int = -1
    current_state_path: list[str] = []
    bgm_tracks: list[Path] = []
    bgm_loop_infos: list[tuple[float, float, bool]] = []

    def get_music_switch_containers(filt: str) -> list[MusicSwitchContainer]:
        if not bnk:
            show_message("No soundbank loaded")
            return []

        filt = f"type=MusicSwitchContainer arguments:*/group_id={bgm_enemy_type_hash} {filt}"
        return list(bnk.query(filt))

    def get_music_switch_container_details(msc: MusicSwitchContainer) -> list[str]:
        return [lookup_name(s, f"#{s}") for s in msc.arguments]

    def on_music_switch_container_selected(
        sender: str, selected_msc: int | MusicSwitchContainer, user_data: Any
    ) -> None:
        nonlocal msc
        nonlocal bgm_enemy_type_idx
        nonlocal current_state_path

        if isinstance(selected_msc, int):
            selected_msc = bnk.get(selected_msc)

        if not isinstance(selected_msc, MusicSwitchContainer):
            show_message("Not a MusicSwitchContainer")
            return

        for i, arg in enumerate(selected_msc.arguments):
            if arg == bgm_enemy_type_hash:
                bgm_enemy_type_idx = i
                break
        else:
            show_message("MSC does not have a BgmEnemyType argument")
            return

        msc = selected_msc
        current_state_path = ["*" for _ in msc.arguments]
        current_state_path[bgm_enemy_type_idx] = dpg.get_value(f"{tag}_bgm_enemy_type")
        show_message()

    def on_bgmenemytype_changed(sender: str, value: str, user_data: Any) -> None:
        if not value or value == "*":
            show_message("BgmEnemyType must not be empty")
            return

        if msc:
            current_state_path[bgm_enemy_type_idx] = value

        dpg.set_value(f"{tag}_bgm_enemy_type", value)
        show_message()

    def edit_state_path() -> None:
        if not bnk:
            show_message("No soundbank loaded")
            return

        if not msc:
            show_message("Select MusicSwitchContainer first")
            return

        create_state_path_dialog(
            bnk,
            msc,
            on_statepath_selected,
            state_path=current_state_path,
            hide_node_id=True,
        )

    def on_statepath_selected(
        sender: str, state_path: list[str], user_data: Any
    ) -> None:
        current_state_path.clear()
        current_state_path.extend(state_path)
        dpg.set_value(f"{tag}_bgm_enemy_type", state_path[bgm_enemy_type_idx])
        show_message()

    def on_bgm_tracks_changed(sender: str, paths: list[Path], user_data: Any) -> None:
        nonlocal bgm_tracks
        bgm_tracks = paths

    def update_loop_infos(
        sender: str, new_loop_infos: list[tuple[float, float, bool]], user_data: Any
    ) -> None:
        nonlocal bgm_loop_infos
        bgm_loop_infos = new_loop_infos

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
        if not bnk:
            show_message("No soundbank loaded")
            return

        if not msc:
            show_message("Select MusicSwitchContainer first")
            return

        bgm_enemy_type = dpg.get_value(f"{tag}_bgm_enemy_type")
        if not bgm_enemy_type or bgm_enemy_type == "*":
            show_message("BgmEnemyType not set")
            return

        if not bgm_tracks:
            show_message("Must add at least one BGM track")
            return

        show_message()

        waves = {f.stem: i for i, f in enumerate(bgm_tracks) if f.name.endswith(".wav")}
        if waves:
            logger.info(f"Converting {len(waves)} wave files to wem")
            wwise = get_config().locate_wwise()
            converted_wavs = wav2wem(wwise, waves)
            for wem in converted_wavs:
                idx = waves[wem.stem]
                bgm_tracks[idx] = wem

        # TODO transition rules
        loop_info = [(li[0], li[1]) for li in bgm_loop_infos]
        nodes = create_boss_bgm(bnk, msc, current_state_path, bgm_tracks, loop_info)
        if on_boss_track_created:
            on_boss_track_created(bgm_enemy_type, nodes)

        show_message("Yay!", color=style.blue)
        dpg.set_item_label(f"{tag}_button_okay", "Again?")

    with dpg.window(
        label=title,
        width=400,
        height=400,
        autosize=True,
        no_saved_settings=True,
        tag=tag,
        on_close=lambda: dpg.delete_item(window),
    ) as window:
        add_node_widget(
            get_music_switch_containers,
            "MusicSwitchContainer",
            on_music_switch_container_selected,
            get_node_details=get_music_switch_container_details,
            node_type=MusicSwitchContainer,
        )

        with dpg.group(horizontal=True):
            dpg.add_input_text(
                callback=on_bgmenemytype_changed,
                default_value="*",
                tag=f"{tag}_bgm_enemy_type",
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
                callback=on_bgmenemytype_changed,
            )
            dpg.add_text("BgmEnemyType")
        dpg.add_button(
            label="State Path",
            callback=edit_state_path,
        )

        # TODO edit markers dialog
        w = add_player_table(
            [],
            on_bgm_tracks_changed,
            get_row_label=lambda i: f"Heatup {i}" if i > 0 else "Normal",
            on_loop_changed=update_loop_infos,
        )
        with dpg.tooltip(w):
            dpg.add_text(
                "First track is the regular BGM, each subsequent track will be used for 'heatup' phases. Vanilla bosses have up to 3 phases controlled by the BossBattleState switch (None, HU1, HU2, ...).",
                wrap=330,
                color=style.light_blue,
            )

        dpg.add_separator()
        dpg.add_text(show=False, tag=f"{tag}_notification", color=style.red)

        add_paragraphs(
            """\
            - Boss tracks need to be added to cs_smain.
            - If multiple MusicSwitchContainers are available, find the one where all other bosses are handled. 
            - Without a dll you can only use one of the reserved BgmEnemyType values. Otherwise, add your custom strings to the BgmBossChrIdConv param in smithbox.
""",
            color=style.light_blue,
        )
        dpg.add_spacer(height=5)

        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Bring the heat!", callback=on_okay, tag=f"{tag}_button_okay"
            )
