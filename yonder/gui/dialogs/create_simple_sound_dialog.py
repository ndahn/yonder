from typing import Any, Callable
from pathlib import Path
import webbrowser
from dearpygui import dearpygui as dpg

from yonder import Soundbank, calc_hash
from yonder.util import logger
from yonder.convenience import (
    create_simple_sound_rsc,
    create_simple_sound_lc,
    create_simple_sound_sc,
)
from yonder.types import Event
from yonder.enums import PropID, PlaybackMode, RandomMode
from yonder.wem import wav2wem
from yonder.util import is_event_name_valid
from yonder.game import get_selected_game
from yonder.game.data import AmxData
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.localization import µ
from yonder.gui.widgets import (
    DpgItem,
    add_properties_table,
    add_select_actormixer,
    add_player_table,
    add_paragraphs,
    add_state_value_input,
    yay,
)


# The container each mode builds the structure around. LayerContainer and
# SwitchContainer still hang off a RandomSequenceContainer, see convenience
MODE_RSC = "Random"
MODE_LC = "Layer"
MODE_SC = "Switch"
MODES = (MODE_RSC, MODE_LC, MODE_SC)

MODE_TIPS = {
    MODE_RSC: """\
        - Use this for short sounds like sfx
        - One of the sounds is picked every time the event is posted
        - Sounds will be added to a RandomSequenceContainer
        - Will create a play and stop event
    """,
    MODE_LC: """\
        - Use this to play several sounds in parallel
        - Sounds will be added to a LayerContainer
        - Will create a play and stop event
    """,
    MODE_SC: """\
        - Use this when the sound depends on game state
        - Sounds sharing a switch will use a RandomSequenceContainer
        - Structure based on a SwitchContainer
        - Will create a play and stop event
    """,
}


class create_simple_sound_dialog(DpgItem):
    """A dialog for creating a simple sound event from one or more audio files.

    Collects a name, actor mixer reference, optional properties, and a list of
    sound files. On confirm, converts any ``.wav`` files to ``.wem``, calls
    ``create_simple_sound``, and passes the resulting play/stop events to
    ``callback``.

    Parameters
    ----------
    bnk : Soundbank
        Target soundbank; used for ID allocation and duplicate checking.
    callback : callable
        Called as ``callback(play_event, stop_event)`` on success.
    default_name : str
        Pre-filled value for the Name field.
    title : str
        Window title bar label.
    tag : int or str, optional
        Explicit tag; auto-generated if None. Existing item is deleted first.
    """

    def __init__(
        self,
        bnk: Soundbank,
        callback: Callable[[Event, Event], None],
        *,
        default_name: str = "s100200300",
        title: str = "Create Simple Sound",
        tag: str = None,
    ) -> None:
        if tag and dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        super().__init__(tag)

        self._bnk = bnk
        self._callback = callback
        self._properties: dict[PropID, float] = {}
        self._soundfiles: list[Path] = []
        self._window: int | str = None
        self._amx_selector: add_select_actormixer = None
        self._sound_table: add_player_table = None

        # Switch mode only. Rows are rebuilt whenever the sound list changes,
        # so the assignment lives here rather than in the row widgets
        self._mode = MODE_RSC
        self._switch_group: str = ""
        self._switch_values: list[str] = []
        self._switch_inputs: dict[int, add_state_value_input] = {}

        self._build(title, default_name)

    # === Build =========================================================

    def _build(self, title: str, default_name: str) -> None:
        with dpg.window(
            label=title,
            width=400,
            height=400,
            autosize=True,
            no_saved_settings=True,
            tag=self._tag,
            on_close=lambda: dpg.delete_item(self._window),
        ) as self._window:
            dpg.add_input_text(
                label=µ("Name"),
                default_value=default_name,
                callback=self._update_name_and_id,
                tag=self._t("name"),
            )
            with dpg.tooltip(dpg.last_item()):
                dpg.add_text(
                    default_value=µ(
                        "Must follow the pattern CXXXXXXXXX, where C is one of 'acfopsmvxbiyzegd' and X is an 8 to 10 digits number'"
                    ),
                    wrap=300,
                )

            dpg.add_input_text(
                label=µ("Hash"),
                default_value=str(calc_hash(default_name)),
                readonly=True,
                enabled=False,
                tag=self._t("hash"),
            )

            # Actor mixer selector
            self._amx_selector = add_select_actormixer(
                self._bnk,
                µ("ActorMixer", "hirc"),
                self._on_amx_selected,
                tag=self._t("actor_mixer"),
            )

            dpg.add_spacer(height=5)
            dpg.add_radio_button(
                list(MODES),
                default_value=self._mode,
                horizontal=True,
                callback=self._on_mode_changed,
                tag=self._t("mode"),
            )
            with dpg.tooltip(dpg.last_item()):
                add_paragraphs(
                    µ(
                        """\
                            - Random: play one sound at a time
                            - Layer: play sounds in parallel
                            - Switch: select sounds based on game state
                        """,
                        "tips",
                    ),
                )

            # Switch mode: which group the container reads
            self._switch_group_input = add_state_value_input(
                list(get_selected_game().game_syncs.switches),
                self._on_switch_group_changed,
                label=µ("Switch Group"),
                tag=self._t("switch_group"),
            )

            dpg.add_combo(
                [p.name for p in PlaybackMode],
                default_value=PlaybackMode.Random.name,
                label=µ("Playback Mode"),
                tag=self._t("playback_mode"),
            )
            dpg.add_combo(
                [r.name for r in RandomMode],
                default_value=RandomMode.Standard.name,
                label=µ("Random Mode"),
                tag=self._t("random_mode"),
            )
            self._apply_mode()

            # Properties
            dpg.add_spacer(height=5)
            with dpg.tree_node(label=µ("Properties")):
                add_properties_table(
                    self._properties, self._on_properties_changed, label=None
                )

            # Sounds
            self._sound_table = add_player_table(
                self._soundfiles,
                label=µ("Sounds"),
                on_track_added=self._on_soundfile_added,
                on_track_removed=self._on_soundfile_removed,
                on_track_changed=self._on_soundfile_changed,
                add_item_label=µ("+ Add Sounds"),
                get_row_label=lambda i: f"source #{i}",
                add_row_extras=self._add_switch_input,
            )

            dpg.add_separator()
            dpg.add_group(tag=self._t("tips"))
            self._build_tips()

            dpg.add_separator()
            dpg.add_spacer(height=2)
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Summon!", "button"),
                    callback=self._on_okay,
                    tag=self._t("simple_sound/button_okay"),
                )
                dpg.add_button(
                    label="?",
                    callback=lambda s, a, u: webbrowser.open(u),
                    user_data="https://ndahn.github.io/yonder/tools/simple_sounds/",
                )
                with dpg.tooltip(dpg.last_item()):
                    dpg.add_text("https://ndahn.github.io/yonder/tools/simple_sounds/")

    def _build_tips(self) -> None:
        dpg.delete_item(self._t("tips"), children_only=True)

        # add_paragraphs builds into the container stack, it takes no parent
        dpg.push_container_stack(self._t("tips"))
        try:
            add_paragraphs(µ(MODE_TIPS[self._mode], "tips"), color=style.light_blue)
        finally:
            dpg.pop_container_stack()

    def _apply_mode(self) -> None:
        """Show only the settings the current mode actually uses."""
        for item, modes in (
            ("playback_mode", (MODE_RSC,)),
            ("random_mode", (MODE_RSC,)),
            ("switch_group", (MODE_SC,)),
        ):
            if dpg.does_item_exist(self._t(item)):
                dpg.configure_item(self._t(item), show=self._mode in modes)

        for widget in self._switch_inputs.values():
            dpg.configure_item(widget.tag, show=self._mode == MODE_SC)

    def _add_switch_input(self, idx: int, path: Path) -> None:
        """The per-sound switch value, built into each row of the sound table."""
        while len(self._switch_values) <= idx:
            self._switch_values.append("")

        widget = add_state_value_input(
            self._switch_values_for_group(),
            self._on_switch_value_changed,
            default_value=self._switch_values[idx],
            label=µ("Switch"),
            user_data=idx,
        )
        self._switch_inputs[idx] = widget
        dpg.configure_item(widget.tag, show=self._mode == MODE_SC)

    def _switch_values_for_group(self) -> list[str]:
        switches = get_selected_game().game_syncs.switches
        return list(switches.get(self._switch_group, []))

    # === DPG callbacks =================================================

    def _on_mode_changed(self, sender: str, mode: str, ud: Any) -> None:
        self._mode = mode
        self._apply_mode()
        self._build_tips()

    def _on_switch_group_changed(
        self, sender: str, info: tuple[int, str], ud: Any
    ) -> None:
        self._switch_group = info[1]

        # Offer the new group's values in every row that is already there
        values = self._switch_values_for_group()
        for widget in self._switch_inputs.values():
            widget.items = values

    def _on_switch_value_changed(
        self, sender: str, info: tuple[int, str], idx: int
    ) -> None:
        while len(self._switch_values) <= idx:
            self._switch_values.append("")

        self._switch_values[idx] = info[1] if info[0] else ""

    def _update_name_and_id(self, sender: str, new_name: str, ud: Any) -> None:
        if not new_name:
            return
        dpg.set_value(self._t("hash"), str(calc_hash(new_name)))

    def _on_amx_selected(self, sender: str, info: AmxData, ud: Any) -> None:
        if info:
            dpg.set_value(self._t("actor_mixer"), info.nid)

    def _on_properties_changed(
        self, sender: str, new_properties: dict[PropID, float], ud: Any
    ) -> None:
        self._properties.clear()
        self._properties.update(new_properties)

    def _on_soundfile_added(self, sender: str, path: Path, user_data: Any) -> None:
        self._soundfiles.append(path)
        self._switch_values.append("")

    def _on_soundfile_removed(self, sender: str, idx: int, user_data: Any) -> None:
        self._soundfiles.pop(idx)
        if idx < len(self._switch_values):
            self._switch_values.pop(idx)

        # The rows below it shifted up, so their widgets are stale
        self._switch_inputs = {
            i: w for i, w in self._switch_inputs.items() if i < len(self._soundfiles)
        }

    def _on_soundfile_changed(
        self, sender: str, info: tuple[int, Path], user_data: Any
    ) -> None:
        idx, path = info
        self._soundfiles[idx] = path

    def _on_okay(self) -> None:
        name = dpg.get_value(self._t("name"))
        if not name:
            self.show_message(µ("Name not specified", "msg"))
            return

        if not is_event_name_valid(name):
            self.show_message(µ("Invalid name"))
            return

        if f"Play_{name}" in self._bnk or f"Stop_{name}" in self._bnk:
            self.show_message(µ("An event with this name already exists", "msg"))
            return

        amx = self._amx_selector.selected_node
        if not amx:
            self.show_message(µ("ActorMixer not specified", "msg"))
            return

        if not self._soundfiles:
            self.show_message(µ("No sounds specified", "msg"))
            return

        switch_map = {}
        if self._mode == MODE_SC:
            if not self._switch_group:
                self.show_message(µ("Switch group not specified", "msg"))
                return

            # Several sounds may share a switch, which randomizes between them
            for idx in range(len(self._soundfiles)):
                value = self._switch_values[idx] if idx < len(self._switch_values) else ""
                if not value:
                    self.show_message(
                        µ("No switch assigned to source #{idx}", "msg").format(idx=idx)
                    )
                    return

                switch_map.setdefault(value, []).append(idx)

        waves = [f for f in self._soundfiles if f.suffix == ".wav"]
        if waves:
            wwise = get_config().locate_wwise()
            converted = wav2wem(wwise, waves)
            for wem in converted:
                for idx, f in enumerate(self._soundfiles):
                    if f.stem == wem.stem:
                        self._soundfiles[idx] = wem

        self.show_message()

        if self._mode == MODE_RSC:
            (play_evt, stop_evt), _, _ = create_simple_sound_rsc(
                self._bnk,
                name,
                self._soundfiles,
                amx,
                playback_mode=PlaybackMode[dpg.get_value(self._t("playback_mode"))],
                random_mode=RandomMode[dpg.get_value(self._t("random_mode"))],
                properties=self._properties,
            )
        elif self._mode == MODE_LC:
            (play_evt, stop_evt), _, _ = create_simple_sound_lc(
                self._bnk,
                name,
                self._soundfiles,
                amx,
                properties=self._properties,
            )
        else:
            (play_evt, stop_evt), _, _ = create_simple_sound_sc(
                self._bnk,
                name,
                self._soundfiles,
                self._switch_group,
                switch_map,
                amx,
                properties=self._properties,
            )

        logger.info(f"Created simple sound {name} ({self._mode})")
        self._callback(play_evt, stop_evt)
        dpg.delete_item(self.tag)
        yay()

    # === Public ========================================================

    def show_message(self, msg: str = None, color: style.RGBA = style.red) -> None:
        """Show or hide the notification label. Pass ``msg=None`` to hide."""
        if not msg:
            dpg.hide_item(self._t("notification"))
            return

        dpg.configure_item(
            self._t("notification"),
            default_value=msg,
            color=color,
            show=True,
        )
