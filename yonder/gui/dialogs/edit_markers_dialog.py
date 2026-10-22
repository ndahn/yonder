from typing import Any, Callable
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder.hash import Hash
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.widgets import DpgItem, add_track_arranger, AudioTrack


class edit_markers_dialog(DpgItem):
    """A dialog wrapping ``add_audio_visualizer`` for editing a sound's markers.

    Loop points, trims and user markers are optional: passing None for one of
    them hides it. Like Wwise segment markers, loop points and user markers are
    absolute positions and are not affected by the trims. A loop end <= 0 is
    measured from the end of the sound.

    For a music track of a segment, pass the track's ``play_at`` as
    ``track_offset`` so the sound sits where it plays within the segment.

    When ``accept_on_okay=True`` changes are only forwarded to the callbacks
    once the user confirms. Otherwise each change fires the callbacks
    immediately and no Apply button is shown.

    Parameters
    ----------
    sound : Path
        Audio file to edit the markers of (not changeable inside the dialog).
    title : str
        Window title bar label.
    accept_on_okay : bool
        Buffer changes until Apply is clicked.
    loop_points : tuple of (float, float), optional
        Initial ``(start, end)`` of the loop. None hides the loop markers.
    on_loop_changed : callable, optional
        Fired as ``on_loop_changed(tag, (start, end), user_data)``.
    trims : tuple of (float, float), optional
        Initial ``(begin_trim, end_trim)``, end trim <= 0. None hides the trims.
    on_trims_changed : callable, optional
        Fired as ``on_trims_changed(tag, (begin, end), user_data)``.
    user_markers : dict, optional
        Initial user marker positions keyed by ID or name. None hides them.
    on_user_markers_changed : callable, optional
        Fired as ``on_user_markers_changed(tag, {id: pos}, user_data)``.
    track_offset : float
        Where the untrimmed sound starts on the timeline (Wwise's ``play_at``).
    balance_trims : bool
        Move the sound along with its begin trim, so that its audible part
        keeps starting at the same position. Mirrors balancing the begin trim
        with a negative ``play_at``.
    markers_in_ms : bool
        Interpret and report all positions in milliseconds.
    tag : int or str, optional
        Explicit tag; auto-generated if None.
    user_data : any
        Passed through to all callbacks.
    """

    def __init__(
        self,
        sound: Path,
        *,
        title: str = "Edit Markers",
        accept_on_okay: bool = False,
        loop_points: tuple[float, float] = None,
        on_loop_changed: Callable[[str, tuple[float, float], Any], None] = None,
        trims: tuple[float, float] = None,
        on_trims_changed: Callable[[str, tuple[float, float], Any], None] = None,
        user_markers: dict[Hash, float] = None,
        on_user_markers_changed: Callable[[str, dict[int, float], Any], None] = None,
        track_offset: float = 0.0,
        balance_trims: bool = False,
        markers_in_ms: bool = True,
        tag: str = None,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self._accept_on_okay = accept_on_okay
        self._has_loop = loop_points is not None
        self._has_trims = trims is not None
        self._has_user_markers = user_markers is not None
        self._on_loop_changed = on_loop_changed
        self._on_trims_changed = on_trims_changed
        self._on_user_markers_changed = on_user_markers_changed
        self._markers_in_ms = markers_in_ms
        self._user_data = user_data
        self._viz: add_track_arranger = None

        begin_trim = trims[0] if trims else 0.0
        self._balance_trims = balance_trims
        self._balance_pending = False
        # Where the audible part starts, kept in place when balancing
        self._audible_start = track_offset + begin_trim

        self._build(title, sound, loop_points, trims, user_markers, track_offset)

    # === Build =========================================================

    def _build(
        self,
        title: str,
        sound: Path,
        loop_points: tuple[float, float],
        trims: tuple[float, float],
        user_markers: dict[Hash, float],
        track_offset: float,
    ) -> None:
        begin_trim, end_trim = trims or (0.0, 0.0)
        track = AudioTrack(
            sound, offset=track_offset, begin_trim=begin_trim, end_trim=end_trim
        )

        with dpg.window(
            label=title,
            width=700,
            height=400,
            autosize=False,
            no_saved_settings=True,
            tag=self._tag,
            on_close=self._close,
        ):
            dpg.add_spacer(height=10)

            self._viz = add_track_arranger(
                [track],
                loop_points=loop_points,
                on_loop_changed=self._dlg_on_loop_changed,
                on_trims_changed=(
                    self._dlg_on_trims_changed if self._has_trims else None
                ),
                user_markers=user_markers,
                on_user_markers_changed=self._dlg_on_user_markers_changed,
                markers_in_ms=self._markers_in_ms,
                row_height=220,
            )

            if loop_points is not None and loop_points[1] < 0.0:
                self._set_loop_from_end(loop_points, end_trim)

            dpg.add_separator()
            dpg.add_spacer(height=2)
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            if self._accept_on_okay:
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label=µ("Apply", "button"),
                        callback=self._on_okay,
                        tag=self._t("button_okay"),
                    )

    def _set_loop_from_end(
        self, loop_points: tuple[float, float], end_trim: float
    ) -> None:
        # The visualizer only knows 0.0 as "to end" and measures it from the end
        # of the timeline, which already includes the end trim
        start, end = loop_points
        duration = self._viz.duration * self._scale() - end_trim
        self._viz.set_loop_points((start, duration + end))

    # === Helpers =======================================================

    def _scale(self) -> float:
        return 1000.0 if self._markers_in_ms else 1.0

    def _get_trims(self) -> tuple[float, float]:
        if not self._has_trims:
            return (0.0, 0.0)

        return self._viz.get_trims(0, self._markers_in_ms)

    def _get_loop(self) -> tuple[float, float]:
        return self._viz.get_loop_points(self._markers_in_ms)

    def _get_user_markers(self) -> dict[int, float]:
        return self._viz.get_user_markers(self._markers_in_ms)

    # === DPG callbacks =================================================

    def _dlg_on_loop_changed(self, sender: str, info: Any, cb_user_data: Any) -> None:
        if not self._accept_on_okay and self._on_loop_changed:
            self._on_loop_changed(self._tag, self._get_loop(), self._user_data)

    def _dlg_on_user_markers_changed(
        self, sender: str, markers: dict[int, float], cb_user_data: Any
    ) -> None:
        if not self._accept_on_okay and self._on_user_markers_changed:
            self._on_user_markers_changed(
                self._tag, self._get_user_markers(), self._user_data
            )

    def _dlg_on_trims_changed(
        self, sender: str, info: tuple[int, tuple[float, float]], cb_user_data: Any
    ) -> None:
        if self._balance_trims:
            self._schedule_balance()

        if not self._accept_on_okay and self._on_trims_changed:
            self._on_trims_changed(self._tag, info[1], self._user_data)

    def _schedule_balance(self) -> None:
        if not self._balance_pending:
            self._balance_pending = True
            dpg.set_frame_callback(dpg.get_frame_count() + 1, self._apply_balance)

    def _apply_balance(self) -> None:
        if not self._viz:
            return

        # Moving the track while its trim handle is dragged would make the
        # handle run away, so wait for the drag to end
        if dpg.is_mouse_button_down(dpg.mvMouseButton_Left):
            dpg.set_frame_callback(dpg.get_frame_count() + 1, self._apply_balance)
            return

        self._balance_pending = False
        begin_trim = self._get_trims()[0]
        self._viz.set_track_offset(0, self._audible_start - begin_trim)

    def _on_okay(self) -> None:
        if self._has_loop and self._on_loop_changed:
            self._on_loop_changed(self._tag, self._get_loop(), self._user_data)
        if self._has_user_markers and self._on_user_markers_changed:
            self._on_user_markers_changed(
                self._tag, self._get_user_markers(), self._user_data
            )
        if self._has_trims and self._on_trims_changed:
            self._on_trims_changed(self._tag, self._get_trims(), self._user_data)

        self._close()

    def _close(self) -> None:
        if self._viz:
            self._viz.destroy()
            self._viz = None

        if dpg.does_item_exist(self._tag):
            dpg.delete_item(self._tag)

    # === Public ========================================================

    def show_message(self, msg: str = None, color: style.RGBA = style.red) -> None:
        """Show or hide the notification label. Pass ``msg=None`` to hide."""
        if not msg:
            dpg.hide_item(self._t("notification"))
            return

        dpg.configure_item(
            self._t("notification"),
            default_value=msg,
            color=color,
            show=True,
        )
