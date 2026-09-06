from __future__ import annotations
from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder import calc_hash, lookup_name
from .dpg_item import DpgItem


def _get_label(value: int | str) -> str:
    if isinstance(value, str):
        if value.startswith("#"):
            value = int(value[1:])
        elif value.isdigit():
            value = int(value)
        else:
            return value

    if isinstance(value, int):
        return lookup_name(value, f"#{value}")

    return str(value)


class add_state_value_input(DpgItem):
    def __init__(
        self,
        state: str,
        values: list[int | str],
        callback: Callable[[str, int, Any], None],
        *,
        default_value: int | str = "",
        empty_value: int = 0,
        custom_values: dict[str, int] = None,
        raw: bool = False,
        readonly: bool = True,
        textbox_width: int = 160,
        show: bool = True,
        parent: str = 0,
        tag: str = 0,
        user_data: Any = None,
    ) -> str:
        super().__init__(tag)

        self._values = values
        self._callback = callback
        self._user_data = user_data
        self._empty_value = empty_value
        self._custom_values = custom_values or {}
        self._raw = raw

        with dpg.group(horizontal=True, show=show, parent=parent, tag=self.tag):
            dpg.add_input_text(
                default_value=_get_label(default_value),
                width=textbox_width,
                readonly=readonly,
                enabled=not readonly,
                callback=self._on_value_changed,
                tag=self._t("input"),
            )
            dpg.add_combo(
                [_get_label(v) for v in self._values],
                no_preview=True,
                callback=self._on_value_changed,
                tag=self._t("combo"),
            )

            if state:
                dpg.add_text(state, tag=self._t("label"))

    def _on_value_changed(self, sender: str, value: str | int, cb_user_data: Any) -> None:
        self.value = value

        if self._callback:
            ret = self.value
            if not self._raw:
                ret = lookup_name(ret, f"#{ret}")

            self._callback(self.tag, ret, self._user_data)

    def _value_to_int(self, value: int | str) -> int:
        if value in self._custom_values:
            return self._custom_values[value]
        elif value:
            if isinstance(value, str) and value.startswith("#"):
                return int(value[1:])
            else:
                return calc_hash(value) 
        
        return self._empty_value

    @property
    def string_value(self) -> str:
        return dpg.get_value(self._t("input"))

    @property
    def value(self) -> int:
        return self._value_to_int(self.string_value)

    @value.setter
    def value(self, val: int | str) -> None:
        val = _get_label(val)
        dpg.set_value(self._t("input"), val)
        dpg.set_value(self._t("combo"), val)
