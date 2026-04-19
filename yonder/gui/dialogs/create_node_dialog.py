from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.gui.localization import µ
from yonder.util import get_function_spec
from yonder.gui import style
from yonder.gui.widgets import DpgItem, add_generic_widget


class create_node_dialog(DpgItem):
    """A modal dialog for creating a new ``HIRCNode`` of any registered type.

    Presents a type selector combo, a read-only ID field, and dynamically
    generated argument widgets derived from the selected type's ``new()``
    signature. Confirming calls ``callback`` with the constructed node and
    closes the window.

    If ``tag`` already exists as a DPG item it is deleted and recreated,
    allowing the dialog to be reopened without stale state.

    Parameters
    ----------
    bnk : Soundbank
        Used to allocate the new node ID via ``bnk.new_id()``.
    callback : callable
        Called as ``callback(node)`` when the user confirms.
    title : str
        Window title bar label.
    tag : int or str, optional
        Explicit tag; auto-generated if None.
    """

    def __init__(
        self,
        bnk: Soundbank,
        callback: Callable[[HIRCNode], None],
        *,
        title: str = "Create Node",
        tag: int | str = None,
    ) -> None:
        if tag and dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        super().__init__(tag if tag else dpg.generate_uuid())

        self._bnk = bnk
        self._callback = callback
        self._nid = bnk.new_id()
        self._node_types: dict[str, type] = {
            c.__name__: c for c in HIRCNode.__subclasses__()
        }
        self._selected_type: str = next(iter(self._node_types))
        self._node_args: dict[str, Any] = {}
        self._window: int | str = None

        self._build(title)
        self._on_type_selected(None, self._selected_type, None)

    # === Build =========================================================

    def _build(self, title: str) -> None:
        with dpg.window(
            label=title,
            width=400,
            height=400,
            autosize=True,
            no_saved_settings=True,
            tag=self._tag,
            on_close=lambda: dpg.delete_item(self._window),
        ) as self._window:
            dpg.add_combo(
                list(self._node_types.keys()),
                default_value=self._selected_type,
                callback=self._on_type_selected,
                width=300,
                tag=self._t("node_type"),
            )
            dpg.add_input_text(
                label=µ("id", "hirc"),
                readonly=True,
                enabled=False,
                default_value=str(self._nid),
                tag=self._t("node_id"),
            )
            with dpg.child_window(auto_resize_y=True, tag=self._t("node_args")):
                pass

            dpg.add_separator()
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Make!", "button"),
                    callback=self._on_okay,
                    tag=self._t("create_node/button_okay"),
                )

    # === DPG callbacks =================================================

    def _set_arg(self, sender: str, app_data: Any, key: str) -> None:
        self._node_args[key] = app_data

    def _on_type_selected(self, sender: str, type_name: str, ud: Any) -> None:
        if type_name == self._selected_type and sender is not None:
            return

        self._selected_type = type_name
        spec = get_function_spec(self._node_types[type_name].new, None)
        self._node_args.clear()

        dpg.delete_item(self._t("node_args"), children_only=True, slot=1)

        for name, arg in spec.items():
            if name in ("nid", "parent"):
                continue

            self._node_args[name] = arg.default
            add_generic_widget(
                arg.type,
                name,
                self._set_arg,
                default=arg.default,
                user_data=name,
                parent=self._t("node_args"),
                tag=self._t(f"arg_{name}"),
            )

    def _on_okay(self) -> None:
        self._node_args["nid"] = self._nid
        node = self._node_types[self._selected_type].new(**self._node_args)
        self._callback(node)
        dpg.delete_item(self._window)

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
