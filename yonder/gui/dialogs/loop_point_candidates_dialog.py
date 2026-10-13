from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
from dearpygui import dearpygui as dpg

from yonder.audio.loop_points import LoopPair
from yonder.audio.wavesignal import to_channels
from yonder.gui import style, Icons
from yonder.gui.localization import µ
from yonder.gui.widgets.dpg_item import DpgItem
from yonder.gui.widgets.signal_preview import add_signal_preview


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
    current_loop_points : tuple of (float, float), optional
        The loop already set, shown as a read-only first row to compare the
        proposals against.
    title : str, optional
        Window title.
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
        title: str = None,
        on_apply: Callable[[str, tuple[float, float], Any], None] = None,
        current_loop_points: tuple[float, float] = None,
        tag: str = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self._on_apply = on_apply
        self._user_data = user_data
        self._selected = 0
        self._preview: add_signal_preview = None

        self._candidates: list[_Candidate] = []
        if current_loop_points:
            self._candidates.append(
                _Candidate(
                    µ("Current"),
                    current_loop_points[0],
                    current_loop_points[1],
                    editable=False,
                )
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
            # Nothing found and nothing set - still give the user a row
            self._candidates.append(
                _Candidate(µ("Current"), 0.0, self._preview.duration, editable=False)
            )

        self._build(title or µ("Loop points"))

        signal = to_channels(signal, 1)[:, 0]
        self._preview.set_signal(signal, framerate)
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

    def close(self) -> None:
        self._preview.close()
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
        value = min(value, self._preview.duration)

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
        # Start/stop playback
        if index == self._selected and self._preview.playing:
            self._preview.stop()
        else:
            self._select(index)
            self._preview.play()

        playing = self._preview.playing

        # Swap the preview buttons between play and stop
        for i, candidate in enumerate(self._candidates):
            if not candidate.play_stop:
                continue

            dpg.configure_item(
                candidate.play_stop,
                texture_tag=Icons.stop if playing and i == index else Icons.play,
            )

    def _on_apply_clicked(self) -> None:
        if self._on_apply:
            self._on_apply(self.tag, self.loop_points, self._user_data)

        self.close()

    # === Internals =====================================================

    def _select(self, index: int) -> None:
        for i, candidate in enumerate(self._candidates):
            dpg.set_value(candidate.check, i == index)

        candidate = self._candidates[index]
        self._preview.loop_points = (candidate.start, candidate.end)
        self._selected = index

    @staticmethod
    def _length_label(candidate: _Candidate) -> str:
        return µ("{len:.3f} s").format(len=candidate.length)

    # === Build =========================================================

    def _build(self, title: str) -> None:
        with dpg.window(
            label=title,
            modal=True,
            width=620,
            height=410,
            no_saved_settings=True,
            tag=self.tag,
            on_close=self.close,
        ):
            self._preview = add_signal_preview(no_playback_controls=True)
            self._preview.loop_preview_enabled = True

            dpg.add_spacer(height=4)
            self._build_table()

            dpg.add_separator()
            dpg.add_spacer(height=3)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Apply", "button"), callback=self._on_apply_clicked
                )

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
