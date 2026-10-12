from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable
from pathlib import Path
import wave
import numpy as np

from dearpygui import dearpygui as dpg

from yonder.hash import calc_hash, lookup_name, Hash
from yonder.types import Soundbank, MusicSegment, MusicTrack
from yonder.types.base_types import MusicMarkerWwise
from yonder.enums import MarkerId, SourceType
from yonder.util import logger, get_temp_dir
from yonder.wem import wav2wem, wem2wav
from yonder.audio.wavesignal import read_wav, minmax_envelope
from yonder.audio.audiomath import mix
from yonder.audio.loop_points import find_loops
from yonder.gui import style, get_config
from yonder.gui.helpers import get_sound_path, center_window
from yonder.gui.localization import µ
from yonder.gui.widgets import DpgItem, loading_indicator
from yonder.gui.dialogs.file_dialog import open_file_dialog
from yonder.gui.dialogs.loop_point_candidates_dialog import loop_point_candidates_dialog


@dataclass
class AudioTrack:
    """A single track on the arranger timeline.

    Parameters
    ----------
    path : Path
        Wav file backing the track.
    label : str
        Display name; defaults to the file stem.
    offset : float
        Where the untrimmed source starts on the timeline, in ms if the
        arranger was built with ``markers_in_ms``, else in seconds. This is
        Wwise's ``play_at``: trimming does not change it.
    begin_trim : float
        How much of the source head is trimmed away (>= 0).
    end_trim : float
        How much of the source tail is trimmed away (<= 0).
    enabled : bool
        Disabled tracks are greyed out, cannot be dragged, and are ignored
        for timeline length and snapping.
    """

    path: Path
    label: str = ""
    offset: float = 0.0
    begin_trim: float = 0.0
    end_trim: float = 0.0
    enabled: bool = True


@dataclass(eq=False)
class _Row:
    """Per-track runtime state. All times are in seconds."""

    path: Path
    label: str
    offset: float = 0.0
    begin_trim: float = 0.0
    end_trim: float = 0.0
    enabled: bool = True
    duration: float = 0.0
    error: str = ""
    mono: bool = False
    # (t, y) envelope per half, t relative to the untrimmed source start
    envelopes: list[tuple[np.ndarray, np.ndarray]] = field(default_factory=list)
    # dpg items, recreated on every rebuild
    plot: int = 0
    xaxis: int = 0
    yaxis: int = 0
    clip: int = 0  # visual only, see _build_row
    trim_lo: int = 0
    trim_hi: int = 0
    head: int = 0  # shade over the trimmed-away source head
    tail: int = 0  # shade over the trimmed-away source tail
    series: list[int] = field(default_factory=list)
    mirrors: dict[str, int] = field(default_factory=dict)
    popup: int = 0
    popup_handlers: int = 0
    offset_input: int = 0
    begin_trim_input: int = 0
    end_trim_input: int = 0

    @property
    def start(self) -> float:
        """Where the audible part begins on the timeline."""
        return self.offset + self.begin_trim

    @property
    def end(self) -> float:
        """Where the audible part ends on the timeline."""
        return self.offset + self.duration + self.end_trim

    @property
    def src_end(self) -> float:
        """Where the untrimmed source ends on the timeline."""
        return self.offset + self.duration


class add_audio_visualizer(DpgItem):
    """A multi-track audio arranger.

    Every track gets its own waveform row inside a linked ``subplots`` block,
    so all rows share one time axis and one amplitude scale. Each track is a
    DAW-style clip: press anywhere inside its playback region and drag to move
    it along the timeline, or grab the handle at either end to trim that end.
    Both snap to the other tracks' edges, to the markers and to zero.
    Trimmed-away audio stays visible under a shade so it can be dragged back
    out.

    Loop points and named user markers are global to the timeline and live on
    a thin marker strip above the rows, mirrored read-only into every waveform
    row. Right-clicking a row opens its options menu.

    There is no playback - this widget only arranges and visualizes.

    Parameters
    ----------
    tracks : list of (Path or AudioTrack), optional
        Initial tracks, top row first.
    label : str
        Text label rendered above the plots.
    loop_markers_enabled : bool
        Enable the global loop start/end markers.
    loop_start : float
        Initial loop start, absolute on the timeline.
    loop_end : float
        Initial loop end, absolute on the timeline. ``0.0`` means "to end".
    on_loop_changed : callable, optional
        Fired as ``on_loop_changed(tag, (start, end, enabled), user_data)``.
    trim_enabled : bool
        Let each track be trimmed by dragging its clip edges.
    on_trims_changed : callable, optional
        Fired as ``on_trims_changed(tag, (index, (begin, end)), user_data)``.
    user_markers_enabled : bool
        Enable the global named user markers.
    user_markers : dict of (int or str) to float, optional
        Initial marker positions keyed by ID or name.
    on_user_markers_changed : callable, optional
        Fired as ``on_user_markers_changed(tag, markers_dict, user_data)``.
    on_track_moved : callable, optional
        Fired as ``on_track_moved(tag, (index, offset), user_data)``.
    on_track_toggled : callable, optional
        Fired as ``on_track_toggled(tag, (index, enabled), user_data)``.
    on_track_removed : callable, optional
        Fired as ``on_track_added(tag, (index, path), user_data)``. Also decides
        whether the row menu offers an add entry.
    on_track_removed : callable, optional
        Fired as ``on_track_removed(tag, index, user_data)``. Also decides
        whether the row menu offers a remove entry.
    snap_enabled : bool
        Initial state of the snapping toggle.
    snap_pixels : int
        Snap radius in screen pixels, converted to time at the current zoom.
    row_height : int
        Pixel height of a single waveform row.
    marker_height : int
        Pixel height of the marker strip above the rows.
    max_points : int
        Maximum waveform envelope points rendered per channel.
    markers_in_ms : bool
        Interpret and report all marker and offset values in milliseconds.
    width : int
        Plot width in pixels (-1 = auto).
    tag : int or str
        Explicit tag; auto-generated if 0.
    parent : int or str
        DPG parent item.
    user_data : any
        Passed through to all callbacks.
    """

    # Y range of a waveform row. Fixed so rows stay comparable.
    _Y_LIMIT = 1.05
    # Shortest a clip may be trimmed to, so it always stays grabbable
    _MIN_CLIP = 0.01
    # Keep-out zone around the trim handles, in pixels, so a move drag started
    # near a clip edge does not fight the trim handle sitting there
    _HANDLE_PIXELS = 7

    @classmethod
    def from_music_segment(
        cls,
        bnk: Soundbank,
        segment: MusicSegment,
        *,
        on_segment_changed: Callable[[str, MusicSegment, Any], None] = None,
        on_track_changed: Callable[[str, MusicTrack, Any], None] = None,
        on_markers_changed: Callable[[str, dict[int, float], Any], None] = None,
        label: str = "",
        snap_enabled: bool = True,
        snap_pixels: int = 8,
        row_height: int = 90,
        marker_height: int = 34,
        max_points: int = 5000,
        markers_in_ms: bool = True,
        width: int = -1,
        tag: str = 0,
        parent: str = 0,
        user_data: Any = None,
    ) -> add_audio_visualizer:
        tracks: list[MusicTrack] = [bnk[cid] for cid in segment.children]
        if not tag:
            tag = dpg.generate_uuid()

        def set_marker(mid: int, pos: float, name: str = None) -> None:
            for marker in segment.markers:
                if marker.id == mid:
                    marker.pos = pos
                    break
            else:
                segment.markers.append(
                    MusicMarkerWwise(
                        mid,
                        pos,
                        len(name or ""),
                        name or "",
                    )
                )

        def on_loop_changed(
            sender: str, info: tuple[float, float], cb_user_data: Any
        ) -> None:
            loop_start, loop_end = info
            set_marker(MarkerId.LoopStart, loop_start)
            set_marker(MarkerId.LoopEnd, loop_end)

            if on_markers_changed:
                on_markers_changed(
                    tag, {m.id: m.position for m in segment.markers}, user_data
                )

        def on_user_marker_changed(
            sender: str, markers: dict[Hash, float], cb_user_data: Any
        ) -> None:
            for mid, pos in markers:
                set_marker(mid, pos)

            if on_markers_changed:
                on_markers_changed(
                    tag, {m.id: m.position for m in segment.markers}, user_data
                )

        def on_trims_changed(
            sender: str, info: tuple[int, tuple[float, float]], cb_user_data: Any
        ) -> None:
            idx, (begin_trim, end_trim) = info
            tracks[idx].playlist[0].begin_trim_offset = begin_trim
            tracks[idx].playlist[0].end_trim_offset = end_trim

            if on_track_changed:
                on_track_changed(tag, tracks[idx], user_data)

        def on_track_moved(
            sender: str, info: tuple[int, float], cb_user_data: Any
        ) -> None:
            idx, pos = info
            tracks[idx].playlist[0].play_at = pos

            if on_track_changed:
                on_track_changed(tag, tracks[idx], user_data)

        def on_track_added(
            sender: str, info: tuple[int, Path], cb_user_data: Any
        ) -> None:
            idx, path = info
            if path.suffix != ".wem":
                path = wav2wem(get_config().locate_wwise(), path, get_temp_dir())

            mt = MusicTrack.new(bnk.new_id(), path, parent=segment.id)

            # Skip attach since we want it at a specific position
            segment.children.items.insert(idx, mt.id)
            bnk.add_nodes(mt)
            bnk.add_wem(path, SourceType.Streaming)

            if on_segment_changed:
                on_segment_changed(tag, segment, user_data)

        def on_track_removed(sender: str, idx: int, cb_user_data: Any) -> None:
            bnk.delete_nodes(tracks[idx])
            del tracks[idx]

            if on_segment_changed:
                on_segment_changed(tag, segment, user_data)

        markers = {m.id: m.position for m in segment.markers}
        loop_start = markers.pop(MarkerId.LoopStart, 0.0)
        loop_end = markers.pop(MarkerId.LoopEnd, 0.0)

        track_info = []

        for child in tracks:
            path = get_sound_path(
                bnk, child.source_ids[0], child.sources[0].source_type
            )
            playback = child.playlist[0]
            track_info.append(
                AudioTrack(
                    path,
                    child.id,
                    offset=playback.play_at,
                    begin_trim=playback.begin_trim_offset,
                    end_trim=playback.end_trim_offset,
                )
            )

        return add_audio_visualizer(
            track_info,
            label=label,
            loop_markers_enabled=on_loop_changed,
            loop_start=loop_start,
            loop_end=loop_end,
            on_loop_changed=on_loop_changed,
            trim_enabled=True,
            on_trims_changed=on_trims_changed,
            user_markers_enabled=True,
            user_markers=markers,
            on_user_markers_changed=on_user_marker_changed,
            on_track_moved=on_track_moved,
            on_track_toggled=None,
            on_track_added=on_track_added,
            on_track_removed=on_track_removed,
            snap_enabled=snap_enabled,
            snap_pixels=snap_pixels,
            row_height=row_height,
            marker_height=marker_height,
            max_points=max_points,
            markers_in_ms=markers_in_ms,
            width=width,
            tag=tag,
            parent=parent,
        )

    def __init__(
        self,
        tracks: Iterable[Path | AudioTrack] = None,
        *,
        label: str = "",
        loop_markers_enabled: bool = False,
        loop_start: float = 0.0,
        loop_end: float = 0.0,
        on_loop_changed: Callable[[str, tuple[float, float], Any], None] = None,
        trim_enabled: bool = False,
        on_trims_changed: Callable[
            [str, tuple[int, tuple[float, float]], Any], None
        ] = None,
        user_markers_enabled: bool = False,
        user_markers: dict[Hash, float] = None,
        on_user_markers_changed: Callable[[str, dict[Hash, float], Any], None] = None,
        on_track_moved: Callable[[str, tuple[int, float], Any], None] = None,
        on_track_toggled: Callable[[str, tuple[int, bool], Any], None] = None,
        on_track_added: Callable[[str, tuple[int, Path], Any], None] = None,
        on_track_removed: Callable[[str, int, Any], None] = None,
        snap_enabled: bool = True,
        snap_pixels: int = 8,
        row_height: int = 90,
        marker_height: int = 34,
        max_points: int = 5000,
        markers_in_ms: bool = True,
        width: int = -1,
        tag: str = 0,
        parent: str = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        # Layout / construction-time settings (fixed for lifetime)
        self._label = label
        self._loop_markers_enabled = loop_markers_enabled
        self._trim_enabled = trim_enabled
        self._user_markers_enabled = user_markers_enabled
        self._snap_pixels = snap_pixels
        self._row_height = row_height
        self._marker_height = marker_height
        self._max_points = max_points
        self._markers_in_ms = markers_in_ms
        self._width = width
        self._parent = parent

        # Callbacks
        self._on_loop_changed = on_loop_changed
        self._on_trims_changed = on_trims_changed
        self._on_user_markers_changed = on_user_markers_changed
        self._on_track_moved = on_track_moved
        self._on_track_toggled = on_track_toggled
        self._on_track_added = on_track_added
        self._on_track_removed = on_track_removed

        self._user_data = user_data

        # Runtime state
        self._rows: list[_Row] = []
        self._strip: dict[str, int] = {}  # marker items on the marker strip
        self._axis_tags: dict[str, int] = {}
        self._subplots: int = 0
        self._marker_plot: int = 0
        self._marker_axis: int = 0
        self._handlers: int = 0
        self._snap_enabled: bool = True
        # (row, anchor time, offset at press) while a clip is being dragged
        self._drag: tuple[_Row, float, float] | None = None

        # Parse user markers - resolves str keys to int hashes
        self._user_markers: dict[int, float] = {}
        self._user_marker_labels: dict[int, str] = {}
        self._user_marker_colors: dict[int, style.RGBA] = {}

        colorgen = style.HighContrastColorGenerator()
        for mid, pos in (user_markers or {}).items():
            if isinstance(mid, str):
                marker_label = mid
                mid = calc_hash(mid)
            else:
                marker_label = lookup_name(mid, f"#{mid}")

            self._user_markers[mid] = pos / 1000 if markers_in_ms else pos
            self._user_marker_labels[mid] = marker_label
            self._user_marker_colors[mid] = colorgen()

        if markers_in_ms:
            loop_start /= 1000
            loop_end /= 1000

        # Loop points are absolute on the timeline — with per-track trims
        # there is no global begin trim left to anchor them to.
        # loop_end == 0.0 means "to end".
        self._loop_start: float = loop_start
        self._loop_end: float = loop_end

        self._setup_content(snap_enabled)
        self.set_tracks(tracks or [])

    def destroy(self) -> None:
        self._destroy_plots()
        self._drop(self._handlers)
        self._handlers = 0
        self._delete_item(self._t("markers_popup"))

    # === Tracks ========================================================

    @property
    def duration(self) -> float:
        """Length of the timeline in seconds (longest enabled track end)."""
        ends = [r.end for r in self._rows if r.enabled and not r.error]
        return max(ends) if ends else 0.0

    @property
    def tracks(self) -> list[AudioTrack]:
        """Current tracks, in row order."""
        return [
            AudioTrack(
                r.path,
                r.label,
                self._out(r.offset),
                self._out(r.begin_trim),
                self._out(r.end_trim),
                r.enabled,
            )
            for r in self._rows
        ]

    def set_tracks(self, tracks: Iterable[Path | AudioTrack]) -> None:
        """Replace all tracks and rebuild the plots."""
        self._rows = [self._make_row(t) for t in tracks]
        self._rebuild()

    def append_track(self, track: Path | AudioTrack) -> None:
        """Add a track as a new bottom row."""
        self._rows.append(self._make_row(track))
        self._rebuild()

    def remove_track(self, index: int) -> None:
        """Remove the track at ``index``."""
        self._rows.pop(index)
        self._rebuild()

    def clear(self) -> None:
        """Remove all tracks."""
        self.set_tracks([])

    def fit(self) -> None:
        """Zoom the time axis to the full timeline."""
        if not self._rows or not dpg.does_item_exist(self._rows[0].xaxis):
            return

        # All rows share one x axis, so fitting the first fits them all.
        xaxis = self._rows[0].xaxis
        duration = max(self.duration, 0.1)
        padding = 0.02 * duration
        dpg.set_axis_limits(xaxis, -padding, duration + padding)

        # set_axis_limits locks the axis - release it once the range landed,
        # otherwise the user can no longer zoom or pan.
        dpg.set_frame_callback(
            dpg.get_frame_count() + 2, lambda: self._unlock_axis(xaxis)
        )

    def get_track_offsets(self, millis: bool) -> list[float]:
        """Return every track's timeline start, in row order."""
        factor = 1000 if millis else 1
        return [r.offset * factor for r in self._rows]

    def set_track_offset(self, index: int, offset: float) -> None:
        """Move a track to a timeline position (snapping is not applied)."""
        row = self._rows[index]
        row.offset = max(0.0, self._into(offset))
        self._update_row_geometry(row)
        self._refresh_timeline()

    def set_track_enabled(self, index: int, enabled: bool) -> None:
        """Enable or disable a track."""
        row = self._rows[index]
        if row.enabled == enabled:
            return

        row.enabled = enabled
        self._apply_row_enabled(row)
        self._refresh_timeline()

    def is_snap_enabled(self) -> bool:
        return self._snap_enabled

    def set_snap_enabled(self, enabled: bool) -> None:
        self._snap_enabled = enabled

    def show_markers_popup(self, pos: tuple[float, float] = None) -> None:
        if pos is not None:
            dpg.set_item_pos(self._t("markers_popup"), pos=pos)

        dpg.show_item(self._t("markers_popup"))

    def _make_row(self, track: Path | AudioTrack) -> _Row:
        if isinstance(track, Path):
            track = AudioTrack(Path(track))

        path = Path(track.path) if track.path else None
        if path.suffix == ".wem":
            path = wem2wav(get_config().locate_vgmstream(), path, get_temp_dir())
            track.path = path

        row = _Row(
            path=path,
            label=track.label or (path.stem if path else µ("<empty>")),
            offset=max(0.0, self._into(track.offset)),
            enabled=track.enabled,
        )
        self._load_row(row)
        # Clamping needs the duration, so trims are applied after loading
        self._clamp_trims(row, self._into(track.begin_trim), self._into(track.end_trim))
        return row

    def _load_row(self, row: _Row) -> None:
        """Read the wav file and compute the per-channel envelopes."""
        if not row.path or not row.path.is_file():
            row.error = µ("Audio {file} not found", "msg").format(file=row.path)
            logger.error(row.error)
            return

        try:
            samples, framerate = read_wav(row.path)
        except (wave.Error, ValueError, OSError) as e:
            row.error = µ("Error reading file: {exc}", "log").format(exc=e)
            logger.error(row.error, exc_info=e)
            return

        n_frames = len(samples)
        row.duration = n_frames / framerate if framerate else 0.0
        time = np.linspace(0, row.duration, num=n_frames)

        # Channels are stacked into one row: first above the axis, second
        # below. Mono is mirrored so it fills the row like a stereo track.
        row.mono = samples.shape[1] == 1
        channels = (0, 0) if row.mono else (0, 1)
        factors = (1, -1)
        for i, channel in enumerate(channels):
            t_env, y_env = minmax_envelope(
                samples[:, channel], time, self._max_points // 2
            )
            row.envelopes.append((t_env, factors[i] * np.abs(y_env)))

    # === Dragging & snapping ===========================================

    def _snap_targets(self, exclude: _Row) -> list[float]:
        """Positions a dragged clip edge is allowed to latch onto."""
        targets = [0.0]

        for row in self._rows:
            if row is exclude or not row.enabled or row.error:
                continue
            targets.append(row.start)
            targets.append(row.end)

        if self._loop_markers_enabled:
            targets.extend(self._loop_abs_bounds())

        if self._user_markers_enabled:
            targets.extend(self._user_markers.values())

        return targets

    def _px_to_time(self, pixels: float) -> float:
        """Convert a screen distance to seconds at the current zoom level."""
        if not self._rows or not dpg.does_item_exist(self._rows[0].xaxis):
            return 0.0

        xmin, xmax = dpg.get_axis_limits(self._rows[0].xaxis)
        width = dpg.get_item_rect_size(self._rows[0].plot)[0]
        if width <= 0:
            return 0.0

        return pixels * (xmax - xmin) / width

    def _snap_threshold(self) -> float:
        """Snap radius in seconds, derived from the current zoom level."""
        return self._px_to_time(self._snap_pixels)

    def _snap_delta(self, row: _Row, anchors: Iterable[float]) -> float:
        """Smallest shift that lands one of ``anchors`` on a snap target."""
        if not self._snap_enabled:
            return 0.0

        threshold = self._snap_threshold()
        if threshold <= 0.0:
            return 0.0

        targets = self._snap_targets(row)
        best = 0.0
        for anchor in anchors:
            for target in targets:
                delta = target - anchor
                if abs(delta) <= threshold and (not best or abs(delta) < abs(best)):
                    best = delta

        return best

    def _on_trim_handle_dragged(self, sender: str, app_data: Any, ud: tuple) -> None:
        """A trim handle was dragged — move that clip edge only."""
        row, which = ud
        edge = dpg.get_value(sender)
        edge += self._snap_delta(row, (edge,))

        if which == "lo":
            self._clamp_trims(row, edge - row.offset, row.end_trim)
        else:
            self._clamp_trims(row, row.begin_trim, edge - row.src_end)

        self._update_row_geometry(row)
        self._refresh_timeline()
        self._fire_trims_changed(row)

    # --- Moving a clip by dragging its playback region ------------------
    #
    # ImPlot's own drag_rect body grab is too small and too invisible to aim
    # at, so the clip rect is inert and the move gesture is driven from the
    # global mouse handlers instead. That leaves the whole playback region
    # grabbable and keeps the trim handles as the only drag tools in the row.

    def _hovered_row(self) -> _Row | None:
        for row in self._rows:
            if (
                row.plot
                and dpg.does_item_exist(row.plot)
                and dpg.is_item_hovered(row.plot)
            ):
                return row

        return None

    def _hovered_time(self) -> float | None:
        """Time under the cursor, or None if the cursor left the arranger.

        Every plot shares the x axis, so any of them gives the same answer.
        """
        if self._hovered_row() is not None:
            return dpg.get_plot_mouse_pos()[0]

        if (
            self._marker_plot
            and dpg.does_item_exist(self._marker_plot)
            and dpg.is_item_hovered(self._marker_plot)
        ):
            return dpg.get_plot_mouse_pos()[0]

        return None

    def _on_mouse_click(self, sender: str, button: int) -> None:
        self._drag = None

        row = self._hovered_row()
        if row is None or not row.enabled or row.error:
            return

        pos = dpg.get_plot_mouse_pos()[0]
        if not row.start <= pos <= row.end:
            return  # outside the playback region, e.g. on a trimmed-away part

        if self._trim_enabled:
            # Leave the trim handles their own keep-out zone at either end
            handle = self._px_to_time(self._HANDLE_PIXELS)
            if abs(pos - row.start) <= handle or abs(pos - row.end) <= handle:
                return

        self._drag = (row, pos, row.offset)

    def _on_mouse_move(self, sender: str, app_data: Any) -> None:
        if not self._drag:
            return

        row, anchor, start_offset = self._drag
        if not any(r is row for r in self._rows) or not dpg.does_item_exist(row.plot):
            self._drag = None  # rebuilt under us
            return

        pos = self._hovered_time()
        if pos is None:
            return  # cursor left the arranger; pick back up when it returns

        # Derived from the anchor rather than accumulated, so a snap that
        # engages and releases again cannot drift the clip.
        offset = max(0.0, start_offset + (pos - anchor))
        offset += self._snap_delta(
            row, (offset + row.begin_trim, offset + row.duration + row.end_trim)
        )
        offset = max(0.0, offset)

        if offset == row.offset:
            return

        row.offset = offset
        self._update_row_geometry(row)
        self._refresh_timeline()
        self._fire_track_moved(row)

    def _on_mouse_release(self, sender: str, app_data: Any) -> None:
        self._drag = None

    def _clamp_trims(self, row: _Row, begin_trim: float, end_trim: float) -> None:
        """Store trims, keeping the clip inside the source and non-degenerate."""
        room = max(0.0, row.duration - self._MIN_CLIP)
        row.begin_trim = min(max(0.0, begin_trim), room)
        row.end_trim = max(min(0.0, end_trim), -(room - row.begin_trim))

    def _fire_track_moved(self, row: _Row) -> None:
        if self._on_track_moved:
            self._on_track_moved(
                self._tag,
                (self._rows.index(row), self._out(row.offset)),
                self._user_data,
            )

    def _update_row_geometry(self, row: _Row) -> None:
        """Push a row's offset and trims into its plot items."""
        if not dpg.does_item_exist(row.clip):
            return

        lo, hi = -self._Y_LIMIT, self._Y_LIMIT
        dpg.set_value(row.clip, (row.start, lo, row.end, hi))
        self._set_value(row.trim_lo, row.start)
        self._set_value(row.trim_hi, row.end)

        # Trimmed-away audio stays drawn, just shaded, so it can be recovered
        if row.head:
            dpg.set_value(row.head, (row.offset, lo, row.start, hi))
            dpg.configure_item(row.head, show=row.begin_trim > 0.0)
        if row.tail:
            dpg.set_value(row.tail, (row.end, lo, row.src_end, hi))
            dpg.configure_item(row.tail, show=row.end_trim < 0.0)

        for series, (t_env, y_env) in zip(row.series, row.envelopes):
            dpg.set_value(series, [(t_env + row.offset).tolist(), y_env.tolist()])

        self._set_value(row.offset_input, self._out(row.offset))
        self._set_value(row.begin_trim_input, self._out(row.begin_trim))
        self._set_value(row.end_trim_input, self._out(row.end_trim))

    def _refresh_timeline(self) -> None:
        """Re-clamp the view and the markers after the timeline length moved."""
        duration = self.duration
        padding = max(0.05 * duration, 0.1)

        for row in self._rows:
            if dpg.does_item_exist(row.xaxis):
                dpg.set_axis_limits_constraints(row.xaxis, -padding, duration + padding)

        if dpg.does_item_exist(self._marker_axis):
            dpg.set_axis_limits_constraints(
                self._marker_axis, -padding, duration + padding
            )

        self._sync_markers()

    @staticmethod
    def _unlock_axis(axis: int) -> None:
        if dpg.does_item_exist(axis):
            dpg.set_axis_limits_auto(axis)

    # === Row menu ======================================================

    def _on_row_enabled_toggled(self, sender: str, value: bool, row: _Row) -> None:
        row.enabled = value
        self._apply_row_enabled(row)
        self._refresh_timeline()

        if self._on_track_toggled:
            self._on_track_toggled(
                self._tag, (self._rows.index(row), value), self._user_data
            )

    def _apply_row_enabled(self, row: _Row) -> None:
        if not dpg.does_item_exist(row.plot):
            return

        suffix = "" if row.enabled else f"  ({µ('disabled', 'track')})"
        dpg.configure_item(row.plot, label=f"{row.label}{suffix}")
        dpg.configure_item(row.clip, color=self._clip_color(row))

        for handle in (row.trim_lo, row.trim_hi):
            if handle:
                dpg.configure_item(handle, no_inputs=not row.enabled)

        for i, series in enumerate(row.series):
            dpg.bind_item_theme(series, self._series_theme(row, i))

    def _on_row_offset_input(self, sender: str, value: float, row: _Row) -> None:
        row.offset = max(0.0, self._into(value))
        self._update_row_geometry(row)
        self._refresh_timeline()
        self._fire_track_moved(row)

    def _on_row_offset_reset(self, sender: str, app_data: Any, row: _Row) -> None:
        row.offset = 0.0
        self._update_row_geometry(row)
        self._refresh_timeline()
        self._fire_track_moved(row)

    def _on_row_add(self, sender: str, app_data: Any, row: _Row) -> None:
        path = open_file_dialog(
            default_dir=str(row.path.parent),
            filetypes={
                µ("Audio Files (.wav, .wem)", "filetypes"): ["*.wav", "*.wem"],
                µ("Wave (.wav)", "filetypes"): "*.wav",
                µ("WEM (.wem)", "filetypes"): "*.wem",
            },
        )

        if path:
            index = self._rows.index(row)
            self._rows.insert(index, self._make_row(Path(path)))
            self._rebuild()

    def _on_row_remove(self, sender: str, app_data: Any, row: _Row) -> None:
        index = self._rows.index(row)
        dpg.hide_item(row.popup)
        self.remove_track(index)

        if self._on_track_removed:
            self._on_track_removed(self._tag, index, self._user_data)

    # === Loop markers ==================================================

    def get_loop_state(self, millis: bool) -> tuple[float, float, bool]:
        """Return ``(loop_start, loop_end, enabled)``, absolute on the timeline."""
        if not self._loop_markers_enabled:
            return (0.0, 0.0)

        factor = 1000 if millis else 1
        return (self._loop_start * factor, self._loop_end * factor)

    def set_loop_state(self, loop_start: float, loop_end: float) -> None:
        """Set loop positions (absolute on the timeline, seconds)."""
        if not self._loop_markers_enabled:
            raise RuntimeError("loop_markers_enabled is False")

        self._loop_start = loop_start
        self._loop_end = loop_end
        self._sync_markers()

    def _loop_abs_bounds(self) -> tuple[float, float]:
        """Loop ``(start, end)``; ``loop_end == 0.0`` means the timeline end."""
        end = self.duration if self._loop_end == 0.0 else self._loop_end
        return self._loop_start, end

    def _fire_loop_changed(self) -> None:
        if self._on_loop_changed:
            self._on_loop_changed(self._tag, self.get_loop_state(True), self._user_data)

    def _set_loop_marker_pos(self, sender: str, pos: float, loop_marker: str) -> None:
        pos = self._get_valid_pos(pos)
        if loop_marker == "loop_start":
            self._loop_start = max(0.0, pos)
        else:
            self._loop_end = max(0.001, pos)  # keep clear of the 0.0 sentinel

        self._sync_markers()
        self._fire_loop_changed()

    def _on_loop_marker_moved(self, sender: str) -> None:
        pos = self._get_valid_pos(dpg.get_value(sender))
        if sender == self._strip.get("loop_start"):
            self._loop_start = max(0.0, pos)
        else:
            self._loop_end = max(0.001, pos)

        self._sync_markers()
        self._fire_loop_changed()

    def _mixdown(self, row_indices: list[int] = None) -> tuple[np.ndarray, int]:
        """Mix every audible track into one mono signal on the timeline.

        Parameters
        ----------
        row_indices : list[int], optional
            Rows to mix, or all rows if None.

        Returns
        -------
        tuple of (numpy.ndarray, int)
            Flat mono samples and their sample rate. Empty if nothing is
            audible.
        """
        if not row_indices:
            row_indices = list(range(len(self._rows)))

        rows = sorted((self._rows[i] for i in row_indices), key=lambda r: r.start)
        signals = []
        offsets = []
        framerates = []

        for row in rows:
            if not row.enabled or row.error:
                continue

            signal, framerate = read_wav(row.path)

            # Only the audible part belongs in the mix
            begin = max(0, round(row.begin_trim * framerate))
            end = len(signal) + min(0, round(row.end_trim * framerate))
            signal = signal[begin:end]
            if not len(signal):
                continue

            signals.append(signal)
            offsets.append(row.start)
            framerates.append(framerate)

        if not signals:
            return np.empty(0, dtype=np.float32), 0

        combined, framerate = mix(signals, offsets, framerates, mono=True)
        # find_loops wants a flat mono signal; mix returns (n_frames, 1)
        return combined[:, 0], framerate

    def _find_loop_markers(self) -> None:
        """Search the mixed-down timeline for loop points and offer them."""
        with loading_indicator(µ("Searching...")):
            combined, framerate = self._mixdown()
            if not len(combined):
                logger.warning(µ("No audio to search for loop points", "log"))
                return

            # TODO remove min_len
            candidates = find_loops(combined, framerate, candidates=5, min_len_s=1.0)

        # Give dpg a frame so that another modal dialog can open again
        dpg.split_frame()

        dlg = loop_point_candidates_dialog(
            candidates,
            combined,
            framerate,
            current_loop_points=self._loop_abs_bounds(),
            on_apply=self._on_loop_candidate_applied,
        )
        center_window(dlg.tag)

    def _on_loop_candidate_applied(
        self, sender: str, loop: tuple[float, float], ud: Any
    ) -> None:
        self.set_loop_state(*loop)
        self._fire_loop_changed()

    # === Trim markers ==================================================

    def get_trims(self, index: int, millis: bool) -> tuple[float, float]:
        """Return one track's ``(begin_trim, end_trim)``.

        Begin trim is measured from the source start, end trim from the
        source end (and is therefore <= 0).
        """
        if not self._trim_enabled:
            return (0.0, 0.0)

        row = self._rows[index]
        factor = 1000 if millis else 1
        return (row.begin_trim * factor, row.end_trim * factor)

    def get_all_trims(self, millis: bool) -> list[tuple[float, float]]:
        """Return every track's ``(begin_trim, end_trim)``, in row order."""
        return [self.get_trims(i, millis) for i in range(len(self._rows))]

    def set_trims(self, index: int, begin_trim: float, end_trim: float) -> None:
        """Set one track's trims programmatically (snapping is not applied)."""
        if not self._trim_enabled:
            raise RuntimeError("trim_enabled is False")

        if end_trim > 0.0:
            raise ValueError("end_trim must be <0")

        row = self._rows[index]
        self._clamp_trims(row, self._into(begin_trim), self._into(end_trim))
        self._update_row_geometry(row)
        self._refresh_timeline()

    def _fire_trims_changed(self, row: _Row) -> None:
        if self._on_trims_changed:
            index = self._rows.index(row)
            self._on_trims_changed(
                self._tag, (index, self.get_trims(index, True)), self._user_data
            )

    def _on_row_trim_input(self, sender: str, value: float, ud: tuple) -> None:
        row, which = ud
        value = self._into(value)
        if which == "begin_trim":
            self._clamp_trims(row, value, row.end_trim)
        else:
            self._clamp_trims(row, row.begin_trim, value)

        self._update_row_geometry(row)
        self._refresh_timeline()
        self._fire_trims_changed(row)

    def _on_row_trims_reset(self, sender: str, app_data: Any, row: _Row) -> None:
        self._clamp_trims(row, 0.0, 0.0)
        self._update_row_geometry(row)
        self._refresh_timeline()
        self._fire_trims_changed(row)

    def _trim_silence(self) -> None:
        pass

    # === User markers ==================================================

    def get_user_markers(self, millis: bool) -> dict[int, float]:
        """Return all user marker positions ``{id: pos}``."""
        if millis:
            return {k: v * 1000 for k, v in self._user_markers.items()}

        return dict(self._user_markers)

    def get_user_marker_pos(self, mid: Hash, default: float = 0.0) -> float:
        """Return a single marker position by ID or name, in seconds."""
        if isinstance(mid, str):
            mid = calc_hash(mid)

        return self._user_markers.get(mid, default)

    def _fire_user_markers_changed(self) -> None:
        if self._on_user_markers_changed:
            self._on_user_markers_changed(
                self._tag, self.get_user_markers(True), self._user_data
            )

    def _set_user_marker_pos(self, sender: str, pos: float, mid: int) -> None:
        self._user_markers[mid] = self._get_valid_pos(pos)
        self._sync_markers()
        self._fire_user_markers_changed()

    def _on_user_marker_moved(self, sender: str, app_data: Any, mid: int) -> None:
        self._user_markers[mid] = self._get_valid_pos(dpg.get_value(sender))
        self._sync_markers()
        self._fire_user_markers_changed()

    # === Marker plumbing ===============================================

    def _get_valid_pos(self, pos: float, force_from_end: bool = False) -> float:
        """Constrain a position to the timeline.

        Parameters
        ----------
        pos : float
            The position to constrain in seconds.
        force_from_end : bool, optional
            If true, the input position is always measured from the end no
            matter its sign.

        Returns
        -------
        float
            A valid position on the timeline.
        """
        duration = self.duration

        if force_from_end:
            pos = duration - abs(pos)
        elif pos < 0:
            pos = duration + pos

        return max(0.0, min(pos, duration))

    def _marker_items(self, key: str) -> list[int]:
        """The strip item plus the read-only mirror in every waveform row."""
        items = [self._strip.get(key, 0)]
        items.extend(row.mirrors.get(key, 0) for row in self._rows)
        return [i for i in items if i and dpg.does_item_exist(i)]

    def _set_marker_line(self, key: str, pos: float) -> None:
        for item in self._marker_items(key):
            dpg.set_value(item, pos)

        tag = self._axis_tags.get(key)
        if tag and dpg.does_item_exist(tag):
            dpg.set_value(tag, pos)

    def _sync_markers(self) -> None:
        """Push the authoritative marker state into every plot item."""
        if self._loop_markers_enabled:
            start, end = self._loop_abs_bounds()
            start_viz = min(self._get_valid_pos(start), end)
            self._set_marker_line("loop_start", start_viz)
            self._set_marker_line("loop_end", end)
            self._set_value(self._t("loop_start_value"), start)
            self._set_value(self._t("loop_end_value"), end)

        if self._user_markers_enabled:
            for mid in self._user_markers:
                pos = self._get_valid_pos(self._user_markers[mid])
                self._user_markers[mid] = pos
                self._set_marker_line(f"m{mid}", pos)
                self._set_value(self._t(f"marker_{mid}_value"), pos)

    @staticmethod
    def _set_value(item: str | int, value: Any) -> None:
        if item and dpg.does_item_exist(item):
            dpg.set_value(item, value)

    @staticmethod
    def _drop(item: int) -> None:
        """Delete a uuid-tagged item. Unlike ``_delete_item`` it has no alias."""
        if item and dpg.does_item_exist(item):
            dpg.delete_item(item)

    def _into(self, value: float) -> float:
        """Convert a public value into internal seconds."""
        return value / 1000 if self._markers_in_ms else value

    def _out(self, value: float) -> float:
        """Convert internal seconds into a public value."""
        return value * 1000 if self._markers_in_ms else value

    def _step(self) -> float:
        """Sensible increment for a numeric input in the public unit."""
        return 10.0 if self._markers_in_ms else 0.01

    # === Rendering =====================================================

    def _clip_color(self, row: _Row) -> style.RGBA:
        if not row.enabled:
            return style.dark_grey.but(a=110)
        return style.light_blue.but(a=70)

    def _series_theme(self, row: _Row, channel: int) -> int:
        if not row.enabled:
            return style.themes.make_series_theme(style.light_grey.but(a=110))

        color = style.blue if row.mono or channel == 0 else style.orange
        return style.themes.make_series_theme(color)

    def _destroy_plots(self) -> None:
        self._drag = None
        for row in self._rows:
            self._drop(row.popup)
            self._drop(row.popup_handlers)
            row.plot = row.xaxis = row.yaxis = row.clip = 0
            row.trim_lo = row.trim_hi = row.head = row.tail = 0
            row.popup = row.popup_handlers = row.offset_input = 0
            row.begin_trim_input = row.end_trim_input = 0
            row.series = []
            row.mirrors = {}

        self._drop(self._subplots)
        self._subplots = 0
        self._marker_plot = 0
        self._marker_axis = 0
        self._strip.clear()
        self._axis_tags.clear()

    def _rebuild(self) -> None:
        """Recreate the subplots block. DPG cannot resize it in place."""
        self._destroy_plots()

        errors = [r.error for r in self._rows if r.error]
        dpg.configure_item(
            self._t("errors"),
            default_value="\n".join(errors),
            show=bool(errors),
        )

        playable = [r for r in self._rows if not r.error]
        if not playable:
            dpg.hide_item(self._t("plot_group"))
            return

        dpg.show_item(self._t("plot_group"))

        # The marker strip is just another subplot row, sized via the ratios so
        # the drag tools on it stay grabbable.
        n_rows = len(playable) + 1
        marker_ratio = self._marker_height / self._row_height
        height = self._marker_height + len(playable) * self._row_height

        with dpg.subplots(
            n_rows,
            1,
            link_all_x=True,
            link_all_y=True,
            row_ratios=[marker_ratio] + [1.0] * len(playable),
            width=self._width,
            height=height,
            no_resize=True,
            no_menus=True,
            no_title=True,
            parent=self._t("plot_group"),
        ) as self._subplots:
            self._build_marker_strip()
            for i, row in enumerate(playable):
                self._build_row(row, is_last=i == len(playable) - 1)

        # Popups are windows, so they have to be built outside the subplots
        for row in playable:
            self._build_row_menu(row)

        for row in playable:
            dpg.set_axis_limits(row.yaxis, -self._Y_LIMIT, self._Y_LIMIT)
            self._update_row_geometry(row)
            self._apply_row_enabled(row)

        self._refresh_timeline()
        self.fit()

    def _build_marker_strip(self) -> None:
        with dpg.plot(
            no_title=True,
            no_menus=True,
            no_mouse_pos=True,
            no_frame=True,
            no_box_select=True,
        ) as self._marker_plot:
            self._marker_axis = dpg.add_plot_axis(
                dpg.mvXAxis,
                label=µ("markers"),
                opposite=True,
                no_label=True,
                no_highlight=True,
                no_tick_labels=True,
                no_tick_marks=True,
                no_initial_fit=True,
            )
            # Not hidden with show=False - a hidden axis loses its flags and
            # renders default tick labels into the strip.
            dpg.add_plot_axis(
                dpg.mvYAxis,
                no_label=True,
                no_highlight=True,
                no_tick_labels=True,
                no_tick_marks=True,
                no_gridlines=True,
            )

            if self._loop_markers_enabled:
                start, end = self._loop_abs_bounds()
                self._axis_tags["loop_start"] = dpg.add_axis_tag(
                    label=µ("L0", "marker"),
                    default_value=start,
                    color=style.green,
                    parent=self._marker_axis,
                )
                self._axis_tags["loop_end"] = dpg.add_axis_tag(
                    label=µ("L1", "marker"),
                    default_value=end,
                    color=style.green,
                    parent=self._marker_axis,
                )
                self._strip["loop_start"] = dpg.add_drag_line(
                    label=µ("loop_start", "marker"),
                    color=style.green,
                    default_value=start,
                    no_fit=True,
                    callback=self._on_loop_marker_moved,
                )
                self._strip["loop_end"] = dpg.add_drag_line(
                    label=µ("loop_end", "marker"),
                    color=style.green,
                    default_value=end,
                    no_fit=True,
                    callback=self._on_loop_marker_moved,
                )

            if self._user_markers_enabled:
                for i, (mid, pos) in enumerate(self._user_markers.items()):
                    color = self._user_marker_colors[mid]
                    marker_label = self._user_marker_labels[mid]
                    self._axis_tags[f"m{mid}"] = dpg.add_axis_tag(
                        label=µ("m{idx}", "marker").format(idx=i),
                        default_value=pos,
                        color=color,
                        parent=self._marker_axis,
                    )
                    self._strip[f"m{mid}"] = dpg.add_drag_line(
                        label=marker_label,
                        color=color,
                        default_value=pos,
                        no_fit=True,
                        callback=self._on_user_marker_moved,
                        user_data=mid,
                    )

        dpg.bind_item_theme(self._marker_plot, style.themes.player_plot)

    def _build_row(self, row: _Row, *, is_last: bool) -> None:
        with dpg.plot(
            label=row.label,
            no_menus=True,
            no_mouse_pos=True,
            no_box_select=True,
            # Left drag moves clips, so panning goes to the middle button
            pan_button=dpg.mvMouseButton_Middle,
        ) as row.plot:
            row.xaxis = dpg.add_plot_axis(
                dpg.mvXAxis,
                label=µ("time"),
                no_label=True,
                no_highlight=True,
                no_tick_labels=not is_last,
                no_tick_marks=not is_last,
            )
            row.yaxis = dpg.add_plot_axis(
                dpg.mvYAxis,
                label=µ("amp"),
                no_label=True,
                no_highlight=True,
                no_tick_labels=True,
                no_tick_marks=True,
            )

            for i, (t_env, y_env) in enumerate(row.envelopes):
                series = dpg.add_line_series(
                    (t_env + row.offset).tolist(),
                    y_env.tolist(),
                    shaded=True,
                    no_clip=True,
                    label=f"Ch{i}",
                    parent=row.xaxis,
                )
                row.series.append(series)

            # Shades over the trimmed-away source head and tail
            if self._trim_enabled:
                row.head = self._add_trim_shade()
                row.tail = self._add_trim_shade()

            # Read-only mirrors of the global markers
            self._build_row_mirrors(row)

            # Outlines the playback region. Inert: moving the clip is driven
            # from the global mouse handlers so the whole region is grabbable.
            row.clip = dpg.add_drag_rect(
                label=row.label,
                color=self._clip_color(row),
                default_value=(row.start, -self._Y_LIMIT, row.end, self._Y_LIMIT),
                no_fit=True,
                no_cursor=True,
                no_inputs=True,
            )

            # Trim handles, added last so they win the hit test over anything
            # else drawn in the row.
            if self._trim_enabled:
                row.trim_lo = self._add_trim_handle(row, "lo", row.start)
                row.trim_hi = self._add_trim_handle(row, "hi", row.end)

        dpg.bind_item_theme(row.plot, style.themes.player_plot)

    def _add_trim_handle(self, row: _Row, which: str, pos: float) -> int:
        """Draggable line at one end of a clip that trims that end."""
        return dpg.add_drag_line(
            label=µ("begin_trim" if which == "lo" else "end_trim", "marker"),
            color=style.red,
            default_value=pos,
            thickness=2,
            show_label=False,
            no_fit=True,
            no_inputs=not row.enabled,
            callback=self._on_trim_handle_dragged,
            user_data=(row, which),
        )

    @staticmethod
    def _add_trim_shade() -> int:
        """A non-interactive rect dimming a trimmed-away part of a source."""
        return dpg.add_drag_rect(
            color=style.red.but(a=110),
            show=False,
            no_inputs=True,
            no_cursor=True,
            no_fit=True,
        )

    def _build_row_mirrors(self, row: _Row) -> None:
        if self._loop_markers_enabled:
            for key, color in (
                ("loop_start", style.green),
                ("loop_end", style.green),
            ):
                row.mirrors[key] = dpg.add_drag_line(
                    color=color.but(a=160),
                    show_label=False,
                    no_inputs=True,
                    no_cursor=True,
                    no_fit=True,
                )

        if self._user_markers_enabled:
            for mid in self._user_markers:
                row.mirrors[f"m{mid}"] = dpg.add_drag_line(
                    color=self._user_marker_colors[mid].but(a=160),
                    show_label=False,
                    no_inputs=True,
                    no_cursor=True,
                    no_fit=True,
                )

    def _build_row_menu(self, row: _Row) -> None:
        """Right-click menu for a waveform row.

        Hand-rolled rather than ``dpg.popup`` so both the window and the
        handler registry can be deleted again on the next rebuild.
        """
        row.popup = dpg.generate_uuid()

        with dpg.item_handler_registry() as row.popup_handlers:
            dpg.add_item_clicked_handler(
                dpg.mvMouseButton_Right,
                callback=lambda s, a, u: dpg.configure_item(u, show=True),
                user_data=row.popup,
            )
        dpg.bind_item_handler_registry(row.plot, row.popup_handlers)

        with dpg.window(
            popup=True,
            show=False,
            autosize=True,
            no_move=True,
            no_title_bar=True,
            no_resize=True,
            tag=row.popup,
        ):
            dpg.add_text(row.label, color=style.light_blue)
            dpg.add_text(
                µ("{dur:.3f} s").format(dur=row.duration),
                color=style.light_grey,
            )

            dpg.add_separator()

            if self._on_track_toggled:
                dpg.add_checkbox(
                    label=µ("Enabled", "track"),
                    default_value=row.enabled,
                    callback=self._on_row_enabled_toggled,
                    user_data=row,
                )

            row.offset_input = dpg.add_input_float(
                label=µ(
                    "Offset (ms)" if self._markers_in_ms else "Offset (s)", "track"
                ),
                default_value=self._out(row.offset),
                min_value=0.0,
                min_clamped=True,
                step=self._step(),
                step_fast=self._step() * 10,
                width=130,
                callback=self._on_row_offset_input,
                user_data=row,
            )

            if self._trim_enabled:
                row.begin_trim_input = dpg.add_input_float(
                    label=µ("begin_trim", "marker"),
                    default_value=self._out(row.begin_trim),
                    min_value=0.0,
                    min_clamped=True,
                    step=self._step(),
                    step_fast=self._step() * 10,
                    width=130,
                    callback=self._on_row_trim_input,
                    user_data=(row, "begin_trim"),
                )
                row.end_trim_input = dpg.add_input_float(
                    label=µ("end_trim", "marker"),
                    default_value=self._out(row.end_trim),
                    max_value=0.0,
                    max_clamped=True,
                    step=self._step(),
                    step_fast=self._step() * 10,
                    width=130,
                    callback=self._on_row_trim_input,
                    user_data=(row, "end_trim"),
                )

            # Tools
            dpg.add_separator()
            dpg.add_menu_item(
                label=µ("Find loop points"),
                callback=self._find_loop_markers,
                user_data=row,
            )
            dpg.add_menu_item(
                label=µ("Trim silence"),
                callback=self._trim_silence,
                user_data=row,
            )

            # Add/remove
            if self._on_track_added or self._on_track_removed:
                dpg.add_separator()
                if self._on_track_added:
                    dpg.add_menu_item(
                        label=µ("Add track", "button"),
                        callback=self._on_row_add,
                        user_data=row,
                    )
                if self._on_track_removed:
                    dpg.add_menu_item(
                        label=µ("Remove track", "button"),
                        callback=self._on_row_remove,
                        user_data=row,
                    )

    # === Build =========================================================

    def _setup_content(self, snap_enabled: bool) -> None:
        with dpg.group(tag=self._tag, parent=self._parent):
            if self._label:
                dpg.add_text(self._label, color=style.pink.mix(style.white))

            dpg.add_text(
                "",
                color=style.yellow,
                show=False,
                tag=self._t("errors"),
            )

            # Rebuilt wholesale whenever the track list changes
            dpg.add_group(tag=self._t("plot_group"))

        self._build_markers_popup()

        # Global handlers drive the "drag the playback region" move gesture.
        # They are harmless when none of our plots is hovered.
        with dpg.handler_registry() as self._handlers:
            dpg.add_mouse_click_handler(
                dpg.mvMouseButton_Left, callback=self._on_mouse_click
            )
            dpg.add_mouse_move_handler(callback=self._on_mouse_move)
            dpg.add_mouse_release_handler(
                dpg.mvMouseButton_Left, callback=self._on_mouse_release
            )

    def _build_markers_popup(self) -> None:
        with dpg.window(
            popup=True,
            no_move=True,
            no_title_bar=True,
            no_resize=True,
            tag=self._t("markers_popup"),
            show=False,
        ):
            if self._loop_markers_enabled:
                start, end = self._loop_abs_bounds()
                dpg.add_input_float(
                    label=µ("loop_start", "marker"),
                    default_value=start,
                    width=130,
                    callback=self._set_loop_marker_pos,
                    user_data="loop_start",
                    tag=self._t("loop_start_value"),
                )
                dpg.add_input_float(
                    label=µ("loop_end", "marker"),
                    default_value=end,
                    width=130,
                    callback=self._set_loop_marker_pos,
                    user_data="loop_end",
                    tag=self._t("loop_end_value"),
                )

            if self._user_markers_enabled:
                if self._loop_markers_enabled:
                    dpg.add_separator()
                # TODO Make this a widget table instead
                for mid, pos in self._user_markers.items():
                    dpg.add_input_float(
                        label=self._user_marker_labels[mid],
                        default_value=pos,
                        width=130,
                        callback=self._set_user_marker_pos,
                        user_data=mid,
                        tag=self._t(f"marker_{mid}_value"),
                    )


# ===========================================================================


def _demo() -> None:
    """Run the arranger standalone.

    ``python -m yonder.gui.widgets.audio_visualizer [wav ...]``

    Without arguments a few throwaway wavs are synthesized into the temp dir.
    """
    import math
    import struct
    import sys
    import tempfile
    from yonder.gui.icons import load_icons

    def make_wav(name: str, seconds: float, freq: float, channels: int) -> Path:
        path = Path(tempfile.gettempdir()) / name
        rate = 22050
        n = int(rate * seconds)
        frames = bytearray()
        for i in range(n):
            env = math.sin(math.pi * i / n) ** 2  # fade in/out
            value = int(28000 * env * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<h", value) * channels

        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(bytes(frames))

        return path

    if len(sys.argv) > 1:
        tracks = [
            AudioTrack(Path(p), offset=i * 1000.0) for i, p in enumerate(sys.argv[1:])
        ]
    else:
        tracks = [
            AudioTrack(make_wav("_yonder_demo_a.wav", 3.0, 220.0, 2)),
            AudioTrack(
                make_wav("_yonder_demo_b.wav", 1.8, 330.0, 1),
                offset=1500.0,
                begin_trim=300.0,
            ),
            AudioTrack(
                make_wav("_yonder_demo_c.wav", 2.4, 440.0, 2),
                offset=3000.0,
                end_trim=-400.0,
            ),
        ]

    def report(what: str) -> Callable:
        return lambda tag, data, ud: print(f"{what}: {data}")

    dpg.create_context()
    style.init_themes()
    load_icons()

    with dpg.window(tag="demo"):
        viz = add_audio_visualizer(
            tracks,
            label="Audio arranger",
            loop_markers_enabled=True,
            loop_start=500.0,
            loop_end=2500.0,
            on_loop_changed=report("loop"),
            trim_enabled=True,
            on_trims_changed=report("trims"),
            user_markers_enabled=True,
            user_markers={"Entry": 1000.0, "Exit": 4000.0},
            on_user_markers_changed=report("markers"),
            on_track_moved=report("moved"),
            on_track_toggled=report("toggled"),
            on_track_added=report("added"),
            on_track_removed=report("removed"),
        )

        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Append",
                callback=lambda: viz.append_track(
                    AudioTrack(tracks[0].path, offset=viz.duration * 1000)
                ),
            )
            dpg.add_button(label="Clear", callback=viz.clear)
            dpg.add_button(
                label="Dump",
                callback=lambda: print(
                    f"duration={viz.duration:.3f}",
                    viz.tracks,
                    viz.get_loop_state(True),
                    viz.get_all_trims(True),
                    viz.get_user_markers(True),
                    sep="\n  ",
                ),
            )

    dpg.create_viewport(title="Audio arranger", width=1100, height=700)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("demo", True)
    dpg.start_dearpygui()
    dpg.destroy_context()


if __name__ == "__main__":
    _demo()
