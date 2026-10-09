from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder import HIRCNode
from yonder.gui import style
from yonder.gui.icons import Icons
from yonder.gui.localization import µ
from yonder.gui.widgets import DpgItem


class add_node_palette(DpgItem):
    """A palette of all HIRC node types, grouped by category.

    Every type is shown as an icon button that can be dragged onto a drop
    target (carrying the type as its payload) or clicked, which calls
    ``callback(sender, app_data, node_type)``.
    """

    def __init__(
        self,
        palette: dict[str, list[type]],
        callback: Callable[[str, type[HIRCNode], Any], None] = None,
        *,
        width: int = 200,
        height: int = 200,
        is_enabled: Callable[[type], bool] = None,
        get_icon: Callable[[type, bool], str] = None,
        get_color: Callable[[type, bool], style.RGBA] = None,
        tag: str = None,
        payload_type: str = "node_type",
        user_data: Any = None,
        **container_kwargs,
    ) -> str:
        super().__init__(tag)

        container_kwargs.setdefault("resizable_x", True)
        container_kwargs.setdefault("autosize_y", True)

        self._palette = palette
        self._is_enabled_hook = is_enabled or (lambda t: True)
        self._get_icon_hook = get_icon or Icons.get_type_icon_tag
        self._get_color_hook = get_color or (
            lambda t: style.type_colors.get(t.__name__, style.white)
        )

        self._callback = callback
        self._user_data = user_data
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

    def _is_enabled(self, tp: type) -> bool:
        if self._is_enabled_hook:
            return self._is_enabled_hook(tp)

        return True

    def _get_color(self, tp: type) -> style.RGBA:
        enabled = self._is_enabled(tp)

        if self._get_color_hook:
            return self._get_color_hook(tp, enabled)

        if enabled:
            return style.type_colors.get(tp.__name__, style.white)

        return style.light_grey

    def _get_icon(self, tp: type) -> str:
        enabled = self._is_enabled(tp)

        if self._get_icon_hook:
            return self._get_icon_hook(tp, enabled)

        return Icons.get_type_icon_tag(tp)

    def destroy(self):
        self._delete_item(self._t("resize_handler_registry"))

    def _on_resize(self) -> None:
        if not dpg.does_item_exist(self.tag):
            return

        dpg.delete_item(self.tag, children_only=True, slot=1)
        dpg.push_container_stack(self.tag)

        w, _ = dpg.get_item_rect_size(self.tag)

        for cat, nodes in self._palette.items():
            dpg.add_separator(label=µ(cat))
            row = None
            row_width = 0

            for tp in nodes:
                row_width += 55
                if not row or row_width > w:
                    row = dpg.add_group(horizontal=True)
                    row_width = 0

                color = self._get_color(tp)
                icon = self._get_icon(tp)

                btn = dpg.add_image_button(
                    icon,
                    width=24,
                    height=24,
                    tint_color=color,
                    callback=lambda s, a, u: self._callback(
                        self.tag, u, self._user_data
                    ),
                    user_data=tp,
                    parent=row,
                )

                with dpg.tooltip(parent=btn):
                    dpg.add_text(tp.__name__)

                with dpg.drag_payload(
                    parent=btn, drag_data=tp, payload_type=self._payload_type
                ):
                    dpg.add_image(icon, tint_color=color)

        dpg.pop_container_stack()
