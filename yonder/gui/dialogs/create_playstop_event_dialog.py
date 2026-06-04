from typing import Callable
import re
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.types import Event, Action
from yonder.enums import SoundType
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.widgets import DpgItem, add_select_node, add_paragraphs
from yonder.gui.widgets.select_node import get_details_generic


class create_wwise_event_dialog(DpgItem):
    def __init__(
        self,
        bnk: Soundbank,
        callback: Callable[[list[HIRCNode]], None],
        *,
        title: str = "New Event",
        tag: str = None,
    ) -> str:
        super().__init__(tag, "create_event")

        self._bnk = bnk
        self._callback = callback

        self._build(title)

    def _on_okay(self) -> None:
        sound_id = dpg.get_value(self._t("sound_id"))
        if not sound_id:
            self.show_message(µ("Name not specified", "msg"))
            return

        allow_arbitrary_name = dpg.get_value(self._t("allow_arbitrary_name"))
        if not allow_arbitrary_name:
            sound_type_label = dpg.get_value(self._t("sound_type"))
            sound_type = SoundType[sound_type_label.split(" ")[0]]
            sound_id = f"{sound_type.value}{sound_id}"

        external_id = int(dpg.get_value(self._t("external_id")))
        if not external_id:
            self.show_message(µ("Target ID not set"))

        self.show_message()

        new_nodes = []
        create_play_event = dpg.get_value(self._t("create_play_event"))

        if create_play_event:
            play_evt = Event.new(f"Play_{sound_id}")
            play_action = Action.new_play_action(
                self._bnk.new_id(), external_id, bank_id=self._bnk.bank_id
            )
            play_evt.attach(play_action)
            new_nodes.extend([play_evt, play_action])

        create_stop_event = dpg.get_value(self._t("create_stop_event"))
        if create_stop_event:
            stop_evt = Event.new(f"Stop_{sound_id}")
            stop_action = Action.new_stop_action(self._bnk.new_id(), external_id)
            stop_evt.attach(stop_action)
            new_nodes.extend([stop_evt, stop_action])

        if not create_play_event and not create_stop_event:
            self.show_message(µ("No events created", "msg"))
            return

        self._bnk.add_nodes(*new_nodes)

        if self._callback:
            self._callback(new_nodes)

        self.show_message(µ("Success!", "msg"), color=style.blue)
        dpg.set_item_label(self._t("playstop/button_okay"), µ("Yay!"))
        dpg.set_item_callback(
            self._t("playstop/button_okay"),
            lambda s, a, u: dpg.delete_item(self.tag),
        )

    def _arbitrary_names_callback(self, sender: str, enabled: bool) -> None:
        if enabled:
            dpg.configure_item(self._t("sound_id"), decimal=False, width=0)
            dpg.configure_item(self._t("sound_type"), show=False)

        else:
            dpg.configure_item(self._t("sound_id"), decimal=True, width=180)
            dpg.configure_item(self._t("sound_type"), show=True)

            sound_id: str = dpg.get_value(self._t("sound_id"))
            if not sound_id.isdecimal():
                dpg.set_value(self._t("sound_id"), "")

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
            with dpg.group(horizontal=True):
                dpg.add_combo(
                    items=[f"{t.name} ({t.value})" for t in SoundType],
                    default_value=f"{SoundType.Sfx.name} ({SoundType.Sfx.value})",
                    width=100,
                    tag=self._t("sound_type"),
                )
                dpg.add_input_text(
                    label=µ("Sound ID"),
                    decimal=True,
                    hint="123456789",
                    width=180,
                    tag=self._t("sound_id"),
                )
            
            dpg.add_checkbox(
                label=µ("Allow arbitrary names"),
                default_value=False,
                tag=self._t("allow_arbitrary_names"),
                callback=self._arbitrary_names_callback,
            )

            add_select_node(
                self._bnk.query,
                µ("Target node"),
                None,
                node_filter=lambda n: hasattr(n, "parent"),
                get_node_details=get_details_generic,
                tag=self._t("external_id"),
            )

            dpg.add_checkbox(
                label=µ("Create play action"),
                default_value=True,
                tag=self._t("create_play_event"),
            )
            dpg.add_checkbox(
                label=µ("Create stop action"),
                default_value=True,
                tag=self._t("create_stop_event"),
            )

            dpg.add_separator()
            add_paragraphs(
                µ(
                    """\
                        - Create events for an existing structure
                        - Will only create the events
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
                    label=µ("Chop chop!", "button"),
                    callback=self._on_okay,
                    tag=self._t("playstop/button_okay"),
                )

    def show_message(
        self, msg: str = None, color: tuple[int, int, int, int] = style.red
    ) -> None:
        if not msg:
            dpg.hide_item(self._t("notification"))
            return

        dpg.configure_item(
            self._t("notification"),
            default_value=msg,
            color=color,
            show=True,
        )
