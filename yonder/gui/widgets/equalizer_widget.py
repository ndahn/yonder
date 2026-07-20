from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder.gui import style
from .dpg_item import DpgItem

from yonder.audio import EQPresets


class add_equalizer(DpgItem):
    def __init__(
        self,
        on_values_changed: Callable[[str, list[float], Any], None],
        preset: list[float] = None,
        *,
        tag: str = 0,
        parent: str = 0,
        user_data: Any = None,
    ):
        super().__init__(tag)

        if preset and len(preset) != 10:
            raise ValueError("Preset must be exactly 10 values")

        self._values = preset or [0.0] * 10
        self._user_data = user_data
        self._on_values_changed = on_values_changed
        self._create_content(parent)

    def _on_preset_selected(self, sender: str, preset: str, cb_user_data: Any) -> None:
        self._values = list(getattr(EQPresets, preset.lower()))

        for idx, val in enumerate(self._values):
            dpg.set_value(self._t(f"boost_{idx}"), val)

        if self._on_values_changed:
            self._on_values_changed(self._tag, self._values, self._user_data)

    def _on_boost_changed(self, sender: str, boost: float, idx: int) -> None:
        self._values[idx] = boost
        dpg.set_value(self._t("preset"), "")

        if self._on_values_changed:
            self._on_values_changed(self._tag, self._values, self._user_data)

    def _create_content(self, parent: str) -> None:
        with dpg.group(parent=parent):
            presets = [key.capitalize() for key in vars(EQPresets) if not key.startswith("_")]
            dpg.add_combo(
                presets,
                default_value=presets[0],
                callback=self._on_preset_selected,
                width=255,
                tag=self._t("preset"),
            )

            dpg.add_spacer(height=1)
            dpg.add_separator()
            dpg.add_spacer(height=1)

            grad = style.RGBA.create_gradient(
                style.blue.but(a=162), style.pink.but(a=162), 10
            )

            with dpg.group(horizontal=True):
                for idx in range(10):
                    with dpg.group():
                        dpg.add_slider_double(
                            vertical=True,
                            width=18,
                            min_value=-12.0,
                            max_value=12.0,
                            clamped=True,
                            callback=self._on_boost_changed,
                            user_data=idx,
                            format="%.1f",
                            tag=self._t(f"boost_{idx}"),
                        )

                        hz = int(2 ** (idx + 5))
                        label = str(hz) if hz < 1000 else f"{hz // 1000}k"
                        dpg.add_text(label)

                        color = grad[idx]
                        handle_color = style.white.mix(color, 0.3)
                        theme = style.themes.make_slider_theme(color, handle_color)
                        dpg.bind_item_theme(self._t(f"boost_{idx}"), theme)
