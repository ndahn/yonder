from typing import Any
import numpy as np
from dearpygui import dearpygui as dpg

from yonder.audio.audiomath import DB_FLOOR, amp_to_db
from yonder.gui import style
from .dpg_item import DpgItem


class add_bar_equalizer(DpgItem):
    def __init__(
        self,
        bars: int = 16,
        levels: int = 10,
        *,
        gamma: float = 0.3,
        tag: str = None,
        parent: str = 0,
    ):
        super().__init__(tag)

        self._bars = bars
        self._levels = levels
        self._amplitudes = [0.0] * bars

        # gamma controls how much thresholds clump near the top
        self._thresholds = [
            DB_FLOOR - DB_FLOOR * (i / (levels - 1)) ** gamma for i in range(levels)
        ]
        self._gradients = [
            style.RGBA.create_gradient(
                base.mix(style.white, 0.3),
                base.mix(style.black, 0.3),
                levels,
            )
            for base in style.RGBA.create_gradient(style.light_blue, style.pink, bars)
        ]

        self._build(parent)
        dpg.set_frame_callback(dpg.get_frame_count() + 2, self._redraw)

    def destroy(self) -> None:
        self._delete_item(self._t("handler"))

    def set_amplitudes(self, amps: list[float]) -> None:
        if len(amps) != self._bars:
            # Interpolate to match our number of bars
            amps = np.interp(
                list(range(self._bars)),
                list(range(len(amps))),
                amps,
            ).tolist()

        self._amplitudes = amps
        self._redraw()

    def _build(self, parent: str) -> None:
        with dpg.child_window(
            autosize_x=True,
            autosize_y=True,
            border=False,
            tag=self._t("container"),
        ) as container:
            dpg.add_drawlist(width=120, height=30, tag=self.tag, parent=parent)

        # Keep bars aligned to the canvas when it resizes
        with dpg.item_handler_registry(tag=self._t("handler")) as handler:
            dpg.add_item_resize_handler(callback=self._redraw)
        dpg.bind_item_handler_registry(container, handler)

        self._redraw()

    def _redraw(self, sender: str = None, app_data: Any = None) -> None:
        # Save some cpu cycles when nothing is showing
        if not dpg.is_item_visible(self.tag):
            return

        w, h = dpg.get_item_rect_size(self._t("container"))
        if w <= 0 or h <= 0:
            return

        dpg.set_item_width(self.tag, w)
        dpg.set_item_height(self.tag, h)

        gap_x = 4
        gap_y = 1
        box_h = h / self._levels - gap_y
        box_w = min(box_h * 6, w / self._bars - gap_x)
        x = 0

        dpg.delete_item(self.tag, children_only=True)

        for idx, amp in enumerate(self._amplitudes):
            grad = self._gradients[idx]
            db = max(DB_FLOOR, min(0.0, amp_to_db(amp)))

            for level, th in enumerate(self._thresholds):
                if db <= th:
                    # Signal does not reach this level
                    break

                y = h - level * (box_h + gap_y)
                dpg.draw_rectangle(
                    (x, y),
                    (x + box_w, y - box_h),
                    color=(0, 0, 0, 0),
                    fill=grad[level],
                    parent=self.tag,
                )

            x += box_w + gap_x
