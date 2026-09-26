from typing import Any
from dearpygui import dearpygui as dpg

from yonder.types import (
    HIRCNode,
    Action,
    ActorMixer,
    Attenuation,
    AuxiliaryBus,
    Bus,
    DialogueEvent,
    EffectCustom,
    EffectShareSet,
    Event,
    LayerContainer,
    LFOModulator,
    MusicRandomSequenceContainer,
    MusicSegment,
    MusicSwitchContainer,
    MusicTrack,
    RandomSequenceContainer,
    Sound,
    SwitchContainer,
    TimeModulator,
)
from yonder.gui import style
from yonder.gui.icons import Icons
from yonder.gui.localization import µ
from yonder.gui.widgets import DpgItem


_categories: dict[str, list[type[HIRCNode]]] = {
    "Sounds": [
        RandomSequenceContainer,
        SwitchContainer,
        LayerContainer,
        Sound,
        DialogueEvent,
    ],
    "Music": [
        MusicRandomSequenceContainer,
        MusicSwitchContainer,
        MusicSegment,
        MusicTrack,
    ],
    "Playback": [
        Event,
        Action,
        ActorMixer,
        Bus,
        AuxiliaryBus,
    ],
    "Effects": [
        Attenuation,
        EffectShareSet,
        EffectCustom,
        LFOModulator,
        TimeModulator,
    ],
}


class add_node_blocks(DpgItem):
    def __init__(
        self,
        *,
        width: int = 200,
        height: int = 200,
        tag: str = None,
        payload_type: str = "node_type",
        **container_kwargs,
    ) -> str:
        super().__init__(tag)

        container_kwargs.setdefault("resizable_x", True)
        container_kwargs.setdefault("autosize_y", True)

        self._payload_type = payload_type
        dpg.add_child_window(
            width=width,
            height=height,
            tag=self.tag,
            **container_kwargs,
        )

        with dpg.item_handler_registry(tag=self._t("resize_handler_registry")):
            dpg.add_item_resize_handler(callback=self._on_resize)
        dpg.bind_item_handler_registry(self.tag, self._t("resize_handler_registry"))

        dpg.set_frame_callback(dpg.get_frame_count() + 2, self._on_resize)

    def destroy(self):
        self._delete_item(self._t("resize_handler_registry"))

    def _on_resize(self) -> None:
        dpg.delete_item(self.tag, children_only=True, slot=1)
        dpg.push_container_stack(self.tag)

        w, _ = dpg.get_item_rect_size(self.tag)

        for cat, nodes in _categories.items():
            dpg.add_separator(label=µ(cat))
            row = None
            row_width = 0
            todo = list(nodes)

            while todo:
                tp = todo.pop(0)

                row_width += 55
                if not row or row_width > w:
                    row = dpg.add_group(horizontal=True)
                    row_width = 0

                color = style.type_colors.get(tp.__name__, style.white)
                icon = Icons.get_type_icon_tag(tp)
                btn = dpg.add_image_button(
                    icon,
                    width=24,
                    height=24,
                    tint_color=color,
                    parent=row,
                )

                with dpg.tooltip(parent=btn):
                    dpg.add_text(tp.__name__)

                with dpg.drag_payload(
                    parent=btn, drag_data=tp, payload_type=self._payload_type
                ):
                    dpg.add_image(icon, tint_color=color)

        dpg.pop_container_stack()
