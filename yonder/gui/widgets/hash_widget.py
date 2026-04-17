from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder.hash import calc_hash, lookup_name
from yonder.gui.helpers import estimate_drawn_text_size
from .widget import Widget


class add_hash_widget(Widget):
    """A paired hash/string input widget for Dear PyGui.

    Displays an integer hash field and a human-readable name field side by
    side (horizontal) or stacked (vertical). Edits to either field are
    reflected in the other via ``calc_hash`` / ``lookup_name``.

    Parameters
    ----------
    default_value : int
        Initial hash value shown in the hash field.
    on_hash_changed : callable, optional
        Called as ``on_hash_changed(tag, (hash_int, name_str), user_data)``
        whenever either field changes.
    initial_string : str, optional
        If given, pre-fills the string field and skips the initial
        ``lookup_name`` call.
    horizontal : bool
        Layout fields side-by-side when True, stacked when False.
    allow_edit_hash : bool
        Whether the hash input field is editable.
    allow_edit_name : bool
        Whether the string input field is editable.
    string_label : str
        DPG label for the string field.
    hash_label : str
        DPG label for the hash field.
    width : int
        Total pixel width allocated to the widget.
    parent : int or str
        DPG parent item.
    tag : int or str
        Explicit tag; auto-generated if 0.
    user_data : any
        Passed through to ``on_hash_changed``.
    """

    def __init__(
        self,
        default_value: int = 0,
        on_hash_changed: Callable[[str, tuple[int, str], Any], None] = None,
        *,
        initial_string: str = None,
        horizontal: bool = True,
        allow_edit_hash: bool = True,
        allow_edit_name: bool = True,
        string_label: str = "String",
        hash_label: str = "Hash",
        width: int = 280,
        parent: int | str = 0,
        tag: int | str = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self._on_hash_changed = on_hash_changed
        self._user_data = user_data

        string_label = string_label or ""
        hash_label = hash_label or ""

        self._build(
            default_value,
            initial_string,
            horizontal,
            allow_edit_hash,
            allow_edit_name,
            string_label,
            hash_label,
            width,
            parent,
        )

        if initial_string is None:
            self._on_hash_update(None, default_value, None)

    # === Build =================

    def _build(
        self,
        default_value: int,
        initial_string: str,
        horizontal: bool,
        allow_edit_hash: bool,
        allow_edit_name: bool,
        string_label: str,
        hash_label: str,
        width: int,
        parent: int | str,
    ) -> None:
        tag = self._tag

        if horizontal:
            half = abs(width) / 2 if width not in (0, -1) else 100
            with dpg.group(horizontal=True, parent=parent, tag=tag):
                dpg.add_input_text(
                    default_value=str(default_value),
                    decimal=True,
                    readonly=not allow_edit_hash,
                    enabled=allow_edit_hash,
                    width=half,
                    callback=self._on_hash_update,
                    tag=f"{tag}_hash",
                )
                dpg.add_input_text(
                    default_value=initial_string,
                    label=hash_label,
                    readonly=not allow_edit_name,
                    enabled=allow_edit_name,
                    width=half,
                    callback=self._on_string_update,
                    tag=f"{tag}_string",
                )
        else:
            field_w = width
            if width == -1:
                txt_w, _ = estimate_drawn_text_size(
                    max(len(string_label), len(hash_label))
                )
                field_w = 300 - txt_w

            with dpg.group(tag=tag, parent=parent, width=field_w):
                dpg.add_input_text(
                    default_value=initial_string,
                    label=string_label,
                    readonly=not allow_edit_name,
                    enabled=allow_edit_name,
                    width=field_w,
                    callback=self._on_string_update,
                    tag=f"{tag}_string",
                )
                dpg.add_input_text(
                    default_value=str(default_value),
                    decimal=True,
                    label=hash_label,
                    readonly=not allow_edit_hash,
                    enabled=allow_edit_hash,
                    width=field_w,
                    callback=self._on_hash_update,
                    tag=f"{tag}_hash",
                )

    # === DPG callbacks =================

    def _on_hash_update(self, sender: str, new_value: str, cb_user_data: Any) -> None:
        if not new_value:
            return
        label = lookup_name(int(new_value), None)
        dpg.set_value(f"{self._tag}_string", label or "<?>")
        if self._on_hash_changed:
            self._on_hash_changed(self._tag, (int(new_value), label), self._user_data)

    def _on_string_update(self, sender: str, label: str, cb_user_data: Any) -> None:
        h = calc_hash(label)
        dpg.set_value(f"{self._tag}_hash", h)
        if self._on_hash_changed:
            self._on_hash_changed(self._tag, (h, label), self._user_data)

    # === Public accessors =================

    @property
    def hash_value(self) -> int:
        return int(dpg.get_value(f"{self._tag}_hash"))

    @hash_value.setter
    def hash_value(self, value: int) -> None:
        dpg.set_value(f"{self._tag}_hash", str(value))
        self._on_hash_update(None, str(value), None)

    @property
    def string_value(self) -> str:
        return dpg.get_value(f"{self._tag}_string")

    @string_value.setter
    def string_value(self, value: str) -> None:
        dpg.set_value(f"{self._tag}_string", value)
        self._on_string_update(None, value, None)
