"""Separate per-row plots with manually linked x axes.

Feasibility demo for giving every arranger track a header with real widgets:
each row is a horizontal group of a header and its own ``dpg.plot``, which
``subplots`` does not allow. DPG only links axes inside ``subplots``, so the
x axes are synced by hand here:

- The hovered plot is the master, its x axis is left free.
- Every other x axis is locked to the master's limits on every sync tick.

``get_axis_limits`` reports what was rendered last frame, so the followers
trail the master by at least one frame. The readout shows by how much, in
pixels, and the sync mode can be switched at runtime to compare:

- Main loop: synced right before every frame, on the main thread. The best
  case, but needs a hand-rolled render loop instead of ``start_dearpygui``.
- call_in_frames: a frame task that re-registers itself, which is what the
  app could do as is. Frame callbacks run on dpg's callback thread, so this
  adds whatever latency that thread has on top.

Middle drag pans and the wheel zooms, like in the arranger. Use a fast pan or
zoom over different rows to see the followers shear.

``python linked_plots_demo.py [n_tracks]``
"""

from __future__ import annotations
import sys
import time
from dataclasses import dataclass

import numpy as np
from dearpygui import dearpygui as dpg

from yonder.gui.frame_tasks import call_in_frames


HEADER_WIDTH = 190
ROW_HEIGHT = 90
STRIP_HEIGHT = 34
Y_LIMIT = 1.05

MODES = ("Off", "Main loop (before each frame)", "call_in_frames (callback thread)")


@dataclass(eq=False)
class _Lane:
    plot: int
    xaxis: int
    yaxis: int
    cursor: int  # mirrors the hovered time, to compare rows by eye


class LinkedPlotsDemo:
    def __init__(self, n_tracks: int) -> None:
        self.lanes: list[_Lane] = []
        self.master: _Lane | None = None
        self.mode = MODES[1]
        self.duration = 0.0
        # Fit has to land before the master may be unlocked, see fit()
        self._unlock_at_frame = 0
        self._peak_px = 0.0
        self._peak_time = 0.0
        self._ticks = 0

        with dpg.window(tag="demo"):
            dpg.add_text(
                "Middle drag pans, wheel zooms, double click fits. "
                "Pan fast and watch the other rows.",
                color=(150, 150, 150),
            )
            self._build_strip()
            for i in range(n_tracks):
                self._build_track(i, is_last=i == n_tracks - 1)

            dpg.add_button(label="Fit", callback=self.fit)

        self.fit()

    # === Build =========================================================

    def _add_axes(self, *, tick_labels: bool) -> tuple[int, int]:
        xaxis = dpg.add_plot_axis(
            dpg.mvXAxis,
            no_label=True,
            no_highlight=True,
            no_tick_labels=not tick_labels,
            no_tick_marks=not tick_labels,
            no_initial_fit=True,
        )
        yaxis = dpg.add_plot_axis(
            dpg.mvYAxis,
            no_label=True,
            no_highlight=True,
            no_tick_labels=True,
            no_tick_marks=True,
        )
        return xaxis, yaxis

    def _add_cursor(self) -> int:
        return dpg.add_drag_line(
            color=(255, 255, 255, 90),
            show_label=False,
            no_inputs=True,
            no_cursor=True,
            no_fit=True,
            show=False,
        )

    def _build_strip(self) -> None:
        with dpg.group(horizontal=True):
            # The header column's top cell holds the global controls
            with dpg.child_window(width=HEADER_WIDTH, height=STRIP_HEIGHT * 3):
                dpg.add_combo(
                    MODES,
                    default_value=self.mode,
                    width=-1,
                    callback=self._on_mode_changed,
                )
                dpg.add_text("", tag="desync_text")
                dpg.add_text("", tag="peak_text")

            with dpg.plot(
                height=STRIP_HEIGHT * 3,
                width=-1,
                no_title=True,
                no_menus=True,
                no_mouse_pos=True,
                no_box_select=True,
                pan_button=dpg.mvMouseButton_Middle,
            ) as plot:
                xaxis, yaxis = self._add_axes(tick_labels=False)
                dpg.add_drag_line(
                    label="playhead",
                    color=(120, 190, 255),
                    default_value=1.0,
                    no_fit=True,
                )
                cursor = self._add_cursor()

        self.lanes.append(_Lane(plot, xaxis, yaxis, cursor))

    def _build_track(self, idx: int, *, is_last: bool) -> None:
        rng = np.random.default_rng(idx)
        length = 2.0 + 3.0 * rng.random()
        offset = idx * 1.5
        self.duration = max(self.duration, offset + length)

        t = np.linspace(0.0, length, 4000)
        env = np.sin(np.pi * t / length) ** 2
        y = env * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * (1 + idx) * t)))

        with dpg.group(horizontal=True):
            with dpg.child_window(width=HEADER_WIDTH, height=ROW_HEIGHT):
                dpg.add_text(f"Track {idx}", color=(120, 190, 255))
                dpg.add_slider_float(
                    label="Vol", default_value=0.0, min_value=-96, max_value=12,
                    format="%.1f dB", width=110,
                )
                dpg.add_slider_float(
                    label="Pitch", default_value=0.0, min_value=-2400,
                    max_value=2400, format="%.0f c", width=110,
                )
                with dpg.group(horizontal=True):
                    dpg.add_checkbox(label="M")
                    dpg.add_checkbox(label="S")

            with dpg.plot(
                height=ROW_HEIGHT,
                width=-1,
                no_title=True,
                no_menus=True,
                no_mouse_pos=True,
                no_box_select=True,
                pan_button=dpg.mvMouseButton_Middle,
            ) as plot:
                xaxis, yaxis = self._add_axes(tick_labels=is_last)
                dpg.add_line_series(
                    (t + offset).tolist(), y.tolist(), shaded=True, parent=xaxis
                )
                dpg.add_line_series(
                    (t + offset).tolist(), (-y).tolist(), shaded=True, parent=xaxis
                )
                cursor = self._add_cursor()

        self.lanes.append(_Lane(plot, xaxis, yaxis, cursor))

    # === Sync ==========================================================

    def fit(self) -> None:
        padding = 0.02 * self.duration
        for lane in self.lanes:
            dpg.set_axis_limits(lane.xaxis, -padding, self.duration + padding)
            dpg.set_axis_limits(lane.yaxis, -Y_LIMIT, Y_LIMIT)

        # Unlocking right away would cancel the limits before they rendered,
        # so the master is only picked again once they landed
        self.master = None
        self._unlock_at_frame = dpg.get_frame_count() + 2

    def _hovered_lane(self) -> _Lane | None:
        for lane in self.lanes:
            if dpg.is_item_hovered(lane.plot):
                return lane
        return None

    def sync(self) -> None:
        """Make the hovered plot the master and pull the others to it."""
        self._ticks += 1
        hovered = self._hovered_lane()

        if self.master is None:
            if dpg.get_frame_count() < self._unlock_at_frame:
                return
            self.master = hovered or self.lanes[0]
            dpg.set_axis_limits_auto(self.master.xaxis)
        elif hovered and hovered is not self.master:
            # Already sitting at the old master's range, so it carries on
            # from there. The old master is locked like any follower below
            self.master = hovered
            dpg.set_axis_limits_auto(hovered.xaxis)

        lo, hi = dpg.get_axis_limits(self.master.xaxis)
        mouse = dpg.get_plot_mouse_pos()[0] if hovered else None

        for lane in self.lanes:
            if lane is not self.master:
                dpg.set_axis_limits(lane.xaxis, lo, hi)

            if mouse is None:
                dpg.configure_item(lane.cursor, show=False)
            else:
                dpg.configure_item(lane.cursor, show=True)
                dpg.set_value(lane.cursor, mouse)

    def _frame_task(self) -> None:
        if self.mode != MODES[2]:
            return  # switched away, let the loop die

        self.sync()
        call_in_frames(self._frame_task, 1)

    def _on_mode_changed(self, sender: int, mode: str) -> None:
        self.mode = mode
        if mode == MODES[0]:
            # Free every axis so the rows can be seen drifting apart
            for lane in self.lanes:
                dpg.set_axis_limits_auto(lane.xaxis)
        elif mode == MODES[2]:
            call_in_frames(self._frame_task, 1)

    # === Measurement ===================================================

    def measure(self) -> None:
        """Worst follower misalignment in the last rendered frame, in pixels."""
        if self.master is None:
            return

        m_lo, m_hi = dpg.get_axis_limits(self.master.xaxis)
        span = m_hi - m_lo
        width = dpg.get_item_rect_size(self.master.plot)[0]
        if span <= 0 or width <= 0:
            return

        worst = 0.0
        for lane in self.lanes:
            if lane is self.master:
                continue
            f_lo, f_hi = dpg.get_axis_limits(lane.xaxis)
            worst = max(worst, abs(f_lo - m_lo), abs(f_hi - m_hi))

        px = worst / span * width
        now = time.perf_counter()
        if px >= self._peak_px or now - self._peak_time > 1.5:
            self._peak_px = px
            self._peak_time = now

        dpg.set_value(
            "desync_text", f"desync {px:5.1f} px  {dpg.get_frame_rate():.0f} fps"
        )
        dpg.set_value("peak_text", f"peak   {self._peak_px:5.1f} px")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n_tracks = int(args[0]) if args else 4
    # Quit on its own after this many frames, for smoke tests
    max_frames = next(
        (int(a.split("=", 1)[1]) for a in sys.argv[1:] if a.startswith("--frames=")),
        0,
    )

    dpg.create_context()
    demo = LinkedPlotsDemo(n_tracks)

    dpg.create_viewport(title="Linked plots demo", width=1100, height=720)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("demo", True)

    # Hand-rolled instead of start_dearpygui so the main loop mode can sync
    # right before every frame
    while dpg.is_dearpygui_running():
        if demo.mode == MODES[1]:
            demo.sync()
        demo.measure()
        dpg.render_dearpygui_frame()

        if max_frames and dpg.get_frame_count() >= max_frames:
            break

    print(f"frames={dpg.get_frame_count()} sync_ticks={demo._ticks}")
    dpg.destroy_context()


if __name__ == "__main__":
    main()
