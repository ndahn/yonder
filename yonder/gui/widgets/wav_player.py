from typing import Any, Callable
from pathlib import Path
import wave
import numpy as np

from dearpygui import dearpygui as dpg

from yonder.util import logger
from yonder.gui.config import get_config
from yonder.wem import wem2wav
from yonder.player import WavPlayer
from yonder.gui import style
from yonder.gui.helpers import tmp_dir, shorten_path
from yonder.gui.dialogs.file_dialog import open_file_dialog


def add_wav_player(
    initial_file: Path,
    *,
    label: str = "",
    allow_change_file: bool = True,
    show_filepath: bool = False,
    on_file_changed: Callable[[str, Path, Any], None] = None,
    user_markers_enabled: bool = False,
    user_markers: list[tuple[str, float, tuple[int, int, int]]] = None,
    on_user_marker_changed: Callable[[str, tuple[str, float], Any], None] = None,
    loop_markers_enabled: bool = False,
    on_loop_changed: Callable[[str, tuple[float, float, bool], Any], None] = None,
    loop_start: float = 1.0,
    loop_end: float = -1.0,
    edit_markers_inplace: bool = False,
    max_points: int = 5000,
    width: int = -1,
    height: int = 100,
    tag: str = 0,
    parent: str = 0,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    if not allow_change_file and not initial_file:
        raise ValueError("allow_change_path is False and no initial_file provided")

    audio: Path = initial_file
    player: WavPlayer = None

    def select_file() -> None:
        nonlocal audio, player

        ret = open_file_dialog(
            title="Select Audio File",
            default_file=str(audio) if audio else None,
            filetypes={"Audio Files (.wav, .wem)": ["*.wav", "*.wem"]},
        )
        if ret:
            path = Path(ret).resolve()
            if path == audio:
                return

            if on_file_changed:
                on_file_changed(tag, Path(ret), user_data)

            if player:
                player.stop()
                player = None

            audio = path
            path_str = shorten_path(path, 40) if show_filepath else path.stem
            dpg.set_value(f"{tag}_filepath", path_str)
            regenerate()

    def get_wav_path() -> Path:
        if audio is None or not audio.is_file():
            logger.error(f"Audio {audio} does not exist")
            return None

        if audio.name.endswith(".wem"):
            wav = Path(tmp_dir.name) / (audio.stem + ".wav")
            if not wav.is_file():
                vgmstream = get_config().locate_vgmstream()
                logger.info(f"Converting {audio} to wav for playback")
                wav = wem2wav(Path(vgmstream), audio, Path(tmp_dir.name))[0]
            return wav

        elif audio.name.endswith(".wav"):
            return audio

        else:
            logger.error(f"Audio must be a wav or wem file ({audio})")
            return None

    def on_play_pause() -> None:
        nonlocal player, audio

        if not player:
            wav = get_wav_path()
            if not wav:
                return

            player = WavPlayer(str(wav))
            dpg.set_value(f"{tag}_progress", 0.0)
            regenerate()

        if player.playing:
            player.pause()
        else:
            if player.position >= player.duration:
                player.seek(0.0)

            player.play()
            progress_update()

    def on_progress_update(sender: str) -> None:
        if player:
            player.seek(dpg.get_value(sender))

    def progress_update() -> None:
        if not player or not player.playing:
            return

        # In case the player widget got destroyed
        if not dpg.does_item_exist(f"{tag}_progress"):
            player.stop()
            return

        pos = player.position
        loop_start, loop_end, loop_active = get_loop_state()
        if loop_active and pos >= loop_end:
            pos = loop_start
            player.seek(pos)

        # Only repeat the part around the loop point for testing
        if dpg.get_value(f"{tag}_loop_test"):
            if pos < loop_start:
                pos = loop_start
                player.seek(pos)
            elif pos >= loop_start + 3 and pos < loop_end - 3:
                pos = loop_end - 3.0
                player.seek(pos)

        dpg.set_value(f"{tag}_progress", pos)
        dpg.set_value(f"{tag}_progress_value", f"{pos:.03f} / {player.duration:.3f}")
        dpg.set_frame_callback(dpg.get_frame_count() + 2, progress_update)

    def get_loop_state() -> tuple[float, float, bool]:
        start = dpg.get_value(f"{tag}_loop_start")
        end = dpg.get_value(f"{tag}_loop_end")

        if dpg.does_item_exist(f"{tag}_loop_enabled"):
            active = dpg.get_value(f"{tag}_loop_enabled")
        else:
            active = True

        return (start, end, active)

    def on_looppoint_edit(
        sender: str, new_loop_info: tuple[float, float, bool], user_data: Any
    ) -> None:
        loop_start, loop_end, enabled = new_loop_info
        dpg.set_value(f"{tag}_loop_start", loop_start)
        dpg.set_value(f"{tag}_loop_end", loop_end)

        if dpg.does_item_exist(f"{tag}_loop_enabled"):
            dpg.set_value(f"{tag}_loop_enabled")

        update_loop_widgets()

    def set_loop_marker_pos(sender: str, pos: float, loop_marker: str) -> None:
        dpg.set_value(f"{tag}_{loop_marker}", pos)
        if on_loop_changed:
            on_loop_changed(tag, get_loop_state(), user_data)

    def update_loop_widgets() -> None:
        loop_start, loop_end, active = get_loop_state()

        # Loop start must be before loop end and vv
        loop_start = max(0.0, min(loop_start, loop_end))
        dpg.set_value(f"{tag}_loop_start", loop_start)
        if dpg.does_item_exist(f"{tag}_loop_start_value"):
            dpg.set_value(f"{tag}_loop_start_value", loop_start)

        dur = player.duration if player else np.finfo(np.float32).max
        loop_end = min(dur, max(loop_end, loop_start))
        if dpg.does_item_exist(f"{tag}_loop_end_value"):
            dpg.set_value(f"{tag}_loop_end_value", loop_end)

        if on_loop_changed:
            on_loop_changed(tag, (loop_start, loop_end, active), user_data)

    def set_user_marker_pos(sender: str, pos: float, marker: str) -> None:
        dpg.set_value(f"{tag}_marker_{marker}", pos)
        if on_user_marker_changed:
            on_user_marker_changed(tag, (marker, pos), user_data)

    def on_user_marker_moved(sender: str) -> None:
        if not player:
            return

        pos = dpg.get_value(sender)
        pos = max(0.0, min(pos, player.duration))
        dpg.set_value(sender, pos)

        marker = dpg.get_item_label(sender)
        dpg.set_value(f"{tag}_marker_{marker}_value", pos)
        if on_user_marker_changed:
            on_user_marker_changed(tag, (marker, pos), user_data)

    def open_edit_markers_dialog() -> None:
        from yonder.gui.dialogs.edit_markers_dialog import edit_looppoints_dialog

        loop_start, loop_end, _ = get_loop_state()
        edit_looppoints_dialog(audio, loop_start, loop_end, on_looppoint_edit)

    def minmax_envelope(
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

    def regenerate() -> None:
        dpg.delete_item(f"{tag}_axis_y", children_only=True)

        try:
            filepath = get_wav_path()
            if not filepath or not filepath.is_file():
                raise FileNotFoundError()

            with wave.open(str(filepath), "r") as f:
                n_channels = f.getnchannels()
                framerate = f.getframerate()
                frames = np.frombuffer(f.readframes(-1), dtype=np.int16)
        except FileNotFoundError:
            logger.error(f"Audio {audio} not found")
            dpg.hide_item(f"{tag}_plot_group")
            dpg.configure_item(
                f"{tag}_audio_error",
                default_value=f"Audio {audio.name} not found",
                show=True,
            )
            return
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            dpg.hide_item(f"{tag}_plot_group")
            dpg.configure_item(
                f"{tag}_audio_error",
                default_value=str(e),
                show=True,
            )
            return

        dpg.show_item(f"{tag}_plot_group")
        dpg.hide_item(f"{tag}_audio_error")

        # Deinterleave channels in one reshape — no Python loop
        # frames is [L, R, L, R, ...] → shape (n_frames, n_channels)
        samples = frames.reshape(-1, n_channels)

        n_frames = samples.shape[0]
        duration = n_frames / framerate
        time = np.linspace(0, duration, num=n_frames)

        factors = [1, -1]
        colors = [style.themes.plot_blue, style.themes.plot_red]

        # Numerical progress display
        dpg.set_value(f"{tag}_progress_value", f"0.000 / {duration:.3f}")

        # If there are multiple channels we only want the first two (usually FL and FR)
        for i in range(min(n_channels, 2)):
            signal = samples[:, i].astype(np.float32)
            t_env, y_env = minmax_envelope(signal, time, n_buckets=max_points // 2)
            y_env = factors[i % 2] * np.abs(y_env)

            dpg.add_line_series(
                t_env.tolist(),
                y_env.tolist(),
                shaded=True,
                tag=f"{tag}_channel_{i}",
                label=f"Ch{i}",
                parent=f"{tag}_axis_y",
            )
            dpg.bind_item_theme(f"{tag}_channel_{i}", colors[i])

        if loop_markers_enabled:
            loop_start, loop_end, _ = get_loop_state()

            if loop_start < 0:
                loop_start = max(0.0, duration + loop_start)
            else:
                loop_start = min(loop_start, duration)

            if loop_end < 0:
                loop_end = max((0.0, loop_start, duration + loop_end))
            else:
                loop_end = min(loop_end, duration)

            dpg.set_value(f"{tag}_loop_start", loop_start)
            dpg.set_value(f"{tag}_loop_end", loop_end)

            if edit_markers_inplace:
                dpg.configure_item(
                    f"{tag}_loop_start_value",
                    default_value=loop_start,
                    max_value=duration,
                )
                dpg.configure_item(
                    f"{tag}_loop_end_value", default_value=loop_end, max_value=duration
                )

        if user_markers_enabled:
            for marker, _, _ in user_markers:
                mpos = dpg.get_value(f"{tag}_marker_{marker}")
                mpos = max(0.0, min(mpos, duration))
                dpg.set_value(f"{tag}_marker_{marker}", mpos)

                if edit_markers_inplace:
                    dpg.configure_item(
                        f"{tag}_marker_{marker}_value",
                        default_value=mpos,
                        max_value=duration,
                    )

        dpg.set_axis_limits_constraints(f"{tag}_axis_x", 0.0, duration)
        dpg.fit_axis_data(f"{tag}_axis_x")
        dpg.fit_axis_data(f"{tag}_axis_y")

    with dpg.group(tag=tag):
        dpg.add_text(
            "Audio not found", color=style.yellow, show=False, tag=f"{tag}_audio_error"
        )

        if allow_change_file:
            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    default_value=shorten_path(initial_file) if initial_file else "",
                    enabled=False,
                    readonly=True,
                    tag=f"{tag}_filepath",
                )
                dpg.add_button(
                    label="Browse",
                    callback=select_file,
                )
                if label:
                    dpg.add_text(label)

        with dpg.group(tag=f"{tag}_plot_group"):
            with dpg.plot(
                width=width,
                height=height,
                no_title=True,
                no_menus=True,
                no_mouse_pos=True,
                tag=f"{tag}_plot",
                parent=parent,
            ):
                dpg.add_plot_axis(
                    dpg.mvXAxis,
                    label="x",
                    no_label=True,
                    no_highlight=True,
                    tag=f"{tag}_axis_x",
                )
                dpg.add_plot_axis(
                    dpg.mvYAxis,
                    label="y",
                    no_label=True,
                    no_highlight=True,
                    no_tick_labels=True,
                    no_tick_marks=True,
                    auto_fit=True,
                    tag=f"{tag}_axis_y",
                )

                # Playback marker
                dpg.add_drag_line(
                    show_label=False,
                    thickness=2,
                    color=style.red,
                    callback=on_progress_update,
                    tag=f"{tag}_progress",
                )

                # Loop markers
                if loop_markers_enabled:
                    dpg.add_drag_line(
                        label="loop_start",
                        color=style.green,
                        default_value=loop_start,
                        tag=f"{tag}_loop_start",
                        callback=update_loop_widgets,
                        no_inputs=not edit_markers_inplace,
                    )
                    dpg.add_drag_line(
                        label="loop_end",
                        color=style.light_green,
                        default_value=loop_end,
                        tag=f"{tag}_loop_end",
                        callback=update_loop_widgets,
                        no_inputs=not edit_markers_inplace,
                    )

                # User markers
                if user_markers_enabled:
                    for marker, pos, color in user_markers:
                        dpg.add_drag_line(
                            label=marker,
                            color=color,
                            default_value=pos,
                            no_inputs=not edit_markers_inplace,
                            tag=f"{tag}_marker_{marker}",
                            callback=on_user_marker_moved,
                        )

            with dpg.group(horizontal=True):
                dpg.add_button(
                    arrow=True,
                    direction=dpg.mvDir_Right,
                    callback=on_play_pause,
                )

                if loop_markers_enabled or user_markers_enabled:
                    dpg.add_text("|")
                    if edit_markers_inplace:
                        dpg.add_button(
                            label="Markers",
                            callback=lambda s, a, u: dpg.show_item(
                                f"{tag}_markers_popup"
                            ),
                        )
                        if loop_markers_enabled:
                            dpg.add_checkbox(
                                label="Loop",
                                default_value=True,
                                tag=f"{tag}_loop_enabled",
                                callback=update_loop_widgets,
                            )
                            dpg.add_checkbox(
                                label="Test",
                                default_value=False,
                                tag=f"{tag}_loop_test",
                            )
                        if user_markers_enabled:
                            # TODO add something to add new user markers here
                            pass
                    else:
                        dpg.add_button(
                            label="Markers",
                            callback=open_edit_markers_dialog,
                        )

                dpg.add_text("|")
                dpg.add_text("0.000 / 0.000", tag=f"{tag}_progress_value")

    with dpg.window(
        popup=True,
        no_move=True,
        no_title_bar=True,
        no_resize=True,
        tag=f"{tag}_markers_popup",
        show=False,
    ):
        if loop_markers_enabled:
            dpg.add_input_float(
                label="loop_start",
                default_value=1.0,
                width=100,
                callback=set_loop_marker_pos,
                user_data="loop_start",
                tag=f"{tag}_loop_start_value",
            )
            dpg.add_input_float(
                label="loop_end",
                default_value=1.0,
                width=100,
                callback=set_loop_marker_pos,
                user_data="loop_end",
                tag=f"{tag}_loop_end_value",
            )
            if user_markers:
                dpg.add_separator()

        if user_markers:
            for marker, pos, _ in user_markers:
                dpg.add_input_float(
                    label=marker,
                    default_value=pos,
                    width=100,
                    callback=set_user_marker_pos,
                    user_data=marker,
                    tag=f"{tag}_marker_{marker}_value",
                )

    if initial_file:
        regenerate()

    return tag
