from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
from dearpygui import dearpygui as dpg

from yonder.audio.loop_points import LoopPair
from yonder.audio.wavesignal import minmax_envelope, to_channels
from yonder.gui import style, Icons
from yonder.gui.localization import µ
from yonder.gui.widgets.dpg_item import DpgItem


# eq=False: rows are matched by identity, never by value - two candidates with
# the same bounds are still two separate rows
@dataclass(eq=False)
class _Candidate:
    """One selectable row. All times are in seconds."""

    label: str
    start: float
    end: float
    score: float = None
    editable: bool = True
    # dpg items
    check: int = 0
    start_input: int = 0
    end_input: int = 0
    length_text: int = 0
    play_stop: int = 0

    @property
    def length(self) -> float:
        return max(0.0, self.end - self.start)


class loop_point_candidates_dialog(DpgItem):
    """Pick a loop from the proposals ``find_loops`` came back with.

    Shows the mixed-down timeline with the selected loop region marked, and
    one row per proposal with its score and editable bounds. Picking a row or
    editing its bounds updates the overview, so candidates can be compared
    before committing to one.

    ``find_loops`` reports sample indices; everything this dialog shows,
    returns and passes to its callbacks is in seconds.

    Parameters
    ----------
    candidates : list of LoopPair
        Proposals, best first. Positions are sample indices into ``signal``.
    signal : numpy.ndarray
        The mix the candidates were found in, shaped ``(n_frames,)`` or
        ``(n_frames, n_channels)``. Folded to mono for display.
    framerate : int
        Sample rate of ``signal``. Required to turn the candidates' sample
        indices into the seconds the rest of the arranger speaks.
    on_apply : callable, optional
        Fired as ``on_apply(tag, (loop_start, loop_end), user_data)`` when the
        user confirms. The dialog closes afterwards.
    current : tuple of (float, float), optional
        The loop already set, shown as a read-only first row to compare the
        proposals against.
    title : str, optional
        Window title.
    max_points : int
        Maximum envelope points in the overview plot.
    tag : int or str
        Explicit tag; auto-generated if 0.
    user_data : any
        Passed through to all callbacks.
    """

    # Y range of the overview plot
    _Y_LIMIT = 1.05

    def __init__(
        self,
        candidates: list[LoopPair],
        signal: np.ndarray,
        framerate: int,
        *,
        on_apply: Callable[[str, tuple[float, float], Any], None] = None,
        current: tuple[float, float] = None,
        title: str = None,
        max_points: int = 4000,
        tag: str = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self._signal = to_channels(signal, 1)[:, 0]
        self._framerate = framerate
        self._duration = len(self._signal) / framerate if framerate else 0.0
        self._on_apply = on_apply
        self._user_data = user_data
        self._selected = 0

        # Plot items
        self._region = 0
        self._line_start = 0
        self._line_end = 0

        self._candidates: list[_Candidate] = []
        if current:
            self._candidates.append(
                _Candidate(µ("Current"), current[0], current[1], editable=False)
            )

        for i, pair in enumerate(candidates):
            self._candidates.append(
                _Candidate(
                    µ("#{idx}").format(idx=i + 1),
                    pair.start / framerate,
                    pair.end / framerate,
                    score=pair.score,
                )
            )

        if not self._candidates:
            # Nothing found and nothing set - still give the user a row rather
            # than an empty window
            self._candidates.append(
                _Candidate(µ("Current"), 0.0, self._duration, editable=False)
            )

        self._build(title or µ("Loop points"), max_points)
        self._select(0)

    def destroy(self) -> None:
        self.close()

    # === Public ========================================================

    @property
    def selected_index(self) -> int:
        """Index of the chosen row, counting the ``current`` row if present."""
        return self._selected

    @property
    def loop_points(self) -> tuple[float, float]:
        """The chosen loop as ``(start, end)`` in seconds."""
        candidate = self._candidates[self._selected]
        return candidate.start, candidate.end

    def _loop_preview_signal(
        self, index: int = None, lead: float = 3.0, tail: float = 3.0
    ) -> np.ndarray:
        """Audio of a loop's seam: the run-up to ``end`` spliced onto ``start``.

        This is what the transition will actually sound like, and the only
        part worth auditioning when judging a loop point.

        Parameters
        ----------
        index : int, optional
            Row to take the bounds from. Defaults to the selected one.
        lead : float
            Seconds of audio before the loop end.
        tail : float
            Seconds of audio after the loop start.

        Returns
        -------
        numpy.ndarray
            Mono samples, ``lead + tail`` seconds long at most.
        """
        if index is None:
            index = self._selected

        candidate = self._candidates[index]

        def at(pos: float) -> int:
            return max(0, min(len(self._signal), round(pos * self._framerate)))

        before = self._signal[at(candidate.end - lead) : at(candidate.end)]
        after = self._signal[at(candidate.start) : at(candidate.start + tail)]
        return np.concatenate([before, after])

    def close(self) -> None:
        if dpg.does_item_exist(self.tag):
            dpg.delete_item(self.tag)

    # === DPG callbacks =================================================

    def _on_row_selected(self, sender: str, value: bool, index: int) -> None:
        if not value:
            # The checkboxes are a radio group - there is always one choice
            dpg.set_value(sender, True)
            return

        self._select(index)

    def _on_bound_changed(
        self, sender: str, value: float, user_data: tuple[int, str]
    ) -> None:
        index, which = user_data
        candidate = self._candidates[index]

        value = max(0.0, value)
        if self._duration:
            value = min(value, self._duration)

        # Keep the bounds ordered, otherwise the region and the length go
        # negative and the loop means nothing
        if which == "start":
            candidate.start = min(value, candidate.end)
        else:
            candidate.end = max(value, candidate.start)

        dpg.set_value(candidate.start_input, candidate.start)
        dpg.set_value(candidate.end_input, candidate.end)
        dpg.set_value(candidate.length_text, self._length_label(candidate))

        # Editing a row is a clear statement about which one is wanted
        self._select(index)

    def _on_preview_clicked(self, sender: str, app_data: Any, index: int) -> None:
        # TODO if currently playing index == index then stop playing, otherwise switch to new track
        playing = False
        candidate = self._candidates[index]

        # Swap the preview buttons between play and stop
        for i, candidate in enumerate(self._candidates):
            if not candidate.play_stop:
                continue

            dpg.configure_item(
                candidate.play_stop,
                texture_tag=Icons.stop if playing and i == index else Icons.play,
            )

        # TODO start/stop playback

    def _on_apply_clicked(self) -> None:
        loop = self.loop_points
        if self._on_apply:
            self._on_apply(self.tag, loop, self._user_data)

        self.close()

    # === Internals =====================================================

    def _select(self, index: int) -> None:
        self._selected = index
        for i, candidate in enumerate(self._candidates):
            dpg.set_value(candidate.check, i == index)

        self._sync_region()

    def _sync_region(self) -> None:
        """Move the overview markers onto the selected loop."""
        start, end = self.loop_points
        dpg.set_value(self._region, (start, -self._Y_LIMIT, end, self._Y_LIMIT))
        dpg.set_value(self._line_start, start)
        dpg.set_value(self._line_end, end)

    @staticmethod
    def _length_label(candidate: _Candidate) -> str:
        return µ("{len:.3f} s").format(len=candidate.length)

    # === Build =========================================================

    def _build(self, title: str, max_points: int) -> None:
        with dpg.window(
            label=title,
            modal=True,
            width=620,
            height=410,
            no_saved_settings=True,
            tag=self.tag,
            on_close=self.close,
        ):
            self._build_overview(max_points)
            dpg.add_spacer(height=4)
            self._build_table()
            dpg.add_separator()
            dpg.add_spacer(height=3)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Apply", "button"), callback=self._on_apply_clicked
                )

    def _build_overview(self, max_points: int) -> None:
        with dpg.plot(
            height=130,
            width=-1,
            no_title=True,
            no_menus=True,
            no_mouse_pos=True,
            no_box_select=True,
        ) as plot:
            xaxis = dpg.add_plot_axis(dpg.mvXAxis, no_label=True, no_highlight=True)
            yaxis = dpg.add_plot_axis(
                dpg.mvYAxis,
                no_label=True,
                no_highlight=True,
                no_tick_labels=True,
                no_tick_marks=True,
            )

            if len(self._signal):
                time = np.linspace(0, self._duration, num=len(self._signal))
                t_env, y_env = minmax_envelope(self._signal, time, max_points // 2)
                series = dpg.add_line_series(
                    t_env.tolist(), y_env.tolist(), shaded=True, parent=xaxis
                )
                dpg.bind_item_theme(series, style.themes.make_series_theme(style.blue))

            # Read-only: the numeric fields in the table are the editor
            self._region = dpg.add_drag_rect(
                color=style.green.but(a=60),
                no_inputs=True,
                no_cursor=True,
                no_fit=True,
            )
            self._line_start = dpg.add_drag_line(
                label=µ("loop_start", "marker"),
                color=style.green,
                no_inputs=True,
                no_cursor=True,
                no_fit=True,
            )
            self._line_end = dpg.add_drag_line(
                label=µ("loop_end", "marker"),
                color=style.green,
                no_inputs=True,
                no_cursor=True,
                no_fit=True,
            )

        dpg.bind_item_theme(plot, style.themes.player_plot)
        dpg.set_axis_limits(yaxis, -self._Y_LIMIT, self._Y_LIMIT)

    def _build_table(self) -> None:
        with dpg.table(
            header_row=True,
            policy=dpg.mvTable_SizingStretchProp,
            scrollY=True,
            height=-40,
        ):
            # Select
            dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=26)
            dpg.add_table_column(
                label=µ("Loop", "table"), width_fixed=True, init_width_or_weight=50
            )
            dpg.add_table_column(
                label=µ("Score", "table"), width_fixed=True, init_width_or_weight=55
            )
            dpg.add_table_column(
                label=µ("Start (s)", "table"),
                width_stretch=True,
                init_width_or_weight=75,
            )
            dpg.add_table_column(
                label=µ("End (s)", "table"),
                width_stretch=True,
                init_width_or_weight=75,
            )
            dpg.add_table_column(
                label=µ("Length", "table"), width_fixed=True, init_width_or_weight=55
            )
            # Playback button
            dpg.add_table_column(label="", width_fixed=True, init_width_or_weight=26)

            for index, candidate in enumerate(self._candidates):
                self._build_row(index, candidate)

    def _build_row(self, index: int, candidate: _Candidate) -> None:
        with dpg.table_row():
            candidate.check = dpg.add_checkbox(
                callback=self._on_row_selected, user_data=index
            )
            dpg.add_text(candidate.label)
            dpg.add_text(
                "-" if candidate.score is None else f"{candidate.score:.3f}",
                color=style.light_grey,
            )

            for which, value in (("start", candidate.start), ("end", candidate.end)):
                item = dpg.add_input_float(
                    default_value=value,
                    width=-1,
                    step=0.01,
                    format="%.3f",
                    enabled=candidate.editable,
                    readonly=not candidate.editable,
                    callback=self._on_bound_changed,
                    user_data=(index, which),
                )
                setattr(candidate, f"{which}_input", item)

            candidate.length_text = dpg.add_text(self._length_label(candidate))
            candidate.play_stop = dpg.add_image_button(
                Icons.play,
                width=18,
                height=18,
                callback=self._on_preview_clicked,
                user_data=index,
            )
