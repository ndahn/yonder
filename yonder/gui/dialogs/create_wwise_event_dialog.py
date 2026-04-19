from typing import Callable
import re
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.types import Event, Action
from yonder.enums import SoundType
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.widgets import DpgItem, add_node_reference


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
        name = dpg.get_value(self._t("name"))
        if not name:
            self.show_message(µ("Name not specified", "msg"))
            return

        allow_arbitrary_name = dpg.get_value(self._t("allow_arbitrary_name"))
        if not allow_arbitrary_name:
            valid_chars = "".join(str(s) for s in SoundType)
            if not re.match(rf"[{valid_chars}]\d{4, 10}"):
                self.show_message(
                    µ(
                        "Name not matching pattern (x123456789)",
                        "msg",
                    )
                )
                return

        self.show_message()

        new_nodes = []
        external_id = int(dpg.get_value(self._t("external_id")))

        create_play_event = dpg.get_value(self._t("create_play_event"))
        if create_play_event:
            play_evt = Event.new(f"Play_{name}")
            play_action = Action.new_play_action(
                self._bnk.new_id(), external_id, bank_id=self._bnk.bank_id
            )
            play_evt.add_action(play_action)
            new_nodes.extend([play_evt, play_action])

        create_stop_event = dpg.get_value(self._t("create_stop_event"))
        if create_stop_event:
            stop_evt = Event.new(f"Stop_{name}")
            stop_action = Action.new_stop_action(self._bnk.new_id(), external_id)
            stop_evt.add_action(stop_action)
            new_nodes.extend([stop_evt, stop_action])

        if not create_play_event and not create_stop_event:
            self.show_message(µ("No events created", "msg"))
            return

        self._bnk.add_nodes(new_nodes)

        self._callback(new_nodes)
        self.show_message(µ("Yay!", "msg"), color=style.blue)
        dpg.set_item_label(self._t("button_okay"), "Again?")

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
            dpg.add_input_text(
                label=µ("Name"),
                tag=self._t("name"),
            )
            dpg.add_checkbox(
                label=µ("Allow arbitrary names"),
                default_value=False,
                tag=self._t("allow_arbitrary_names"),
            )

            add_node_reference(
                self._bnk.query,
                µ("Target node"),
                None,
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
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Chop chop!", "button"),
                    callback=self._on_okay,
                    tag=self._t("button_okay"),
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
