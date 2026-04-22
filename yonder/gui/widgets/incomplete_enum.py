from typing import TypeVar, Type, Callable, Any
from enum import IntEnum
from dearpygui import dearpygui as dpg

from .dpg_item import DpgItem


_T = TypeVar("_T", bound=IntEnum)


class add_incomplete_int_enum(DpgItem):
    def __init__(
        self,
        enum: Type[_T],
        default_value: _T,
        unknown_label: str,
        on_value_changed: Callable[[str, int, Any], None],
        *,
        width: int = 280,
        label: str = None,
        sort: bool = True,
        tag: str = 0,
        user_data: Any = None,
    ) -> str:
        super().__init__(tag)

        self._enum_type = enum
        self._default_value = default_value
        self._unknown_label = unknown_label
        self._on_value_changed = on_value_changed
        self._choices = [e.name for e in enum]
        self._user_data = user_data

        if sort:
            self._choices.sort()

        self._build(width, label)

    def _build(self, width: int, label: str):
        with dpg.group(horizontal=True, tag=self.tag):
            dpg.add_combo(
                self._choices,
                default_value=self._default_value.name,
                callback=self._on_combo_changed,
                tag=self._t("combo"),
                width=width / 2,
            )
            dpg.add_input_int(
                default_value=self._default_value.value,
                label=label,
                min_value=min(e.value for e in self._enum_type),
                max_value=max(e.value for e in self._enum_type),
                callback=self._on_int_changed,
                tag=self._t("value"),
                width=width / 2,
            )

    def _on_combo_changed(self, sender: str, choice: str, user_data: Any) -> None:
        val = self._enum_type[choice]
        dpg.set_value(self._t("value"), val.value)
        self._on_value_changed(self.tag, val.value, self._user_data)

    def _on_int_changed(self, sender: str, value: int, user_data: Any) -> None:
        try:
            choice = self._enum_type(value).name
        except KeyError:
            choice = self._unknown_label

        dpg.set_value(self._t("combo"), choice)
        self._on_value_changed(self.tag, value, self._user_data)
