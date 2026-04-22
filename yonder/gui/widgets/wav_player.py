from typing import Any, Callable
from pathlib import Path
import numpy as np

from dearpygui import dearpygui as dpg

from yonder.hash import calc_hash, lookup_name, Hash
from yonder.util import logger
from yonder.interpolation import interpolate
from yonder.wem import wem2wav
from yonder.player import WavPlayer
from yonder.enums import CurveInterpolation
from yonder.types.base_types import RTPCGraphPoint
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.helpers import tmp_dir, shorten_path
from yonder.gui.localization import µ
from yonder.gui.dialogs.file_dialog import open_file_dialog
from .dpg_item import DpgItem


class add_wav_player(DpgItem):
    """An audio waveform player widget for Dear PyGui.

    Displays a waveform plot with an interactive playback cursor. Optionally
    supports loop markers, trim markers, and named user markers. Markers can
    be edited via drag handles on the plot or through a popup/dialog.

    Parameters
    ----------
    initial_file : Path, optional
        Audio file to load on construction (.wav or .wem).
    label : str
        Text label shown next to the file path row.
    allow_change_file : bool
        Show a Browse button to swap the audio file at runtime.
    show_filepath : bool
        Show the full shortened path instead of just the stem.
    on_file_changed : callable, optional
        Fired as ``on_file_changed(tag, path, user_data)`` when the file changes.
    loop_markers_enabled : bool
        Enable loop start/end drag markers on the waveform.
    loop_start : float
        Initial loop start position (in ms if ``markers_in_ms``, else seconds).
    loop_end : float
        Initial loop end position.
    on_loop_changed : callable, optional
        Fired as ``on_loop_changed(tag, (start, end, enabled), user_data)``.
    trim_enabled : bool
        Enable begin/end trim drag rect markers.
    begin_trim : float
        Initial begin trim position.
    end_trim : float
        Initial end trim position (negative = from end).
    on_trim_marker_changed : callable, optional
        Fired as ``on_trim_marker_changed(tag, (begin, end), user_data)``.
    user_markers_enabled : bool
        Enable named user-defined drag line markers.
    user_markers : dict of (int or str) to float, optional
        Initial marker positions keyed by ID or name.
    on_user_markers_changed : callable, optional
        Fired as ``on_user_markers_changed(tag, markers_dict, user_data)``.
    edit_markers_inplace : bool
        Allow dragging markers directly on the plot; otherwise use a dialog.
    max_points : int
        Maximum waveform envelope points rendered per channel.
    markers_in_ms : bool
        Interpret and report all marker positions in milliseconds.
    width : int
        Plot width in pixels (-1 = auto).
    height : int
        Plot height in pixels.
    tag : int or str
        Explicit tag; auto-generated if 0.
    parent : int or str
        DPG parent item.
    user_data : any
        Passed through to all callbacks.
    """

    def __init__(
        self,
        initial_file: Path,
        *,
        label: str = "",
        allow_change_file: bool = True,
        show_filepath: bool = False,
        on_file_changed: Callable[[str, Path, Any], None] = None,
        loop_markers_enabled: bool = False,
        loop_start: float = 0.0,
        loop_end: float = 0.0,
        on_loop_changed: Callable[[str, tuple[float, float, bool], Any], None] = None,
        trim_enabled: bool = False,
        begin_trim: float = 0.0,
        end_trim: float = 0.0,
        on_trim_marker_changed: Callable[[str, tuple[float, float], Any], None] = None,
        user_markers_enabled: bool = False,
        user_markers: dict[Hash, float] = None,
        on_user_markers_changed: Callable[[str, dict[Hash, float], Any], None] = None,
        edit_markers_inplace: bool = False,
        max_points: int = 5000,
        markers_in_ms: bool = True,
        width: int = -1,
        height: int = 100,
        tag: str = 0,
        parent: str = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        # Layout / construction-time settings (fixed for lifetime)
        self._label = label
        self._allow_change_file = allow_change_file
        self._show_filepath = show_filepath
        self._loop_markers_enabled = loop_markers_enabled
        self._trim_enabled = trim_enabled
        self._user_markers_enabled = user_markers_enabled
        self._edit_markers_inplace = edit_markers_inplace
        self._max_points = max_points
        self._markers_in_ms = markers_in_ms
        self._height = height
        self._parent = parent

        # Callbacks
        self._on_file_changed = on_file_changed
        self._on_loop_changed = on_loop_changed
        self._on_trim_marker_changed = on_trim_marker_changed
        self._on_user_markers_changed = on_user_markers_changed

        self._user_data = user_data

        # Runtime state
        self._audio: Path = initial_file
        self._player: WavPlayer = None

        # Parse user markers — resolves str keys to int hashes
        self._user_markers: dict[int, float] = {}
        self._user_marker_labels: dict[int, str] = {}
        if user_markers:
            for mid, pos in user_markers.items():
                if isinstance(mid, str):
                    marker_label = mid
                    mid = calc_hash(mid)
                else:
                    marker_label = lookup_name(mid, f"#{mid}")
                self._user_markers[mid] = pos
                self._user_marker_labels[mid] = marker_label

        # Convert initial marker positions to seconds if needed
        if markers_in_ms:
            loop_start /= 1000
            loop_end /= 1000
            begin_trim /= 1000
            end_trim /= 1000
            self._user_markers = {k: v / 1000 for k, v in self._user_markers.items()}

        self._loop_start = loop_start
        self._loop_end = loop_end
        self._begin_trim = begin_trim
        self._end_trim = end_trim

        # SFX curves — set via set_volume / set_lowpass / etc.
        self.volume: list[RTPCGraphPoint] = None
        self.lowpass: list[RTPCGraphPoint] = None
        self.highpass: list[RTPCGraphPoint] = None
        self.fadein: list[RTPCGraphPoint] = None
        self.fadeout: list[RTPCGraphPoint] = None

        self._setup_content(width, height)

        if initial_file:
            self.regenerate()

    # === Playback ======================================================

    def set_file(self, path: str | Path) -> None:
        """Load a new audio file, stopping any current playback."""
        if path:
            path = Path(path).absolute()

        if path == self._audio:
            return

        if self._on_file_changed:
            self._on_file_changed(self._tag, path, self._user_data)

        if self._player:
            self._player.stop()
            self._player = None

        self._audio = path

        if path and self._allow_change_file:
            path_str = shorten_path(path, 40) if self._show_filepath else path.stem
            dpg.set_value(self._t("filepath"), path_str)

        self.regenerate()

    def open_select_wav_dialog(self) -> None:
        """Open a file picker and load the chosen file."""
        ret = open_file_dialog(
            title="Select Audio File",
            default_file=str(self._audio) if self._audio else None,
            filetypes={µ("Audio Files (.wav, .wem)", "filetypes"): ["*.wav", "*.wem"]},
        )
        if ret:
            self.set_file(Path(ret))

    def play_pause(self) -> None:
        """Toggle playback; creates the player on first call."""
        if not self._player:
            self._create_player()
            self.regenerate()

        if self._player.playing:
            self._player.pause()
        else:
            if self._player.position >= self._player.duration:
                if self._trim_enabled:
                    pos = self._get_valid_pos(self.get_trims()[0])
                else:
                    pos = 0.0
                dpg.set_value(self._t("progress"), pos)
                dpg.set_value(self._t("progress_axis"), pos)
                self._player.seek(pos)

            self._player.play()
            self._progress_update()

    def _get_wav_path(self) -> Path:
        if self._audio is None:
            return None

        if not self._audio.is_file():
            logger.error(
                µ("Audio {file} is not a file", "log").format(file=self._audio)
            )
            return None

        if self._audio.suffix == ".wem":
            wav = Path(tmp_dir.name) / (self._audio.stem + ".wav")
            if not wav.is_file():
                vgmstream = get_config().locate_vgmstream()
                logger.info(
                    µ("Converting {file} to wav for playback", "log").format(
                        file=self._audio.name
                    )
                )
                wav = wem2wav(Path(vgmstream), self._audio, Path(tmp_dir.name))[0]
            return wav

        if self._audio.suffix == ".wav":
            return self._audio

        logger.error(
            µ("Audio {file} is not a wav or wem file", "log").format(
                file=self._audio.name
            )
        )
        return None

    def _get_valid_pos(self, pos: float, use_trims: bool = True) -> float:
        if self._player:
            if pos < 0:
                pos = self._player.duration + pos

            if self._trim_enabled and use_trims:
                trims = self.get_trims()
                begin = self._get_valid_pos(trims[0], False)
                end = (
                    self._player.duration
                    if trims[1] == 0.0
                    else self._get_valid_pos(trims[1], False)
                )
                min_pos = max(0.0, min(begin, self._player.duration))
                max_pos = min(self._player.duration, max(0.0, end))
            else:
                min_pos = 0.0
                max_pos = self._player.duration

            return max(min_pos, min(pos, max_pos))

        return max(0.0, abs(pos))

    def _create_player(self) -> None:
        if self._player:
            raise ValueError("A player instance already exists")

        wav = self._get_wav_path()
        if not wav or not wav.is_file():
            raise FileNotFoundError()

        self._player = WavPlayer(str(wav))
        self._player.seek(self._player.duration)  # set on first play_pause call

        initial_pos = self.get_trims()[0]
        dpg.set_value(self._t("progress"), initial_pos)
        dpg.set_value(self._t("progress_axis"), initial_pos)

    def _progress_update(self) -> None:
        if not self._player or not self._player.playing:
            return

        if not dpg.does_item_exist(self._t("progress")):
            self._player.stop()
            return

        pos = self._player.position
        loop_start, loop_end, loop_active = self.get_loop_state()

        if loop_active:
            loop_start = self._get_valid_pos(loop_start)
            loop_end = self._get_valid_pos(loop_end)
            if pos >= loop_end:
                pos = loop_start
                self._player.seek(pos)

        # Only repeat the region around the loop point for testing
        if dpg.get_value(self._t("loop_test")):
            if pos < loop_start:
                pos = loop_start
                self._player.seek(pos)
            elif loop_start + 3 <= pos < loop_end - 3:
                pos = loop_end - 3.0
                self._player.seek(pos)

        # Apply trims only when not in loop-test mode
        elif self._trim_enabled:
            trims = self.get_trims()
            if pos < trims[0] or pos >= self._player.duration + trims[1]:
                pos = trims[0]
                self._player.seek(pos)

        self._player.fx_set_volume_rel(self.get_volume_at(pos))
        self._player.fx_set_lowpass(self.get_lowpass_at(pos))
        self._player.fx_set_highpass(self.get_highpass_at(pos))

        dpg.set_value(self._t("progress"), pos)
        dpg.set_value(self._t("progress_axis"), pos)
        dpg.set_value(
            self._t("progress_value"), f"{pos:.03f} / {self._player.duration:.3f}"
        )
        # TODO update every frame if sfx updates don't seem smooth
        dpg.set_frame_callback(dpg.get_frame_count() + 2, self._progress_update)

    # === SFX ===========================================================

    def _interpolate_curve(
        self, points: list[RTPCGraphPoint], pos: float, default: float = 0.0
    ) -> float:
        if not points:
            return default

        # Find the last point whose from_ is <= pos
        p0 = None
        p1 = None
        for i, p in enumerate(points):
            if p.from_ <= pos:
                p0 = p
                p1 = points[i + 1] if i + 1 < len(points) else None
            else:
                break

        if p0 is None:
            return points[0].to  # before first point

        if p1 is None:
            return p0.to  # after last point

        t = (pos - p0.from_) / (p1.from_ - p0.from_)
        return interpolate(p0.interpolation, t, p0.to, p1.to)

    def get_volume_at(self, pos: float) -> float:
        vol_lin = 10 ** (self._interpolate_curve(self.volume, pos, default=0.0) / 20)
        fadein = self._interpolate_curve(self.fadein, pos, default=1.0)
        fadeout = 1.0 - self._interpolate_curve(self.fadeout, pos, default=0.0)
        return vol_lin * fadein * fadeout

    def get_lowpass_at(self, pos: float) -> float:
        return self._interpolate_curve(self.lowpass, pos)

    def get_highpass_at(self, pos: float) -> float:
        return self._interpolate_curve(self.highpass, pos)

    def set_volume(self, volume: float | list[RTPCGraphPoint] = None) -> None:
        if isinstance(volume, (float, int)):
            volume = [RTPCGraphPoint(0.0, volume, CurveInterpolation.Constant)]
        self.volume = volume

    def set_lowpass(self, lowpass: float | list[RTPCGraphPoint] = None) -> None:
        if isinstance(lowpass, (float, int)):
            lowpass = [RTPCGraphPoint(0.0, lowpass, CurveInterpolation.Constant)]
        self.lowpass = lowpass

    def set_highpass(self, highpass: float | list[RTPCGraphPoint] = None) -> None:
        if isinstance(highpass, (float, int)):
            highpass = [RTPCGraphPoint(0.0, highpass, CurveInterpolation.Constant)]
        self.highpass = highpass

    def set_fadein(self, fadein: float | list[RTPCGraphPoint] = None) -> None:
        if isinstance(fadein, (float, int)):
            fadein = [
                RTPCGraphPoint(0.0, 0.0, CurveInterpolation.Linear),
                RTPCGraphPoint(fadein, 1.0, CurveInterpolation.Constant),
            ]
        self.fadein = fadein

    def set_fadeout(self, fadeout: float | list[RTPCGraphPoint] = None) -> None:
        if isinstance(fadeout, (float, int)):
            duration = self._player.duration if self._player else 100
            fadeout = [
                RTPCGraphPoint(duration - fadeout, 0.0, CurveInterpolation.Linear),
                RTPCGraphPoint(duration, 1.0, CurveInterpolation.Constant),
            ]
        self.fadeout = fadeout

    # === Loop markers ==================================================

    def get_loop_state(self) -> tuple[float, float, bool]:
        """Return ``(loop_start, loop_end, enabled)`` in seconds."""
        if not self._loop_markers_enabled:
            return (0.0, 0.0, False)

        start = dpg.get_value(self._t("loop_start"))
        end = dpg.get_value(self._t("loop_end"))
        active = (
            dpg.get_value(self._t("loop_enabled"))
            if dpg.does_item_exist(self._t("loop_enabled"))
            else True
        )
        return (start, end, active)

    def set_loop_state(self, loop_start: float, loop_end: float, enabled: bool) -> None:
        """Set loop marker positions and enabled state programmatically."""
        if not self._loop_markers_enabled:
            raise RuntimeError("loop_markers_enabled is False")

        dpg.set_value(self._t("loop_start"), loop_start)
        dpg.set_value(self._t("loop_end"), loop_end)
        if dpg.does_item_exist(self._t("loop_enabled")):
            dpg.set_value(self._t("loop_enabled"), enabled)
        self._update_loop_widgets()

    def _set_loop_marker_pos(self, sender: str, pos: float, loop_marker: str) -> None:
        pos = self._get_valid_pos(pos, False)
        if loop_marker == "loop_end" and pos == 0.0:
            pos = -0.01

        dpg.set_value(self._t(loop_marker), pos)
        dpg.set_value(self._t(f"{loop_marker}_axis"), pos)

        if self._on_loop_changed:
            loop_start, loop_end, enabled = self.get_loop_state()
            if self._markers_in_ms:
                loop_start *= 1000
                loop_end *= 1000
            self._on_loop_changed(
                self._tag, (loop_start, loop_end, enabled), self._user_data
            )

    def _update_loop_widgets(self) -> None:
        loop_start, loop_end, _ = self.get_loop_state()

        loop_start = self._get_valid_pos(loop_start, False)
        loop_end = self._get_valid_pos(loop_end, False)
        loop_end_viz = self._player.duration if loop_end == 0.0 else loop_end

        loop_start = min(loop_start, loop_end)

        dpg.set_value(self._t("loop_start"), loop_start)
        dpg.set_value(self._t("loop_start_axis"), loop_start)
        dpg.set_value(self._t("loop_start_value"), loop_start)

        dpg.set_value(self._t("loop_end"), loop_end_viz)
        dpg.set_value(self._t("loop_end_axis"), loop_end_viz)
        dpg.set_value(self._t("loop_end_value"), loop_end)

    def _on_loop_marker_moved(self) -> None:
        self._update_loop_widgets()

        if self._on_loop_changed:
            loop_start, loop_end, enabled = self.get_loop_state()
            if self._markers_in_ms:
                loop_start *= 1000
                loop_end *= 1000
            self._on_loop_changed(
                self._tag, (loop_start, loop_end, enabled), self._user_data
            )

    # === Trim markers ==================================================

    def get_trims(self) -> tuple[float, float]:
        """Return ``(begin_trim, end_trim)`` in seconds."""
        if not self._trim_enabled:
            return (0.0, 0.0)

        begin = dpg.get_value(self._t("begin_trim_value"))
        end = dpg.get_value(self._t("end_trim_value"))
        return (begin, end)

    def set_trims(self, begin_trim: float, end_trim: float) -> None:
        """Set trim marker positions programmatically."""
        if not self._trim_enabled:
            raise RuntimeError("trim_enabled is False")

        dpg.set_value(self._t("begin_trim_value"), begin_trim)
        dpg.set_value(self._t("end_trim_value"), end_trim)
        self._update_trim_widgets()

    def set_trim_marker_pos(self, sender: str, pos: float, trim_marker: str) -> None:
        """Set a single trim marker; also usable as a DPG callback."""
        if trim_marker == "begin_trim":
            pos = self._get_valid_pos(pos, False)
            dpg.set_value(self._t("begin_trim"), (-10, -1, pos, 1))
            dpg.set_value(self._t("begin_trim_axis"), pos)
        elif trim_marker == "end_trim":
            if pos == 0.0:
                pos = -0.01
            pos = self._get_valid_pos(pos, False)
            dpg.set_value(self._t("end_trim"), (pos, -1, 1000, 1))
            dpg.set_value(self._t("end_trim_axis"), pos)

        if self._on_trim_marker_changed:
            begin_trim, end_trim = self.get_trims()
            if self._markers_in_ms:
                begin_trim *= 1000
                end_trim *= 1000
            self._on_trim_marker_changed(
                self._tag, (begin_trim, end_trim), self._user_data
            )

    def _update_trim_widgets(self) -> None:
        begin_trim, end_trim = self.get_trims()

        begin_trim = self._get_valid_pos(begin_trim, False)
        end_trim = self._get_valid_pos(end_trim, False)
        end_trim_viz = self._player.duration if end_trim == 0.0 else end_trim

        begin_trim = min(begin_trim, end_trim_viz)

        dpg.set_value(self._t("begin_trim"), (-1000, -1, begin_trim, 1))
        dpg.set_value(self._t("begin_trim_axis"), begin_trim)
        dpg.set_value(self._t("begin_trim_value"), begin_trim)

        dpg.set_value(self._t("end_trim"), (end_trim_viz, -1, 1000, 1))
        dpg.set_value(self._t("end_trim_axis"), end_trim_viz)
        dpg.set_value(self._t("end_trim_value"), end_trim)  # raw value

    def _on_trim_marker_moved(self) -> None:
        # Store raw values in the float widgets
        begin_drag = dpg.get_value(self._t("begin_trim"))[2]
        end_drag = dpg.get_value(self._t("end_trim"))[0]
        dpg.set_value(self._t("begin_trim_value"), begin_drag)
        dpg.set_value(self._t("end_trim_value"), -(self._player.duration - end_drag))

        self._update_trim_widgets()

        if self._on_trim_marker_changed:
            begin_trim, end_trim = self.get_trims()
            if self._markers_in_ms:
                begin_trim *= 1000
                end_trim *= 1000
            self._on_trim_marker_changed(
                self._tag, (begin_trim, end_trim), self._user_data
            )

    # === User markers ==================================================

    def get_user_markers(self) -> dict[int, float]:
        """Return all user marker positions ``{id: pos}`` in seconds."""
        return dict(self._user_markers)

    def get_user_marker_pos(self, mid: Hash, default: float = 0.0) -> float:
        """Return a single marker position by ID or name."""
        if isinstance(mid, str):
            mid = calc_hash(mid)
        return self._user_markers.get(mid, default)

    def _set_user_marker_pos(self, sender: str, pos: float, mid: int) -> None:
        dpg.set_value(self._t(f"marker_{mid}"), pos)
        self._user_markers[mid] = pos
        self._fire_user_markers_changed()

    def _update_user_marker_widget(self, mid: int) -> None:
        pos = dpg.get_value(self._t(f"marker_{mid}"))
        pos = self._get_valid_pos(pos)
        self._user_markers[mid] = pos

        dpg.set_value(self._t(f"marker_{mid}"), pos)
        dpg.set_value(self._t(f"marker_{mid}_value"), pos)
        dpg.set_value(self._t(f"marker_{mid}_axis"), pos)

    def _on_user_markers_moved(self) -> None:
        for mid in self._user_markers:
            self._update_user_marker_widget(mid)
        self._fire_user_markers_changed()

    def _fire_user_markers_changed(self) -> None:
        if not self._on_user_markers_changed:
            return
        markers = (
            {k: v * 1000 for k, v in self._user_markers.items()}
            if self._markers_in_ms
            else dict(self._user_markers)
        )
        self._on_user_markers_changed(self._tag, markers, self._user_data)

    # === Edit dialog ===================================================

    def _on_loop_marker_edit(
        self, sender: str, new_loop_info: tuple[float, float, bool], ud: Any
    ) -> None:
        loop_start, loop_end, _ = new_loop_info
        dpg.set_value(self._t("loop_start"), loop_start)
        dpg.set_value(self._t("loop_end"), loop_end)
        self._on_loop_marker_moved()

    def _on_trim_marker_edit(
        self, sender: str, trims: tuple[float, float], ud: Any
    ) -> None:
        dpg.set_value(self._t("begin_trim"), (-1000, -1, trims[0], 1))
        dpg.set_value(
            self._t("end_trim"), (self._player.duration + trims[1], -1, 1000, 1)
        )
        self._on_trim_marker_moved()

    def _on_user_marker_edit(
        self, sender: str, markers: dict[Hash, float], ud: Any
    ) -> None:
        for mid, pos in markers.items():
            dpg.set_value(self._t(f"marker_{mid}"), pos)
        self._on_user_markers_moved()

    def _open_edit_markers_dialog(self) -> None:
        from yonder.gui.dialogs.edit_markers_dialog import edit_markers_dialog

        dpg.hide_item(self._t("markers_popup"))
        loop_start, loop_end, _ = self.get_loop_state()

        edit_markers_dialog(
            self._audio,
            loop_markers_enabled=self._loop_markers_enabled,
            loop_start=loop_start,
            loop_end=loop_end,
            on_loop_changed=self._on_loop_marker_edit,
            trim_enabled=self._trim_enabled,
            begin_trim=self._begin_trim,
            end_trim=self._end_trim,
            on_trim_marker_changed=self._on_trim_marker_edit,
            user_markers_enabled=self._user_markers_enabled,
            user_markers=self._user_markers,
            on_user_marker_changed=self._on_user_marker_edit,
            markers_in_ms=False,  # already in seconds internally
        )

    # === Rendering =====================================================

    @staticmethod
    def _minmax_envelope(
        signal: np.ndarray, time: np.ndarray, n_buckets: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Downsample by splitting into n_buckets and keeping min+max per bucket.
        Returns (t, y) where len == 2*n_buckets, ready to plot as a filled waveform.
        """
        trim = (len(signal) // n_buckets) * n_buckets
        sig_buckets = signal[:trim].reshape(n_buckets, -1)
        t_buckets = time[:trim].reshape(n_buckets, -1)

        mins = sig_buckets.min(axis=1)
        maxs = sig_buckets.max(axis=1)
        t_mid = t_buckets.mean(axis=1)

        # Interleave: for each bucket emit (t, max) then (t, min) for a
        # continuous envelope trace
        t_out = np.empty(2 * n_buckets)
        y_out = np.empty(2 * n_buckets)
        t_out[0::2] = t_mid
        t_out[1::2] = t_mid
        y_out[0::2] = maxs
        y_out[1::2] = mins

        return t_out, y_out

    def regenerate(self) -> None:
        """Rebuild the waveform plot from the current audio file."""
        dpg.delete_item(self._t("xaxis"), children_only=True)
        
        if not self._get_wav_path():
            return

        if not self._player:
            try:
                self._create_player()
            except FileNotFoundError:
                logger.error(
                    µ("Audio {file} not found", "msg").format(file=self._audio)
                )
                dpg.hide_item(self._t("plot_group"))
                dpg.configure_item(
                    self._t("audio_error"),
                    default_value=µ("Audio {file} not found", "msg").format(
                        file=self._audio.name
                    ),
                    show=True,
                )
                return
            except Exception as e:
                logger.error(µ("Error reading file: {exc}", "log").format(exc=e))
                dpg.hide_item(self._t("plot_group"))
                dpg.configure_item(
                    self._t("audio_error"), default_value=str(e), show=True
                )
                return

        dpg.show_item(self._t("plot_group"))
        dpg.hide_item(self._t("audio_error"))

        # frames is [L, R, L, R, ...] -> shape (n_frames, n_channels)
        samples = self._player.frames
        time = np.linspace(0, self._player.duration, num=self._player.num_frames)

        factors = [1, -1]
        colors = [style.themes.plot_blue, style.themes.plot_red]

        dpg.set_value(self._t("progress_value"), f"0.000 / {self._player.duration:.3f}")

        for i in range(min(self._player.num_channels, 2)):
            signal = samples[:, i].astype(np.float32)
            t_env, y_env = self._minmax_envelope(signal, time, self._max_points // 2)
            y_env = factors[i % 2] * np.abs(y_env)

            dpg.add_line_series(
                t_env.tolist(),
                y_env.tolist(),
                shaded=True,
                no_clip=True,
                tag=self._t(f"channel_{i}"),
                label=f"Ch{i}",
                parent=self._t("xaxis"),
            )
            dpg.bind_item_theme(self._t(f"channel_{i}"), colors[i])

        if self._loop_markers_enabled:
            self._update_loop_widgets()

        if self._user_markers_enabled:
            for mid in self._user_markers:
                self._update_user_marker_widget(mid)

        if self._trim_enabled:
            self._update_trim_widgets()

        dpg.set_axis_limits_constraints(self._t("xaxis"), 0.0, self._player.duration)
        dpg.fit_axis_data(self._t("xaxis"))
        dpg.fit_axis_data(self._t("yaxis"))

    # === DPG callbacks =================================================

    def _on_progress_moved(self, sender: str) -> None:
        pos = dpg.get_value(sender)
        dpg.set_value(self._t("progress_axis"), pos)

        if self._player:
            dpg.set_value(
                self._t("progress_value"), f"{pos:.03f} / {self._player.duration:.3f}"
            )
            self._player.seek(pos)

    # === Build =========================================================

    def _setup_content(self, width: int, height: int) -> None:
        with dpg.group(tag=self._tag, parent=self._parent):
            dpg.add_text(
                "Audio not found",
                color=style.yellow,
                show=False,
                tag=self._t("audio_error"),
            )

            with dpg.group(horizontal=True):
                if self._allow_change_file:
                    dpg.add_input_text(
                        default_value=shorten_path(self._audio) if self._audio else "",
                        enabled=False,
                        readonly=True,
                        tag=self._t("filepath"),
                    )
                    dpg.add_button(
                        label=µ("Browse", "button"),
                        callback=self.open_select_wav_dialog,
                        tag=self._t("browse"),
                    )

                if self._label:
                    dpg.add_text(self._label, color=style.pink.mix(style.white))

                dpg.add_spacer(height=2)

            with dpg.group(tag=self._t("plot_group")):
                # Two linked subplots: a thin marker strip on top, waveform below.
                # Markers must live on a separate plot to appear above the waveform
                # while still sharing the same x-axis range.
                with dpg.subplots(
                    2,
                    1,
                    link_all_x=True,
                    link_all_y=True,
                    row_ratios=[0.0001, 1],
                    width=width,
                    height=height,
                    no_resize=True,
                    no_menus=True,
                    no_title=True,
                ):
                    with dpg.plot(
                        no_title=True,
                        no_menus=True,
                        no_mouse_pos=True,
                        no_inputs=True,
                        no_frame=True,
                        height=1,
                    ):
                        dpg.add_plot_axis(
                            dpg.mvXAxis,
                            label=µ("markers"),
                            opposite=True,
                            no_label=True,
                            no_highlight=True,
                            no_tick_labels=True,
                            no_tick_marks=True,
                            no_initial_fit=True,
                            tag=self._t("marker_axis"),
                        )
                        dpg.add_plot_axis(
                            dpg.mvYAxis,
                            show=False,
                            no_label=True,
                            no_highlight=True,
                            no_tick_labels=True,
                            no_tick_marks=True,
                        )

                        # Playback cursor on marker strip
                        dpg.add_axis_tag(
                            label=" ",
                            default_value=self._loop_start,
                            color=style.light_blue,
                            parent=self._t("marker_axis"),
                            tag=self._t("progress_axis"),
                        )

                        if self._loop_markers_enabled:
                            dpg.add_drag_line(
                                label=µ("loop_start", "marker"),
                                color=style.green,
                                default_value=self._loop_start,
                                callback=self._on_loop_marker_moved,
                                no_inputs=not self._edit_markers_inplace,
                                tag=self._t("loop_start"),
                            )
                            dpg.add_axis_tag(
                                label=µ("L0", "marker"),
                                default_value=self._loop_start,
                                color=style.green,
                                parent=self._t("marker_axis"),
                                tag=self._t("loop_start_axis"),
                            )
                            dpg.add_drag_line(
                                label=µ("loop_end", "marker"),
                                color=style.green,
                                default_value=self._loop_end,
                                callback=self._on_loop_marker_moved,
                                no_inputs=not self._edit_markers_inplace,
                                tag=self._t("loop_end"),
                            )
                            dpg.add_axis_tag(
                                label=µ("L1", "marker"),
                                default_value=self._loop_end,
                                color=style.green,
                                parent=self._t("marker_axis"),
                                tag=self._t("loop_end_axis"),
                            )

                        if self._trim_enabled:
                            dpg.add_drag_rect(
                                label=µ("begin_trim", "marker"),
                                color=style.red,
                                no_fit=True,
                                no_inputs=not self._edit_markers_inplace,
                                callback=self._on_trim_marker_moved,
                                tag=self._t("begin_trim"),
                            )
                            dpg.add_axis_tag(
                                label=µ("T0", "marker"),
                                color=style.red,
                                parent=self._t("marker_axis"),
                                tag=self._t("begin_trim_axis"),
                            )
                            dpg.add_drag_rect(
                                label=µ("end_trim", "marker"),
                                color=style.red,
                                no_fit=True,
                                no_inputs=not self._edit_markers_inplace,
                                callback=self._on_trim_marker_moved,
                                tag=self._t("end_trim"),
                            )
                            dpg.add_axis_tag(
                                label=µ("T1", "marker"),
                                color=style.red,
                                parent=self._t("marker_axis"),
                                tag=self._t("end_trim_axis"),
                            )

                        if self._user_markers_enabled:
                            colorgen = style.HighContrastColorGenerator()
                            for i, (mid, pos) in enumerate(self._user_markers.items()):
                                color = colorgen()
                                marker_label = self._user_marker_labels.get(
                                    mid, f"#{mid}"
                                )
                                dpg.add_drag_line(
                                    label=marker_label,
                                    color=color,
                                    default_value=pos,
                                    no_inputs=not self._edit_markers_inplace,
                                    callback=self._on_user_markers_moved,
                                    tag=self._t(f"marker_{mid}"),
                                    user_data=mid,
                                )
                                dpg.add_axis_tag(
                                    label=µ("m{idx}", "marker"),
                                    default_value=pos,
                                    color=color,
                                    parent=self._t("marker_axis"),
                                    tag=self._t(f"marker_{mid}_axis"),
                                )

                    with dpg.plot(
                        no_title=True,
                        no_menus=True,
                        no_mouse_pos=True,
                        tag=self._t("plot"),
                    ):
                        dpg.add_plot_axis(
                            dpg.mvXAxis,
                            label=µ("amp"),
                            no_label=True,
                            no_highlight=True,
                            tag=self._t("xaxis"),
                        )
                        dpg.add_plot_axis(
                            dpg.mvYAxis,
                            label=µ("time"),
                            no_label=True,
                            no_highlight=True,
                            no_tick_labels=True,
                            no_tick_marks=True,
                            auto_fit=True,
                            tag=self._t("yaxis"),
                        )

                        dpg.add_drag_line(
                            show_label=False,
                            thickness=2,
                            color=style.light_blue,
                            callback=self._on_progress_moved,
                            tag=self._t("progress"),
                        )

            with dpg.group(horizontal=True):
                dpg.add_button(
                    arrow=True,
                    direction=dpg.mvDir_Right,
                    callback=self.play_pause,
                )
                dpg.add_text("|")

                if self._loop_markers_enabled:
                    dpg.add_checkbox(
                        label=µ("Loop"),
                        default_value=True,
                        callback=self._on_loop_marker_moved,
                        tag=self._t("loop_enabled"),
                    )
                    dpg.add_checkbox(
                        label=µ("Test"),
                        default_value=False,
                        tag=self._t("loop_test"),
                    )

                if (
                    self._loop_markers_enabled
                    or self._user_markers_enabled
                    or self._trim_enabled
                ):
                    dpg.add_text("|")
                    if self._edit_markers_inplace:
                        dpg.add_button(
                            label=µ("Markers", "button"),
                            callback=lambda s, a, u: dpg.show_item(
                                self._t("markers_popup")
                            ),
                            tag=self._t("markers"),
                        )
                    else:
                        dpg.add_button(
                            label=µ("Edit", "button"),
                            callback=self._open_edit_markers_dialog,
                            tag=self._t("edit"),
                        )
                    dpg.add_text("|")

                dpg.add_text("0.000 / 0.000", tag=self._t("progress_value"))

        with dpg.window(
            popup=True,
            no_move=True,
            no_title_bar=True,
            no_resize=True,
            tag=self._t("markers_popup"),
            show=False,
        ):
            if self._loop_markers_enabled:
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

            if self._trim_enabled:
                if self._loop_markers_enabled:
                    dpg.add_separator()
                dpg.add_input_float(
                    label=µ("begin_trim", "marker"),
                    default_value=self._begin_trim,
                    min_value=0.0,
                    min_clamped=True,
                    width=130,
                    callback=self.set_trim_marker_pos,
                    user_data="begin_trim",
                    tag=self._t("begin_trim_value"),
                )
                dpg.add_input_float(
                    label=µ("end_trim", "marker"),
                    default_value=-abs(self._end_trim),
                    max_value=0.0,
                    max_clamped=True,
                    width=130,
                    callback=self.set_trim_marker_pos,
                    user_data="end_trim",
                    tag=self._t("end_trim_value"),
                )

            if self._user_markers_enabled:
                if self._loop_markers_enabled or self._trim_enabled:
                    dpg.add_separator()
                # TODO Make this a widget table instead
                for mid, pos in self._user_markers.items():
                    marker_label = self._user_marker_labels.get(mid, f"#{mid}")
                    dpg.add_input_float(
                        label=marker_label,
                        default_value=pos,
                        width=130,
                        callback=self._set_user_marker_pos,
                        user_data=mid,
                        tag=self._t(f"marker_{mid}_value"),
                    )
