from typing import Callable
import re
from dearpygui import dearpygui as dpg

from yonder import Soundbank, Node
from yonder.node_types import Event, Action
from yonder.enums import SoundType
from yonder.gui import style
from yonder.gui.widgets import add_generic_widget


def new_wwise_event_dialog(
    bnk: Soundbank,
    callback: Callable[[list[Node]], None],
    *,
    title: str = "New Event",
    tag: str = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()
    elif dpg.does_item_exist(tag):
        dpg.delete_item(tag)

    def show_message(msg: str = None, color: tuple[int, int, int, int] = style.red) -> None:
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
        name = dpg.get_value(f"{tag}_name")
        if not name:
            show_message("Name not specified")
            return

        allow_arbitrary_name = dpg.get_value(f"{tag}_allow_arbitrary_name")
        if not allow_arbitrary_name:
            valid_chars = "".join(str(s) for s in SoundType)
            if not re.match(rf"[{valid_chars}]\d{4, 10}"):
                show_message("Name not matching pattern (x123456789)")
                return

        show_message()

        new_nodes = []
        target_id = int(dpg.get_value(f"{tag}_target_id"))

        create_play_event = dpg.get_value(f"{tag}_create_play_event")
        if create_play_event:
            play_evt = Event.new(f"Play_{name}")
            play_action = Action.new_play_action(
                bnk.new_id(), target_id, bank_id=bnk.id
            )
            play_evt.add_action(play_action)
            new_nodes.extend([play_evt, play_action])

        create_stop_event = dpg.get_value(f"{tag}_create_stop_event")
        if create_stop_event:
            stop_evt = Event.new(f"Stop_{name}")
            stop_action = Action.new_stop_action(bnk.new_id(), target_id)
            stop_evt.add_action(stop_action)
            new_nodes.extend([stop_evt, stop_action])

        if not create_play_event and not create_stop_event:
            show_message("No events created")
            return

        bnk.add_nodes(new_nodes)

        callback(new_nodes)
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
        dpg.add_input_text(
            label="Name",
            tag=f"{tag}_name",
        )
        dpg.add_checkbox(
            label="Allow arbitrary names",
            default_value=False,
            tag=f"{tag}_allow_arbitrary_names",
        )

        add_generic_widget(
            Node,
            "Target node",
            None,
            tag=f"{tag}_target_id",
        )

        dpg.add_checkbox(
            label="Create play action",
            default_value=True,
            tag=f"{tag}_create_play_event",
        )
        dpg.add_checkbox(
            label="Create stop action",
            default_value=True,
            tag=f"{tag}_create_stop_event",
        )

        dpg.add_separator()
        dpg.add_text(show=False, tag=f"{tag}_notification", color=style.red)

        with dpg.group(horizontal=True):
            dpg.add_button(label="Chop chop!", callback=on_okay, tag=f"{tag}_button_okay")
