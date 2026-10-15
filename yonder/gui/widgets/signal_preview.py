from __future__ import annotations
from typing import Any, Callable
import numpy as np
from dearpygui import dearpygui as dpg

from yonder import lookup_name
from yonder.audio.wavesignal import minmax_envelope, to_channels
from yonder.audio.simple_player import SimplePlayer
from yonder.gui import style, Icons
from yonder.gui.localization import µ
from yonder.gui.widgets.dpg_item import DpgItem


class add_signal_preview(DpgItem):
    # Y range of the plot
    _Y_LIMIT = 1.05

    def __init__(
        self,
        signal: np.ndarray = None,
        framerate: int = None,
        *,
        no_playback_controls: bool = False,
        loop_points: tuple[float, float] = None,
        user_markers: dict[int, float] = None,
        on_marker_changed: Callable[[str, tuple[int, float], Any], None] = None,
        max_points: int = 4000,
        tag: str = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self._signal = None
        self._framerate = 0
        self._duration = 0.0
        self._loop_points = loop_points or (0, 0)
        self._user_markers = user_markers or {}
        self._max_points = max_points
        self._user_data = user_data

        self._player: SimplePlayer = None
        self._playing = False
        self.loop_preview_enabled = False

        self._build(no_playback_controls)

        if signal is not None and framerate > 0:
            self.set_signal(signal, framerate)
            self._sync_region()

    def destroy(self) -> None:
        self.close()

    # === Public ========================================================

    @property
    def signal(self) -> np.ndarray:
        return self._signal

    def set_signal(self, sig: np.ndarray, framerate: int) -> None:
        dpg.delete_item(self._t("xaxis"), slot=1, children_only=True)

        self._signal = to_channels(sig, 1)[:, 0]
        self._framerate = framerate
        self._duration = len(self._signal) / framerate

        time = np.linspace(0, self._duration, num=len(self._signal))
        t_env, y_env = minmax_envelope(self._signal, time, self._max_points // 2)
        series = dpg.add_line_series(
            t_env.tolist(), y_env.tolist(), shaded=True, parent=self._t("xaxis")
        )
        dpg.bind_item_theme(series, style.themes.make_series_theme(style.blue))

    @property
    def framerate(self) -> int:
        return self._framerate

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def playback_duration(self) -> float:
        return max(0.0, self._loop_points[1] - self._loop_points[0])

    @property
    def loop_points(self) -> tuple[float, float]:
        """The chosen loop as ``(start, end)`` in seconds."""
        return self._loop_points

    @loop_points.setter
    def loop_points(self, points: tuple[float, float]) -> None:
        self._loop_points = points
        self._sync_region()

    @property
    def user_markers(self) -> dict[int, float]:
        """Return all user marker positions ``{id: pos}`` in seconds."""
        return dict(self._user_markers)

    @user_markers.setter
    def user_markers(self, markers: dict[int, float]) -> None:        
        dpg.delete_item(self._t("user_markers_container"), children_only=True)

        for mid in self._user_markers:
            if dpg.does_item_exist(self._t(f"user_marker_{mid}")):
                dpg.delete_item(self._t(f"user_marker_{mid}"))

        self._user_markers = markers

        for mid, pos in self._user_markers.items():
            marker_label = lookup_name(mid, f"#{mid}")
            dpg.add_input_float(
                label=marker_label,
                default_value=pos,
                width=130,
                callback=self._on_user_marker_changed,
                user_data=mid,
                tag=self._t(f"marker_{mid}_value"),
            )
            # TODO plot markers

    @property
    def player(self) -> SimplePlayer:
        if not self._player:
            self._player = SimplePlayer()

        return self._player

    @property
    def playing(self) -> bool:
        return self._playing

    def play(self) -> None:
        if self.playing:
            return

        player = self.player
        player.play_signal(self._signal, self._framerate, loop=True)
        # In case seek was called before
        player.seek(dpg.get_value(self._t("playback_pos")))

        if dpg.does_item_exist(self._t("play_stop")):
            dpg.configure_item(self._t("play_stop"), texture_tag=Icons.stop)

        self._update_playback_pos()

    def stop(self) -> None:
        if not self._player:
            return

        self._player.stop()

        if dpg.does_item_exist(self._t("play_stop")):
            dpg.configure_item(self._t("play_stop"), texture_tag=Icons.play)

    def seek(self, pos: float, relative: bool = False) -> None:
        if self._player:
            self._player.seek(pos, relative)

        if relative:
            pos *= self._duration

        dpg.set_value(self._t("playback_pos"), pos)

    def close(self) -> None:
        if self._player:
            self._player.close()

        if dpg.does_item_exist(self.tag):
            dpg.delete_item(self.tag)

    # === DPG callbacks =================================================

    def _on_play_stop_clicked(self) -> None:
        if self.playing:
            self.stop()
        else:
            self.play()

    def _update_playback_pos(self) -> None:
        if self._player.playing:
            loop_start, loop_end = self.loop_points
            pos = self._player.pos

            if pos < loop_start:
                self._player.seek(loop_start)
            elif (
                self.loop_preview_enabled
                and pos >= min(loop_start + 2.0, self._duration)
                and pos < loop_end - 2.0
            ):
                self._player.seek(max((0, loop_start, loop_end - 2.0)))
            elif pos >= loop_end:
                self._player.seek(loop_start)

            dpg.set_frame_callback(dpg.get_frame_count() + 2, self._update_playback_pos)

        dpg.set_value(self._t("playback_pos"), self._player.pos)

    # === Internals =====================================================

    def _sync_region(self) -> None:
        """Move the overview markers onto the selected loop."""
        start, end = self.loop_points
        dpg.set_value(
            self._t("playback_region"), (start, -self._Y_LIMIT, end, self._Y_LIMIT)
        )
        dpg.set_value(self._t("loop_start"), start)
        dpg.set_value(self._t("loop_end"), end)

        if dpg.does_item_exist(self._t("playback_pos")):
            dpg.set_value(self._t("playback_pos"), start)

    def _on_bound_changed(self, sender: str, value: float, which: str) -> None:
        value = max(0.0, value)
        if self._duration:
            value = min(value, self._duration)

        if which == "start":
            end = self._loop_points[1]
            start = min(value, end)
        else:
            start = self._loop_points[0]
            end = max(value, start)

        self._loop_points = (start, end)
        dpg.set_value(self._t("start_input"), start)
        dpg.set_value(self._t("end_input"), end)
        dpg.set_value(self._t("length_text"), self._length_label())

        self._sync_region()

    def _length_label(self) -> str:
        return µ("{len:.3f} s").format(len=self.playback_duration)

    def _build(self, no_playback_controls: bool) -> None:
        with dpg.child_window(
            autosize_x=True,
            auto_resize_y=True,
            tag=self.tag,
        ):
            self._build_plot()
            if not no_playback_controls:
                dpg.add_spacer(height=4)
                self._build_footer()

    def _build_plot(self) -> None:
        with dpg.plot(
            width=-1,
            height=130,
            no_title=True,
            no_menus=True,
            no_mouse_pos=True,
            no_box_select=True,
            tag=self._t("plot"),
        ) as plot:
            dpg.add_plot_axis(
                dpg.mvXAxis,
                no_label=True,
                no_highlight=True,
                tag=self._t("xaxis"),
            )
            yaxis = dpg.add_plot_axis(
                dpg.mvYAxis,
                no_label=True,
                no_highlight=True,
                no_tick_labels=True,
                no_tick_marks=True,
            )

            # Read-only: the numeric fields in the table are the editor
            dpg.add_drag_rect(
                color=style.green.but(a=60),
                no_inputs=True,
                no_cursor=True,
                no_fit=True,
                tag=self._t("playback_region"),
            )
            dpg.add_drag_line(
                label=µ("loop_start", "marker"),
                color=style.green,
                no_inputs=True,
                no_cursor=True,
                no_fit=True,
                tag=self._t("loop_start"),
            )
            dpg.add_drag_line(
                label=µ("loop_end", "marker"),
                color=style.green,
                no_inputs=True,
                no_cursor=True,
                no_fit=True,
                tag=self._t("loop_end"),
            )
            dpg.add_drag_line(
                label=µ("pos", "marker"),
                color=style.light_blue,
                no_inputs=True,
                no_cursor=True,
                no_fit=True,
                tag=self._t("playback_pos"),
            )

        dpg.bind_item_theme(plot, style.themes.player_plot)
        dpg.set_axis_limits(yaxis, -self._Y_LIMIT, self._Y_LIMIT)

    def _build_footer(self) -> None:
        with dpg.group(horizontal=True):
            dpg.add_image_button(
                Icons.play,
                width=18,
                height=18,
                callback=self._on_play_stop_clicked,
                tag=self._t("play_stop"),
            )

            for which, value in zip(("start", "end"), self._loop_points):
                dpg.add_input_float(
                    default_value=value,
                    width=-1,
                    step=0.01,
                    format="%.3f",
                    callback=self._on_bound_changed,
                    user_data=(which),
                    tag=self._t(f"{which}_input"),
                )

            dpg.add_text(self._length_label(), tag=self._t("length_text"))

        # TODO use the marker editor widget instead
        with dpg.window(
            popup=True,
            no_move=True,
            no_title_bar=True,
            no_resize=True,
            tag=self._t("markers_popup"),
            show=False,
        ):
            dpg.add_input_float(
                label=µ("loop_start", "marker"),
                default_value=self._loop_start,
                width=130,
                callback=self._set_loop_marker_pos,
                user_data="loop_start",
                tag=self._t("loop_start_value"),
            )
            dpg.add_input_float(
                label=µ("loop_end", "marker"),
                default_value=self._loop_end,
                width=130,
                callback=self._set_loop_marker_pos,
                user_data="loop_end",
                tag=self._t("loop_end_value"),
            )

            dpg.add_separator()
            dpg.add_group(tag=self._t("user_markers_container"))

