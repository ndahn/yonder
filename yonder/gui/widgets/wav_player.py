from typing import Any, Callable
from pathlib import Path
import numpy as np

from dearpygui import dearpygui as dpg

from yonder.hash import calc_hash, lookup_name
from yonder.util import logger
from yonder.gui.config import get_config
from yonder.wem import wem2wav
from yonder.player import WavPlayer
from yonder.gui import style
from yonder.gui.helpers import tmp_dir, shorten_path
from yonder.gui.dialogs.file_dialog import open_file_dialog


class add_wav_player:
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
        user_markers: dict[int | str, float] = None,
        on_user_markers_changed: Callable[
            [str, dict[int | str, float], Any], None
        ] = None,
        edit_markers_inplace: bool = False,
        max_points: int = 5000,
        markers_in_ms: bool = True,
        width: int = -1,
        height: int = 100,
        tag: str = 0,
        parent: str = 0,
        user_data: Any = None,
    ) -> None:
        if not tag:
            tag = dpg.generate_uuid()

        if not allow_change_file and not initial_file:
            raise ValueError("allow_change_path is False and no initial_file provided")

        self.tag = tag
        self.label = label
        self.allow_change_file = allow_change_file
        self.show_filepath = show_filepath
        self.on_file_changed = on_file_changed
        self.loop_markers_enabled = loop_markers_enabled
        self.on_loop_changed = on_loop_changed
        self.trim_enabled = trim_enabled
        self.on_trim_marker_changed = on_trim_marker_changed
        self.user_markers_enabled = user_markers_enabled
        self.on_user_markers_changed = on_user_markers_changed
        self.edit_markers_inplace = edit_markers_inplace
        self.max_points = max_points
        self.markers_in_ms = markers_in_ms
        self.width = width
        self.height = height
        self.parent = parent
        self.user_data = user_data

        self.audio: Path = initial_file
        self.player: WavPlayer = None
        self.user_markers: dict[int, float] = {}
        self.user_marker_labels: dict[int, str] = {}

        if user_markers:
            for mid, pos in user_markers:
                if isinstance(mid, str):
                    label = mid
                    mid = calc_hash(mid)
                else:
                    label = lookup_name(mid, f"#{mid}")

                self.user_markers[mid] = pos
                self.user_marker_labels[mid] = label

        if markers_in_ms:
            loop_start /= 1000
            loop_end /= 1000
            begin_trim /= 1000
            end_trim /= 1000
            self.user_markers = {k: v / 1000 for k, v in self.user_markers.items()}

        self.loop_start = loop_start
        self.loop_end = loop_end
        self.begin_trim = begin_trim
        self.end_trim = end_trim

        self._setup_content()

        if initial_file:
            self.regenerate()

    def _t(self, suffix: str) -> str:
        """Return a namespaced dpg tag."""
        return f"{self.tag}_{suffix}"

    # -- PLAYBACK -------------------------------------------------

    def select_file(self) -> None:
        ret = open_file_dialog(
            title="Select Audio File",
            default_file=str(self.audio) if self.audio else None,
            filetypes={"Audio Files (.wav, .wem)": ["*.wav", "*.wem"]},
        )
        if not ret:
            return

        path = Path(ret).absolute()
        if path == self.audio:
            return

        if self.on_file_changed:
            self.on_file_changed(self.tag, path, self.user_data)

        if self.player:
            self.player.stop()
            self.player = None

        self.audio = path
        path_str = shorten_path(path, 40) if self.show_filepath else path.stem
        dpg.set_value(self._t("filepath"), path_str)
        self.regenerate()

    def _get_wav_path(self) -> Path:
        if self.audio is None or not self.audio.is_file():
            logger.error(f"Audio {self.audio} does not exist")
            return None

        if self.audio.name.endswith(".wem"):
            wav = Path(tmp_dir.name) / (self.audio.stem + ".wav")
            if not wav.is_file():
                vgmstream = get_config().locate_vgmstream()
                logger.info(f"Converting {self.audio} to wav for playback")
                wav = wem2wav(Path(vgmstream), self.audio, Path(tmp_dir.name))[0]
            return wav

        if self.audio.name.endswith(".wav"):
            return self.audio

        logger.error(f"Audio must be a wav or wem file ({self.audio})")
        return None

    def _get_valid_pos(self, pos: float, use_trims: bool = True) -> float:
        if self.player:
            if pos < 0:
                pos = self.player.duration + pos

            if self.trim_enabled and use_trims:
                trims = self.get_trims()
                begin = self._get_valid_pos(trims[0], False)
                end = (
                    self.player.duration
                    if trims[1] == 0.0
                    else self._get_valid_pos(trims[1], False)
                )
                min_pos = max(0.0, min(begin, self.player.duration))
                max_pos = min(self.player.duration, max(0.0, end))
            else:
                min_pos = 0.0
                max_pos = self.player.duration

            return max(min_pos, min(pos, max_pos))

        return max(0.0, abs(pos))

    def _create_player(self) -> None:
        if self.player:
            raise ValueError("A player instance already exists")

        wav = self._get_wav_path()
        if not wav or not wav.is_file():
            raise FileNotFoundError()

        self.player = WavPlayer(str(wav))
        # Will be set on first call to on_play_pause
        self.player.seek(self.player.duration)

        initial_pos = self.get_trims()[0]
        dpg.set_value(self._t("progress"), initial_pos)
        dpg.set_value(self._t("progress_axis"), initial_pos)

    def play_pause(self) -> None:
        if not self.player:
            self._create_player()
            self.regenerate()

        if self.player.playing:
            self.player.pause()
        else:
            if self.player.position >= self.player.duration:
                if self.trim_enabled:
                    pos = self._get_valid_pos(self.get_trims()[0])
                    dpg.set_value(self._t("progress"), pos)
                    dpg.set_value(self._t("progress_axis"), pos)
                else:
                    pos = 0.0

                self.player.seek(pos)

            self.player.play()
            self._progress_update()

    def _on_progress_moved(self, sender: str) -> None:
        pos = dpg.get_value(sender)
        dpg.set_value(self._t("progress_axis"), pos)

        if self.player:
            dpg.set_value(
                self._t("progress_value"), f"{pos:.03f} / {self.player.duration:.3f}"
            )
            self.player.seek(pos)

    def _progress_update(self) -> None:
        if not self.player or not self.player.playing:
            return

        # In case the player widget got destroyed
        if not dpg.does_item_exist(self._t("progress")):
            self.player.stop()
            return

        pos = self.player.position
        loop_start, loop_end, loop_active = self.get_loop_state()

        if loop_active:
            loop_start = self._get_valid_pos(loop_start)
            loop_end = self._get_valid_pos(loop_end)
            if pos >= loop_end:
                pos = loop_start
                self.player.seek(pos)

        # Only repeat the part around the loop point for testing
        if dpg.get_value(self._t("loop_test")):
            if pos < loop_start:
                pos = loop_start
                self.player.seek(pos)
            elif pos >= loop_start + 3 and pos < loop_end - 3:
                pos = loop_end - 3.0
                self.player.seek(pos)
        # Use trimming only when not in loop testing mode
        elif self.trim_enabled:
            trims = self.get_trims()
            if pos < trims[0]:
                self.player.seek(trims[0])
            elif pos >= self.player.duration + trims[1]:
                self.player.seek(trims[0])

        dpg.set_value(self._t("progress"), pos)
        dpg.set_value(self._t("progress_axis"), pos)
        dpg.set_value(
            self._t("progress_value"), f"{pos:.03f} / {self.player.duration:.3f}"
        )
        dpg.set_frame_callback(dpg.get_frame_count() + 2, self._progress_update)

    # -- LOOP MARKERS -------------------------------------------------

    def get_loop_state(self) -> tuple[float, float, bool]:
        if not self.loop_markers_enabled:
            return (0.0, 0.0, False)

        start = dpg.get_value(self._t("loop_start"))
        end = dpg.get_value(self._t("loop_end"))

        if dpg.does_item_exist(self._t("loop_enabled")):
            active = dpg.get_value(self._t("loop_enabled"))
        else:
            active = True

        return (start, end, active)

    def _set_loop_marker_pos(self, sender: str, pos: float, loop_marker: str) -> None:
        pos = self._get_valid_pos(pos, False)
        if loop_marker == "loop_end" and pos == 0.0:
            pos = -0.01

        dpg.set_value(self._t(loop_marker), pos)
        dpg.set_value(self._t(f"{loop_marker}_axis"), pos)

        if self.on_loop_changed:
            loop_start, loop_end, enabled = self.get_loop_state()
            if self.markers_in_ms:
                loop_start *= 1000
                loop_end *= 1000

            self.on_loop_changed(
                self.tag, (loop_start, loop_end, enabled), self.user_data
            )

    def _update_loop_widgets(self) -> None:
        loop_start, loop_end, _ = self.get_loop_state()

        loop_start = self._get_valid_pos(loop_start, False)
        loop_end = self._get_valid_pos(loop_end, False)
        loop_end_viz = self.player.duration if loop_end == 0.0 else loop_end

        # Can't have overlap
        loop_start = min(loop_start, loop_end)

        dpg.set_value(self._t("loop_start"), loop_start)
        dpg.set_value(self._t("loop_start_axis"), loop_start)
        dpg.set_value(self._t("loop_start_value"), loop_start)

        dpg.set_value(self._t("loop_end"), loop_end_viz)
        dpg.set_value(self._t("loop_end_axis"), loop_end_viz)
        dpg.set_value(self._t("loop_end_value"), loop_end)

    def _on_loop_marker_moved(self) -> None:
        self._update_loop_widgets()

        if self.on_loop_changed:
            loop_start, loop_end, enabled = self.get_loop_state()
            if self.markers_in_ms:
                loop_start *= 1000
                loop_end *= 1000

            self.on_loop_changed(
                self.tag, (loop_start, loop_end, enabled), self.user_data
            )

    # -- TRIMS -------------------------------------------------

    def get_trims(self) -> tuple[float, float]:
        if not self.trim_enabled:
            return (0.0, 0.0)

        begin = dpg.get_value(self._t("begin_trim_value"))
        end = dpg.get_value(self._t("end_trim_value"))
        return (begin, end)

    def set_trim_marker_pos(self, sender: str, pos: float, trim_marker: str) -> None:
        if trim_marker == "begin_trim":
            pos = self._get_valid_pos(pos, False)
            dpg.set_value(self._t("begin_trim"), (-10, -1, pos, 1))
            dpg.set_value(self._t("begin_trim_axis"), pos)
        if trim_marker == "end_trim":
            if pos == 0.0:
                pos = -0.01
            pos = self._get_valid_pos(pos, False)
            dpg.set_value(self._t("end_trim"), (pos, -1, 1000, 1))
            dpg.set_value(self._t("end_trim_axis"), pos)

        if self.on_trim_marker_changed:
            begin_trim, end_trim = self.get_trims()
            if self.markers_in_ms:
                begin_trim *= 1000
                end_trim *= 1000

            self.on_trim_marker_changed(
                self.tag, (begin_trim, end_trim), self.user_data
            )

    def _update_trim_widgets(self) -> None:
        begin_trim, end_trim = self.get_trims()

        begin_trim = self._get_valid_pos(begin_trim, False)
        end_trim = self._get_valid_pos(end_trim, False)
        end_trim_viz = self.player.duration if end_trim == 0.0 else end_trim

        # Can't have overlap
        begin_trim = min(begin_trim, end_trim_viz)

        dpg.set_value(self._t("begin_trim"), (-1000, -1, begin_trim, 1))
        dpg.set_value(self._t("begin_trim_axis"), begin_trim)
        dpg.set_value(self._t("begin_trim_value"), begin_trim)

        dpg.set_value(self._t("end_trim"), (end_trim_viz, -1, 1000, 1))
        dpg.set_value(self._t("end_trim_axis"), end_trim_viz)
        dpg.set_value(self._t("end_trim_value"), end_trim)  # raw value

    def _on_trim_marker_moved(self) -> None:
        # Storing the value in the float widget instead
        begin_drag = dpg.get_value(self._t("begin_trim"))[2]
        end_drag = dpg.get_value(self._t("end_trim"))[0]
        dpg.set_value(self._t("begin_trim_value"), begin_drag)
        dpg.set_value(self._t("end_trim_value"), -(self.player.duration - end_drag))

        self._update_trim_widgets()

        if self.on_trim_marker_changed:
            begin_trim, end_trim = self.get_trims()
            if self.markers_in_ms:
                begin_trim *= 1000
                end_trim *= 1000

            self.on_trim_marker_changed(
                self.tag, (begin_trim, end_trim), self.user_data
            )

    # -- USER MARKERS -------------------------------------------------

    def get_user_marker_pos(self, mid: int | str, default: float = 0.0) -> float:
        if isinstance(mid, str):
            mid = calc_hash(mid)

        return self.user_markers.get(mid, default)

    def _set_user_marker_pos(self, sender: str, pos: float, marker: str) -> None:
        dpg.set_value(self._t(f"marker_{marker}"), pos)
        self.user_markers[marker] = pos

        if self.on_user_markers_changed:
            markers = (
                {k: v * 1000 for k, v in self.user_markers}
                if self.markers_in_ms
                else self.user_markers
            )
            self.on_user_markers_changed(self.tag, markers, self.user_data)

    def _update_user_marker_widget(self, marker: str) -> None:
        marker_drag = self._t(f"marker_{marker}")
        pos = dpg.get_value(marker_drag)
        pos = self._get_valid_pos(pos)
        self.user_markers[marker] = pos

        dpg.set_value(marker_drag, pos)
        dpg.set_value(self._t(f"marker_{marker}_value"), pos)
        dpg.set_value(self._t(f"marker_{marker}_axis"), pos)

    def _on_user_markers_moved(self) -> None:
        for marker in self.user_markers.keys():
            self._update_user_marker_widget(marker)

        if self.on_user_markers_changed:
            markers = (
                {k: v * 1000 for k, v in self.user_markers}
                if self.markers_in_ms
                else self.user_markers
            )
            self.on_user_markers_changed(self.tag, markers, self.user_data)

    # -- EDIT DIALOG -------------------------------------------------

    def _on_loop_marker_edit(
        self, sender: str, new_loop_info: tuple[float, float, bool], user_data: Any
    ) -> None:
        loop_start, loop_end, _ = new_loop_info
        dpg.set_value(self._t("loop_start"), loop_start)
        dpg.set_value(self._t("loop_end"), loop_end)
        self._on_loop_marker_moved()

    def _on_trim_marker_edit(
        self, sender: str, trims: tuple[float, float], user_data: Any
    ) -> None:
        dpg.set_value(self._t("begin_trim"), (-1000, -1, trims[0], 1))
        dpg.set_value(
            self._t("end_trim"), (self.player.duration + trims[1], -1, 1000, 1)
        )
        self._on_trim_marker_moved()

    def _on_user_marker_edit(
        self, sender: str, markers: dict[int | str, float], user_data: Any
    ) -> None:
        for name, pos in markers.items():
            dpg.set_value(self._t(f"marker_{name}"), pos)

        self._on_user_markers_moved()

    def _open_edit_markers_dialog(self) -> None:
        from yonder.gui.dialogs.edit_markers_dialog import edit_markers_dialog

        dpg.hide_item(self._t("markers_popup"))
        loop_start, loop_end, _ = self.get_loop_state()

        edit_markers_dialog(
            self.audio,
            loop_markers_enabled=self.loop_markers_enabled,
            loop_start=loop_start,
            loop_end=loop_end,
            on_loop_changed=self._on_loop_marker_edit,
            trim_enabled=self.trim_enabled,
            begin_trim=self.begin_trim,
            end_trim=self.end_trim,
            on_trim_marker_changed=self._on_trim_marker_edit,
            user_markers_enabled=self.user_markers_enabled,
            user_markers=self.user_markers,
            on_user_marker_changed=self._on_user_marker_edit,
            markers_in_ms=False,  # already converted to seconds
        )

    # -- RENDERING -------------------------------------------------

    @staticmethod
    def _minmax_envelope(
        signal: np.ndarray, time: np.ndarray, n_buckets: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Downsample by splitting into n_buckets and keeping min+max per bucket.
        Returns (t, y) where len == 2*n_buckets, ready to plot as a filled waveform.
        """
        # Trim to a multiple of n_buckets for clean reshaping
        trim = (len(signal) // n_buckets) * n_buckets
        sig_buckets = signal[:trim].reshape(n_buckets, -1)
        t_buckets = time[:trim].reshape(n_buckets, -1)

        mins = sig_buckets.min(axis=1)
        maxs = sig_buckets.max(axis=1)
        # Use the midpoint time of each bucket
        t_mid = t_buckets.mean(axis=1)

        # Interleave: for each bucket emit (t, max) then (t, min)
        # This gives a continuous line that traces the envelope
        t_out = np.empty(2 * n_buckets)
        y_out = np.empty(2 * n_buckets)
        t_out[0::2] = t_mid
        t_out[1::2] = t_mid
        y_out[0::2] = maxs
        y_out[1::2] = mins

        return t_out, y_out

    def regenerate(self) -> None:
        dpg.delete_item(self._t("yaxis"), children_only=True)

        if not self.player:
            try:
                self._create_player()
            except FileNotFoundError:
                logger.error(f"Audio {self.audio} not found")
                dpg.hide_item(self._t("plot_group"))
                dpg.configure_item(
                    self._t("audio_error"),
                    default_value=f"Audio {self.audio.name} not found",
                    show=True,
                )
                return
            except Exception as e:
                logger.error(f"Error reading file: {e}")
                dpg.hide_item(self._t("plot_group"))
                dpg.configure_item(
                    self._t("audio_error"), default_value=str(e), show=True
                )
                return

        dpg.show_item(self._t("plot_group"))
        dpg.hide_item(self._t("audio_error"))

        # frames is [L, R, L, R, ...] -> shape (n_frames, n_channels)
        samples = self.player.frames
        time = np.linspace(0, self.player.duration, num=self.player.num_frames)

        factors = [1, -1]
        colors = [style.themes.plot_blue, style.themes.plot_red]

        # Numerical progress display
        dpg.set_value(self._t("progress_value"), f"0.000 / {self.player.duration:.3f}")

        # If there are multiple channels we only want the first two (usually FL and FR)
        for i in range(min(self.player.num_channels, 2)):
            signal = samples[:, i].astype(np.float32)
            t_env, y_env = self._minmax_envelope(
                signal, time, n_buckets=self.max_points // 2
            )
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

        if self.loop_markers_enabled:
            self._update_loop_widgets()

        if self.user_markers_enabled:
            for marker in self.user_markers.keys():
                self._update_user_marker_widget(marker)

        if self.trim_enabled:
            self._update_trim_widgets()

        dpg.set_axis_limits_constraints(self._t("xaxis"), 0.0, self.player.duration)
        dpg.fit_axis_data(self._t("xaxis"))
        dpg.fit_axis_data(self._t("yaxis"))

    # -- UI BUILD -------------------------------------------------

    def _setup_content(self) -> None:
        with dpg.group(tag=self.tag):
            dpg.add_text(
                "Audio not found",
                color=style.yellow,
                show=False,
                tag=self._t("audio_error"),
            )

            with dpg.group(horizontal=True):
                if self.allow_change_file:
                    dpg.add_input_text(
                        default_value=shorten_path(self.audio) if self.audio else "",
                        enabled=False,
                        readonly=True,
                        tag=self._t("filepath"),
                    )
                    dpg.add_button(label="Browse", callback=self.select_file)

                if self.label:
                    dpg.add_text(self.label, color=style.pink.mix(style.white))

                dpg.add_spacer(height=2)

            with dpg.group(tag=self._t("plot_group"), parent=self.parent):
                # We want the markers to be at the top, but placing them on e.g. x-axis 2 will
                # make their position independent from x-axis 1 where the plot is. So we make
                # two plots, one for the markers with no visible plot area, and one for the
                # series itself, then link their x-axis.
                with dpg.subplots(
                    2,
                    1,
                    link_all_x=True,
                    link_all_y=True,
                    row_ratios=[0.0001, 1],
                    width=self.width,
                    height=self.height,
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
                            label="markers",
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

                    with dpg.plot(
                        no_title=True,
                        no_menus=True,
                        no_mouse_pos=True,
                        tag=self._t("plot"),
                    ):
                        dpg.add_plot_axis(
                            dpg.mvXAxis,
                            label="amp",
                            no_label=True,
                            no_highlight=True,
                            tag=self._t("xaxis"),
                        )
                        dpg.add_plot_axis(
                            dpg.mvYAxis,
                            label="time",
                            no_label=True,
                            no_highlight=True,
                            no_tick_labels=True,
                            no_tick_marks=True,
                            auto_fit=True,
                            tag=self._t("yaxis"),
                        )

                        # Playback marker
                        dpg.add_drag_line(
                            show_label=False,
                            thickness=2,
                            color=style.light_blue,
                            callback=self._on_progress_moved,
                            tag=self._t("progress"),
                        )
                        dpg.add_axis_tag(
                            label=" ",
                            default_value=self.loop_start,
                            color=style.light_blue,
                            parent=self._t("marker_axis"),
                            tag=self._t("progress_axis"),
                        )

                        # Loop markers
                        if self.loop_markers_enabled:
                            dpg.add_drag_line(
                                label="loop_start",
                                color=style.green,
                                default_value=self.loop_start,
                                callback=self._on_loop_marker_moved,
                                no_inputs=not self.edit_markers_inplace,
                                tag=self._t("loop_start"),
                            )
                            dpg.add_axis_tag(
                                label="L0",
                                default_value=self.loop_start,
                                color=style.green,
                                parent=self._t("marker_axis"),
                                tag=self._t("loop_start_axis"),
                            )
                            dpg.add_drag_line(
                                label="loop_end",
                                color=style.green,
                                default_value=self.loop_end,
                                callback=self._on_loop_marker_moved,
                                no_inputs=not self.edit_markers_inplace,
                                tag=self._t("loop_end"),
                            )
                            dpg.add_axis_tag(
                                label="L1",
                                default_value=self.loop_end,
                                color=style.green,
                                parent=self._t("marker_axis"),
                                tag=self._t("loop_end_axis"),
                            )

                        # Trimming
                        if self.trim_enabled:
                            dpg.add_drag_rect(
                                label="begin_trim",
                                color=style.red,
                                no_fit=True,
                                no_inputs=not self.edit_markers_inplace,
                                callback=self._on_trim_marker_moved,
                                tag=self._t("begin_trim"),
                            )
                            dpg.add_axis_tag(
                                label="T0",
                                color=style.red,
                                parent=self._t("marker_axis"),
                                tag=self._t("begin_trim_axis"),
                            )
                            dpg.add_drag_rect(
                                label="end_trim",
                                color=style.red,
                                no_fit=True,
                                no_inputs=not self.edit_markers_inplace,
                                callback=self._on_trim_marker_moved,
                                tag=self._t("end_trim"),
                            )
                            dpg.add_axis_tag(
                                label="T1",
                                color=style.red,
                                parent=self._t("marker_axis"),
                                tag=self._t("end_trim_axis"),
                            )

                        # User markers
                        if self.user_markers_enabled:
                            colorgen = style.HighContrastColorGenerator()

                            for i, (mid, pos) in enumerate(self.user_markers.items()):
                                color = colorgen()
                                label = self.user_marker_labels.get(mid, f"#{mid}")
                                dpg.add_drag_line(
                                    label=label,
                                    color=color,
                                    default_value=pos,
                                    no_inputs=not self.edit_markers_inplace,
                                    callback=self._on_user_markers_moved,
                                    tag=self._t(f"marker_{mid}"),
                                    user_data=mid,
                                )
                                dpg.add_axis_tag(
                                    label=f"m{i}",
                                    default_value=pos,
                                    color=color,
                                    parent=self._t("marker_axis"),
                                    tag=self._t(f"marker_{mid}_axis"),
                                )

            with dpg.group(horizontal=True):
                dpg.add_button(
                    arrow=True,
                    direction=dpg.mvDir_Right,
                    callback=self.play_pause,
                )

                dpg.add_text("|")
                if self.loop_markers_enabled:
                    dpg.add_checkbox(
                        label="Loop",
                        default_value=True,
                        callback=self._on_loop_marker_moved,
                        tag=self._t("loop_enabled"),
                    )
                    dpg.add_checkbox(
                        label="Test",
                        default_value=False,
                        tag=self._t("loop_test"),
                    )

                if (
                    self.loop_markers_enabled
                    or self.user_markers_enabled
                    or self.trim_enabled
                ):
                    dpg.add_text("|")
                    if self.edit_markers_inplace:
                        dpg.add_button(
                            label="Markers",
                            callback=lambda s, a, u: dpg.show_item(
                                self._t("markers_popup")
                            ),
                        )
                    else:
                        dpg.add_button(
                            label="Edit", callback=self._open_edit_markers_dialog
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
            if self.loop_markers_enabled:
                dpg.add_input_float(
                    label="loop_start",
                    default_value=self.loop_start,
                    width=130,
                    callback=self._set_loop_marker_pos,
                    user_data="loop_start",
                    tag=self._t("loop_start_value"),
                )
                dpg.add_input_float(
                    label="loop_end",
                    default_value=self.loop_end,
                    width=130,
                    callback=self._set_loop_marker_pos,
                    user_data="loop_end",
                    tag=self._t("loop_end_value"),
                )

            if self.trim_enabled:
                if self.loop_markers_enabled:
                    dpg.add_separator()

                dpg.add_input_float(
                    label="begin_trim",
                    default_value=self.begin_trim,
                    min_value=0.0,
                    min_clamped=True,
                    width=130,
                    callback=self.set_trim_marker_pos,
                    user_data="begin_trim",
                    tag=self._t("begin_trim_value"),
                )
                dpg.add_input_float(
                    label="end_trim",
                    default_value=-abs(self.end_trim),
                    max_value=0.0,
                    max_clamped=True,
                    width=130,
                    callback=self.set_trim_marker_pos,
                    user_data="end_trim",
                    tag=self._t("end_trim_value"),
                )

            if self.user_markers_enabled:
                if self.loop_markers_enabled or self.trim_enabled:
                    dpg.add_separator()

                # TODO Make this a widget table instead
                for mid, pos in self.user_markers.items():
                    label = self.user_marker_labels.get(mid, f"#{mid}")
                    dpg.add_input_float(
                        label=label,
                        default_value=pos,
                        width=130,
                        callback=self._set_user_marker_pos,
                        user_data=mid,
                        tag=self._t(f"marker_{mid}_value"),
                    )
