from __future__ import annotations
from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder import calc_hash, lookup_name
from .dpg_item import DpgItem


class add_state_value_input(DpgItem):
    def __init__(
        self,
        values: list[int | str],
        callback: Callable[[str, tuple[int, str], Any], None],
        *,
        default_value: int | str = "",
        label: str = None,
        empty_value: int = 0,
        custom_values: dict[str, int] = None,
        raw: bool = False,
        readonly: bool = False,
        width: int = 160,
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

        self._custom_values.setdefault("-", 0)

        with dpg.group(horizontal=True, horizontal_spacing=3, parent=parent, tag=self.tag):
            dpg.add_input_text(
                default_value=self._get_label(default_value),
                width=width,
                readonly=readonly,
                callback=self._on_value_changed,
                tag=self._t("input"),
            )
            dpg.add_combo(
                [self._get_label(v) for v in self._values],
                no_preview=True,
                callback=self._on_value_changed,
                tag=self._t("combo"),
            )

            if label:
                dpg.add_text(label, tag=self._t("label"))

    def _get_label(self, value: int | str) -> str:
        if isinstance(value, str):
            if value.startswith("#"):
                value = int(value[1:])
            elif value.isdigit():
                value = int(value)
            else:
                return value

        for label, val in self._custom_values.items():
            if val == value:
                return label

        if not value:
            return "-"

        if isinstance(value, int):
            return lookup_name(value, f"#{value}")

        return str(value)

    def _on_value_changed(self, sender: str, value: str, cb_user_data: Any) -> None:
        self.value = value

        if self._callback:
            hash = self._value_to_int(value)
            name = lookup_name(hash, f"#{hash}")

            self._callback(self.tag, (hash, name), self._user_data)

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
    def items(self) -> list[str]:
        return list(self._values)

    @items.setter
    def items(self, values: list[str]) -> None:
        self._values = values
        dpg.configure_item(self._t("combo"), items=values)

    @property
    def string_value(self) -> str:
        return dpg.get_value(self._t("input"))

    @property
    def value(self) -> int:
        return self._value_to_int(self.string_value)

    @value.setter
    def value(self, val: int | str) -> None:
        val = self._get_label(val)
        dpg.set_value(self._t("input"), val)
        dpg.set_value(self._t("combo"), val)

    def set_enabled(self, enabled: bool) -> None:
        dpg.configure_item(self._t("input"), enabled=enabled)
        dpg.configure_item(self._t("combo"), enabled=enabled)
