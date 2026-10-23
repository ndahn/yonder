from __future__ import annotations
from typing import Any, Callable
from pathlib import Path
import wave
import numpy as np
from dearpygui import dearpygui as dpg

from yonder.hash import calc_hash, lookup_name, Hash
from yonder.util import logger, get_temp_dir
from yonder.wem import wem2wav
from yonder.audio.wavesignal import minmax_envelope, to_channels, read_wav
from yonder.audio.simple_player import SimplePlayer
from yonder.gui import style, Icons
from yonder.gui.config import get_config
from yonder.gui.frame_tasks import call_in_frames
from yonder.gui.localization import µ
from yonder.gui.widgets.dpg_item import DpgItem


class add_signal_preview(DpgItem):
    """A waveform preview with simple playback.

    Loop points, trims and user markers are all optional: setting one of them
    to None hides its markers from the plot and stops playback from respecting
    it. All values are in milliseconds, like everywhere else in Wwise. Only the
    player and the plot's time axis work in seconds.

    Like Wwise segment markers, loop points and user markers are absolute
    positions and are not affected by the trims. A loop end <= 0 is measured
    from the end of the signal instead.

    When previewing a music track of a segment, the markers are on the
    segment's timeline while the signal is placed on it at the track's
    ``play_at``. Set ``marker_offset`` to ``-play_at`` so the markers line up
    with the audio.

    The markers popup in the footer holds a numeric input per marker, plus an
    entry into ``edit_markers_dialog`` for editing them on a full timeline.
    That entry needs a file to hand the dialog, so it only appears when the
    signal came from ``set_signal_from_wav``.

    Parameters
    ----------
    signal : numpy.ndarray, optional
        Samples to show, shaped ``(n_frames,)`` or ``(n_frames, n_channels)``.
        A mono signal is drawn as a single envelope filling the plot; two or
        more channels are stacked, the first above the axis and the second
        below, each in its own color. Anything past the second channel is
        folded away, see ``to_channels``.
    framerate : int, optional
        Sample rate of ``signal``.
    loop_points : tuple of (float, float), optional
        Initial ``(start, end)`` of the loop. None hides the loop markers.
    on_loop_changed : callable, optional
        Fired as ``on_loop_changed(tag, (start, end), user_data)``.
    trims : tuple of (float, float), optional
        Initial ``(begin_trim, end_trim)``. Begin trim is >= 0 and measured
        from the start, end trim is <= 0 and measured from the end. None hides
        the trim markers.
    on_trims_changed : callable, optional
        Fired as ``on_trims_changed(tag, (begin, end), user_data)``.
    user_markers : dict of (int or str) to float, optional
        Initial marker positions keyed by ID or name. None hides them.
    on_user_markers_changed : callable, optional
        Fired as ``on_user_markers_changed(tag, {id: pos}, user_data)``.
    marker_offset : float
        Signal position of the markers' origin, i.e. a marker at ``pos`` is
        drawn at ``pos + marker_offset``. Does not apply to the trims.
    markers_editable : bool
        Whether the markers on the plot can be dragged.
    balance_trims : bool
        Forwarded to the marker dialog: move the signal along with its begin
        trim so its audible part keeps starting at the same position. Set this
        when the owner balances the begin trim with a negative ``play_at``.
    no_playback_controls : bool
        Hide the footer with the play button and marker inputs.
    max_points : int
        Maximum waveform envelope points rendered.
    height : int
        Pixel height of the plot.
    tag : int or str
        Explicit tag; auto-generated if 0.
    user_data : any
        Passed through to all callbacks.
    """

    # Y range of the plot
    _Y_LIMIT = 1.05
    # One per channel of a multi channel signal, same pairing as the arranger
    _CHANNEL_COLORS = (style.blue, style.orange)
    # Length of the audio played on either side of the loop seam in loop preview
    _LOOP_PREVIEW_LEN = 2000.0
    # Steps of the numeric marker inputs
    _STEP = 10.0
    _STEP_FAST = 100.0

    def __init__(
        self,
        signal: np.ndarray = None,
        framerate: int = None,
        *,
        loop_points: tuple[float, float] = None,
        on_loop_changed: Callable[[str, tuple[float, float], Any], None] = None,
        trims: tuple[float, float] = None,
        on_trims_changed: Callable[[str, tuple[float, float], Any], None] = None,
        user_markers: dict[Hash, float] = None,
        on_user_markers_changed: Callable[[str, dict[int, float], Any], None] = None,
        marker_offset: float = 0.0,
        markers_editable: bool = False,
        balance_trims: bool = False,
        no_playback_controls: bool = False,
        max_points: int = 4000,
        height: int = 130,
        tag: str = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self._signal = None
        self._source_path: Path = None
        self._framerate = 0
        self._duration = 0.0
        self._loop_points: tuple[float, float] = None
        self._trims: tuple[float, float] = None
        self._user_markers: dict[int, float] = None
        self._marker_offset = marker_offset
        self._markers_editable = markers_editable
        self._balance_trims = balance_trims
        self._max_points = max_points
        self._user_data = user_data

        self._on_loop_changed = on_loop_changed
        self._on_trims_changed = on_trims_changed
        self._on_user_markers_changed = on_user_markers_changed

        self._player: SimplePlayer = None
        self._want_playing = False
        self._last_pos = 0.0
        self.loop_preview_enabled = False

        self._build(no_playback_controls, height)

        self.trims = trims
        self.loop_points = loop_points
        self.user_markers = user_markers

        if signal is not None and framerate:
            self.set_signal(signal, framerate)

    def destroy(self) -> None:
        self.close()

    # === Public ========================================================

    @property
    def signal(self) -> np.ndarray:
        """The samples being shown: flat if mono, ``(n, 2)`` otherwise."""
        return self._signal

    @property
    def channels(self) -> int:
        if self._signal is None:
            return 0

        return self._signal.shape[1] if self._signal.ndim > 1 else 1

    def set_signal(self, sig: np.ndarray, framerate: int) -> None:
        self.stop()
        dpg.delete_item(self._t("xaxis"), slot=1, children_only=True)
        dpg.hide_item(self._t("error"))

        sig = np.asarray(sig, dtype=np.float32)
        if sig.ndim > 1:
            if sig.shape[1] == 1:
                sig = sig[:, 0]
            elif sig.shape[1] > 2:
                # A two sided plot can only show a pair, and folding surround
                # down properly needs a layout a wav header does not carry
                sig = to_channels(sig, 2)

        self._signal = sig
        self._framerate = framerate
        self._duration = len(sig) / framerate * 1000

        self._draw_waveform()
        # Whether the marker dialog can be offered depends on the source
        self._update_visibility()
        self._sync_markers()
        self.seek(self._region()[0])
        dpg.fit_axis_data(self._t("xaxis"))

    def clear(self) -> None:
        """Remove the signal."""
        self.stop()
        dpg.delete_item(self._t("xaxis"), slot=1, children_only=True)
        dpg.hide_item(self._t("error"))

        if self._player:
            self._player.clear()

        self._signal = None
        self._source_path = None
        self._framerate = 0
        self._duration = 0.0
        self._update_visibility()
        self._sync_markers()
        self.seek(0.0)

    def set_signal_from_wav(self, path: Path, mono: bool = False) -> None:
        """Load a wav or wem file. Wem files are converted first."""
        try:
            path = Path(path)
            # Kept as passed in: this is what the marker dialog is handed, and
            # it converts wem files of its own accord
            self._source_path = path

            if path.suffix == ".wem":
                vgmstream = get_config().locate_vgmstream()
                path = wem2wav(vgmstream, path, get_temp_dir())[0]

            if not path or not path.is_file():
                raise FileNotFoundError(path)

            self.set_signal(*read_wav(path, mono=mono))
        except (wave.Error, ValueError, OSError) as e:
            msg = µ("Error reading file: {exc}", "log").format(exc=e)
            logger.error(msg, exc_info=e)
            dpg.configure_item(self._t("error"), default_value=msg, show=True)

    @property
    def source_path(self) -> Path:
        """File the signal was loaded from, or None if it was set directly."""
        return self._source_path

    @property
    def framerate(self) -> int:
        return self._framerate

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def playback_duration(self) -> float:
        """Length of the loop, or of the trimmed signal if there is no loop."""
        start, end = self._abs_loop() or self._region()
        return max(0.0, end - start)

    @property
    def loop_points(self) -> tuple[float, float]:
        """The loop as ``(start, end)``, or None."""
        return self._loop_points

    @loop_points.setter
    def loop_points(self, points: tuple[float, float]) -> None:
        self._loop_points = tuple(points) if points is not None else None

        if self._player:
            self._player.loop = points is not None

        self._update_visibility()
        self._sync_markers()

        if not self.playing and points is not None:
            self.seek(self._playback_loop()[0])

    @property
    def trims(self) -> tuple[float, float]:
        """The ``(begin_trim, end_trim)``, or None."""
        return self._trims

    @trims.setter
    def trims(self, trims: tuple[float, float]) -> None:
        if trims is not None:
            trims = (max(0.0, trims[0]), min(0.0, trims[1]))

        self._trims = trims
        self._update_visibility()
        self._sync_markers()

    @property
    def user_markers(self) -> dict[int, float]:
        """User marker positions ``{id: pos}``, or None."""
        if self._user_markers is None:
            return None

        return dict(self._user_markers)

    @user_markers.setter
    def user_markers(self, markers: dict[Hash, float]) -> None:
        for mid in self._user_markers or ():
            self._delete_item(self._t(f"marker_{mid}"))

        if dpg.does_item_exist(self._t("user_markers_inputs")):
            dpg.delete_item(self._t("user_markers_inputs"), children_only=True)

        if markers is None:
            self._user_markers = None
            self._update_visibility()
            return

        self._user_markers = {}
        colorgen = style.HighContrastColorGenerator()

        for mid, pos in markers.items():
            if isinstance(mid, str):
                marker_label = mid
                mid = calc_hash(mid)
            else:
                marker_label = lookup_name(mid, f"#{mid}")

            self._user_markers[mid] = pos

            # Inserted before the playback cursor so it stays on top
            dpg.add_drag_line(
                label=marker_label,
                color=colorgen(),
                no_inputs=not self._markers_editable,
                no_fit=True,
                callback=self._on_user_marker_dragged,
                user_data=mid,
                parent=self._t("plot"),
                before=self._t("playback_pos"),
                tag=self._t(f"marker_{mid}"),
            )

            if dpg.does_item_exist(self._t("user_markers_inputs")):
                dpg.add_input_float(
                    label=marker_label,
                    default_value=pos,
                    step=self._STEP,
                    step_fast=self._STEP_FAST,
                    format="%.1f",
                    width=130,
                    callback=self._on_user_marker_input,
                    user_data=mid,
                    parent=self._t("user_markers_inputs"),
                    tag=self._t(f"marker_{mid}_value"),
                )

        self._update_visibility()
        self._sync_markers()

    @property
    def marker_offset(self) -> float:
        """Signal position of the markers' origin."""
        return self._marker_offset

    @marker_offset.setter
    def marker_offset(self, offset: float) -> None:
        self._marker_offset = offset
        self._sync_markers()

    @property
    def markers_editable(self) -> bool:
        return self._markers_editable

    @markers_editable.setter
    def markers_editable(self, editable: bool) -> None:
        self._markers_editable = editable

        items = ["loop_start", "loop_end", "begin_trim", "end_trim"]
        items.extend(f"marker_{mid}" for mid in self._user_markers or ())
        for item in items:
            dpg.configure_item(self._t(item), no_inputs=not editable)

    @property
    def player(self) -> SimplePlayer:
        if not self._player:
            self._player = SimplePlayer()

        return self._player

    @property
    def playing(self) -> bool:
        return self._want_playing

    def play(self) -> None:
        if self.playing or self._signal is None:
            return

        # Deliberately lazy: every player boots a pyo server of its own, and a
        # track table can hold a lot of previews that are never played
        player = self.player

        if player.signal is not self._signal or player.framerate != self._framerate:
            player.set_signal(self._signal, self._framerate)

        player.loop = self._loop_points is not None
        # Resume from wherever the cursor sits. Also covers a seek made while
        # there was no player yet, which the player could not store
        self.seek(self._last_pos)
        player.play()

        self._want_playing = True

        if dpg.does_item_exist(self._t("play_stop")):
            dpg.configure_item(self._t("play_stop"), texture_tag=Icons.stop)

        self._update_playback_pos()

    def stop(self) -> None:
        self._want_playing = False

        if self._player and self._player.playing:
            # Keeps the position, the cursor is not moved either
            self._player.pause()

        if dpg.does_item_exist(self._t("play_stop")):
            dpg.configure_item(self._t("play_stop"), texture_tag=Icons.play)

    def seek(self, pos: float, relative: bool = False) -> None:
        if relative:
            pos *= self._duration

        if self._player:
            # The player works in seconds
            self._player.seek(pos / 1000)

        self._last_pos = pos
        self._set_plot_pos(self._t("playback_pos"), pos)

    def close(self) -> None:
        self._want_playing = False
        if self._player:
            self._player.close()
            self._player = None

        self._delete_item(self._t("markers_popup"))
        if dpg.does_item_exist(self.tag):
            dpg.delete_item(self.tag)

    # === DPG callbacks =================================================

    def _on_play_stop_clicked(self) -> None:
        if self.playing:
            self.stop()
        else:
            self.play()

    def _on_playback_pos_dragged(self, sender: str) -> None:
        start, end = self._region()
        self.seek(min(max(start, self._get_plot_pos(sender)), end))

    def _update_playback_pos(self) -> None:
        if not self._want_playing:
            return

        start, end = self._region()

        if not self._player.playing:
            # Reached the end on its own
            self.stop()
            self.seek(start)
            return

        pos = self._player.pos * 1000
        jump = None
        loop = self._playback_loop()

        if loop:
            loop_start, loop_end = loop
            preview_len = self._LOOP_PREVIEW_LEN

            if self.loop_preview_enabled and (pos < loop_start or pos >= loop_end):
                jump = loop_start
            elif (
                self.loop_preview_enabled
                and loop_start + preview_len <= pos < loop_end - preview_len
            ):
                jump = loop_end - preview_len
            elif pos >= loop_end or pos < self._last_pos:
                # The player wraps around at the end of the signal
                jump = loop_start
        elif pos >= end:
            self.stop()
            self.seek(start)
            return

        if jump is None and pos < start:
            jump = start

        if jump is not None:
            pos = jump
            self._player.seek(pos / 1000)

        self._last_pos = pos
        self._set_plot_pos(self._t("playback_pos"), pos)

        if dpg.does_item_exist(self._t("pos_text")):
            dpg.set_value(self._t("pos_text"), self._time_label(pos))

        call_in_frames(self._update_playback_pos)

    def _on_loop_dragged(self, sender: str, app_data: Any, which: str) -> None:
        self._set_loop_bound(which, self._get_plot_pos(sender) - self._marker_offset)

    def _on_loop_input(self, sender: str, value: float, which: str) -> None:
        self._set_loop_bound(which, value)

    def _on_trim_dragged(self, sender: str, app_data: Any, which: str) -> None:
        pos = self._get_plot_pos(sender)
        if which == "begin":
            self._set_trim(which, pos)
        else:
            self._set_trim(which, pos - self._duration)

    def _on_trim_input(self, sender: str, value: float, which: str) -> None:
        self._set_trim(which, value)

    def _on_user_marker_dragged(self, sender: str, app_data: Any, mid: int) -> None:
        self._set_user_marker(mid, self._get_plot_pos(sender) - self._marker_offset)

    def _on_user_marker_input(self, sender: str, value: float, mid: int) -> None:
        self._set_user_marker(mid, value)

    # --- Marker dialog --------------------------------------------------
    #
    # The dialog edits the same markers on a far roomier timeline. It hands
    # back whole tuples rather than single bounds, so these adopt the value
    # and then fire the same callback a drag would have.

    def _on_edit_markers_clicked(self) -> None:
        from yonder.gui.dialogs.edit_markers_dialog import edit_markers_dialog

        dpg.hide_item(self._t("markers_popup"))
        edit_markers_dialog(
            self._source_path,
            accept_on_okay=True,
            loop_points=self._loop_points,
            on_loop_changed=self._on_dialog_loop_changed,
            trims=self._trims,
            on_trims_changed=self._on_dialog_trims_changed,
            user_markers=self.user_markers,
            on_user_markers_changed=self._on_dialog_user_markers_changed,
            # We store where the markers' origin sits relative to the signal,
            # the dialog wants where the signal sits on the markers' timeline
            track_offset=-self._marker_offset,
            balance_trims=self._balance_trims,
            markers_in_ms=True,
        )

    def _on_dialog_loop_changed(
        self, sender: str, loop: tuple[float, float], ud: Any
    ) -> None:
        self.loop_points = loop
        if self._on_loop_changed:
            self._on_loop_changed(self.tag, self._loop_points, self._user_data)

    def _on_dialog_trims_changed(
        self, sender: str, trims: tuple[float, float], ud: Any
    ) -> None:
        self.trims = trims
        if self._on_trims_changed:
            self._on_trims_changed(self.tag, self._trims, self._user_data)

    def _on_dialog_user_markers_changed(
        self, sender: str, markers: dict[int, float], ud: Any
    ) -> None:
        self.user_markers = markers
        if self._on_user_markers_changed:
            self._on_user_markers_changed(self.tag, self.user_markers, self._user_data)

    # === Internals =====================================================

    def _draw_waveform(self) -> None:
        """Draw one waveform envelope per channel.

        A mono signal gets the whole row to itself, as its plain min/max
        envelope around the axis. Two channels are stacked instead, the first
        folded above the axis and the second below, each in its own color, so
        the stereo image can be read at a glance. The point budget is shared,
        so a stereo plot does not cost twice the vertices of a mono one.
        """
        if self._signal is None:
            return

        channels = self.channels
        time = np.linspace(0, self._duration / 1000, num=len(self._signal))
        buckets = max(1, self._max_points // (2 * channels))

        for channel in range(channels):
            samples = self._signal if channels == 1 else self._signal[:, channel]
            t_env, y_env = minmax_envelope(samples, time, buckets)

            if channels > 1:
                # Fold onto one side each so the two do not overlap
                y_env = np.abs(y_env) if channel == 0 else -np.abs(y_env)

            series = dpg.add_line_series(
                t_env.tolist(),
                y_env.tolist(),
                shaded=True,
                label=µ("Ch{idx}", "plot").format(idx=channel),
                parent=self._t("xaxis"),
            )
            color = self._CHANNEL_COLORS[channel % len(self._CHANNEL_COLORS)]
            dpg.bind_item_theme(series, style.themes.make_series_theme(color))

    # Trims, loop points and markers are all in ms, like the rest of the
    # widget. The conversion to the player's and the plot's seconds happens in
    # seek and the _..._plot_... helpers below, nowhere else

    def _region(self) -> tuple[float, float]:
        """The absolute ``(start, end)`` of the trimmed signal, in ms."""
        if self._trims is None:
            return 0.0, self._duration

        begin, end = self._trims
        start = min(begin, self._duration)
        return start, max(start, self._duration + end)

    def _abs_loop(self) -> tuple[float, float]:
        """The ``(start, end)`` of the loop within the signal in ms, or None."""
        if self._loop_points is None:
            return None

        offset = self._marker_offset
        loop_start, loop_end = self._loop_points
        loop_start += offset
        if loop_end <= 0.0:
            loop_end = self._duration + loop_end
        else:
            loop_end += offset

        start = min(max(0.0, loop_start), self._duration)
        return start, min(max(start, loop_end), self._duration)

    def _playback_loop(self) -> tuple[float, float]:
        """The loop in ms, limited to the trimmed signal, or None."""
        loop = self._abs_loop()
        if loop is None:
            return None

        region_start, region_end = self._region()
        start = min(max(region_start, loop[0]), region_end)
        end = min(max(start, loop[1]), region_end)

        if end <= start:
            # The loop was trimmed away, loop the trimmed signal instead
            return region_start, region_end

        return start, end

    def _set_loop_bound(self, which: str, value: float) -> None:
        if self._loop_points is None:
            return

        start, end = self._loop_points
        if which == "start":
            start = max(0.0, value)
            if end > 0.0:
                start = min(start, end)
        else:
            # Keep clear of the "measured from the end" range when dragging
            end = max(value, start, 1.0)

        self._loop_points = (start, end)
        self._sync_markers()

        if self._on_loop_changed:
            self._on_loop_changed(self.tag, self._loop_points, self._user_data)

    def _set_trim(self, which: str, value: float) -> None:
        if self._trims is None:
            return

        begin, end = self._trims
        if which == "begin":
            begin = min(max(0.0, value), self._duration + end)
        else:
            end = max(min(0.0, value), begin - self._duration)

        self._trims = (begin, end)
        self._sync_markers()

        if self._on_trims_changed:
            self._on_trims_changed(self.tag, self._trims, self._user_data)

    def _set_user_marker(self, mid: int, value: float) -> None:
        if self._user_markers is None:
            return

        self._user_markers[mid] = max(0.0, value)
        self._sync_markers()

        if self._on_user_markers_changed:
            self._on_user_markers_changed(self.tag, self.user_markers, self._user_data)

    # The plot shows the signal in seconds, the values are edited in ms

    @staticmethod
    def _get_plot_pos(item: str) -> float:
        return dpg.get_value(item) * 1000

    @staticmethod
    def _set_plot_pos(item: str, pos: float) -> None:
        dpg.set_value(item, pos / 1000)

    @staticmethod
    def _set_plot_span(item: str, start: float, end: float, y: float) -> None:
        dpg.set_value(item, (start / 1000, -y, end / 1000, y))

    @staticmethod
    def _set_value(item: str, value: Any) -> None:
        if dpg.does_item_exist(item):
            dpg.set_value(item, value)

    def _update_visibility(self) -> None:
        has_loop = self._loop_points is not None
        has_trims = self._trims is not None
        # An empty dict leaves nothing to edit
        has_markers = bool(self._user_markers)

        for item in ("playback_region", "loop_start", "loop_end", "loop_inputs"):
            if dpg.does_item_exist(self._t(item)):
                dpg.configure_item(self._t(item), show=has_loop)

        for item in ("head", "tail", "begin_trim", "end_trim", "trim_inputs"):
            if dpg.does_item_exist(self._t(item)):
                dpg.configure_item(self._t(item), show=has_trims)

        if dpg.does_item_exist(self._t("markers_button")):
            show = {
                "markers_button": has_loop or has_trims or has_markers,
                "trims_separator": has_trims and has_loop,
                "markers_separator": has_markers and (has_loop or has_trims),
                "user_markers_inputs": has_markers,
                # The dialog arranges the signal on a timeline, which needs a
                # file it can load for itself
                "edit_markers_separator": self._source_path is not None,
                "edit_markers": self._source_path is not None,
            }
            for item, visible in show.items():
                dpg.configure_item(self._t(item), show=visible)

            if not show["markers_button"]:
                dpg.hide_item(self._t("markers_popup"))

    def _sync_markers(self) -> None:
        """Push the marker state into the plot and the inputs."""
        y = self._Y_LIMIT
        start, end = self._region()

        if self._trims is not None:
            self._set_plot_span(self._t("head"), 0.0, start, y)
            self._set_plot_span(self._t("tail"), end, self._duration, y)
            self._set_plot_pos(self._t("begin_trim"), start)
            self._set_plot_pos(self._t("end_trim"), end)
            self._set_value(self._t("begin_trim_value"), self._trims[0])
            self._set_value(self._t("end_trim_value"), self._trims[1])

        loop = self._abs_loop()
        if loop:
            loop_start, loop_end = loop
            self._set_plot_span(self._t("playback_region"), loop_start, loop_end, y)
            self._set_plot_pos(self._t("loop_start"), loop_start)
            self._set_plot_pos(self._t("loop_end"), loop_end)
            self._set_value(self._t("start_input"), self._loop_points[0])
            self._set_value(self._t("end_input"), self._loop_points[1])

        for mid, pos in (self._user_markers or {}).items():
            self._set_plot_pos(self._t(f"marker_{mid}"), pos + self._marker_offset)
            self._set_value(self._t(f"marker_{mid}_value"), pos)

        self._set_value(self._t("pos_text"), self._time_label(self._last_pos))
        self._set_value(self._t("duration_text"), self._time_label(self.duration))

    def _time_label(self, pos_ms: float) -> str:
        return µ("{len:.03f} s").format(len=pos_ms / 1000)

    # === Build =========================================================

    def _build(self, no_playback_controls: bool, height: int) -> None:
        with dpg.child_window(
            autosize_x=True,
            auto_resize_y=True,
            tag=self.tag,
        ):
            dpg.add_text(
                "",
                color=style.yellow,
                show=False,
                tag=self._t("error"),
            )
            self._build_plot(height)

            if not no_playback_controls:
                dpg.add_spacer(height=4)
                self._build_footer()

    def _build_plot(self, height: int) -> None:
        editable = self._markers_editable

        with dpg.plot(
            width=-1,
            height=height,
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

            # Shades over the trimmed-away head and tail
            for item in ("head", "tail"):
                dpg.add_drag_rect(
                    color=style.red.but(a=110),
                    no_inputs=True,
                    no_cursor=True,
                    no_fit=True,
                    tag=self._t(item),
                )

            dpg.add_drag_rect(
                color=style.green.but(a=60),
                no_inputs=True,
                no_cursor=True,
                no_fit=True,
                tag=self._t("playback_region"),
            )

            for which in ("start", "end"):
                dpg.add_drag_line(
                    label=µ(f"loop_{which}", "marker"),
                    color=style.green,
                    no_inputs=not editable,
                    no_fit=True,
                    callback=self._on_loop_dragged,
                    user_data=which,
                    tag=self._t(f"loop_{which}"),
                )

            for which in ("begin", "end"):
                dpg.add_drag_line(
                    label=µ(f"{which}_trim", "marker"),
                    color=style.red,
                    thickness=2,
                    no_inputs=not editable,
                    no_fit=True,
                    callback=self._on_trim_dragged,
                    user_data=which,
                    tag=self._t(f"{which}_trim"),
                )

            # User markers are inserted before this, it should stay on top
            dpg.add_drag_line(
                label=µ("pos", "marker"),
                color=style.light_blue,
                show_label=False,
                no_fit=True,
                callback=self._on_playback_pos_dragged,
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

            def _on_loop_test_changed(sender: str, enabled: bool, ud: Any) -> None:
                self.loop_preview_enabled = enabled

            dpg.add_checkbox(
                label=µ("Loop Test"),
                default_value=self.loop_preview_enabled,
                callback=_on_loop_test_changed,
                tag=self._t("loop_test"),
            )

            dpg.add_text("|")
            dpg.add_text(self._time_label(0.0), tag=self._t("pos_text"))
            dpg.add_text(self._time_label(self.duration), tag=self._t("duration_text"))
            dpg.add_text("|")

            dpg.add_button(
                label=µ("Markers", "button"),
                callback=lambda: dpg.show_item(self._t("markers_popup")),
                tag=self._t("markers_button"),
            )

        with dpg.window(
            popup=True,
            no_move=True,
            no_title_bar=True,
            no_resize=True,
            autosize=True,
            show=False,
            tag=self._t("markers_popup"),
        ):
            # Each section is only shown if its markers are handled at all
            with dpg.group(tag=self._t("loop_inputs")):
                for which in ("start", "end"):
                    dpg.add_input_float(
                        label=µ(f"loop_{which}", "marker"),
                        step=self._STEP,
                        step_fast=self._STEP_FAST,
                        format="%.1f",
                        width=130,
                        callback=self._on_loop_input,
                        user_data=which,
                        tag=self._t(f"{which}_input"),
                    )

            dpg.add_separator(tag=self._t("trims_separator"))
            with dpg.group(tag=self._t("trim_inputs")):
                dpg.add_input_float(
                    label=µ("begin_trim", "marker"),
                    min_value=0.0,
                    min_clamped=True,
                    step=self._STEP,
                    step_fast=self._STEP_FAST,
                    format="%.1f",
                    width=130,
                    callback=self._on_trim_input,
                    user_data="begin",
                    tag=self._t("begin_trim_value"),
                )
                dpg.add_input_float(
                    label=µ("end_trim", "marker"),
                    max_value=0.0,
                    max_clamped=True,
                    step=self._STEP,
                    step_fast=self._STEP_FAST,
                    format="%.1f",
                    width=130,
                    callback=self._on_trim_input,
                    user_data="end",
                    tag=self._t("end_trim_value"),
                )

            dpg.add_separator(tag=self._t("markers_separator"))
            dpg.add_group(tag=self._t("user_markers_inputs"))

            dpg.add_separator(tag=self._t("edit_markers_separator"))
            dpg.add_button(
                label=µ("Edit Markers", "button"),
                callback=self._on_edit_markers_clicked,
                tag=self._t("edit_markers"),
            )
