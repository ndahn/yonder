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
    loop_markers_enabled: bool = False,
    loop_start: float = 1.0,
    loop_end: float = -1.0,
    on_loop_changed: Callable[[str, tuple[float, float, bool], Any], None] = None,
    trim_enabled: bool = False,
    begin_trim: float = 0.0,
    end_trim: float = 0.0,
    on_trim_marker_changed: Callable[[str, tuple[float, float], Any], None] = None,
    user_markers_enabled: bool = False,
    user_markers: list[tuple[str, float, tuple[int, int, int]]] = None,
    on_user_marker_changed: Callable[[str, tuple[str, float], Any], None] = None,
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

    # PLAYBACK

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

    def get_valid_pos(pos: float) -> float:
        if player:
            if pos < 0:
                pos = player.duration - pos
            return max(0.0, min(pos, player.duration))

        return max(0.0, abs(pos))

    def create_player() -> None:
        nonlocal player

        if player:
            raise ValueError("A player instance already exists")

        wav = get_wav_path()
        if not wav or not wav.is_file():
            raise FileNotFoundError()

        player = WavPlayer(str(wav))
        # Will be set on first call to on_play_pause
        player.seek(player.duration)

        initial_pos = get_trims()[0]
        dpg.set_value(f"{tag}_progress", initial_pos)
        dpg.set_value(f"{tag}_progress_axis", initial_pos)

    def on_play_pause() -> None:
        nonlocal player

        if not player:
            create_player()
            regenerate()

        if player.playing:
            player.pause()
        else:
            if player.position >= player.duration:
                if trim_enabled:
                    pos = get_valid_pos(get_trims()[0])
                    dpg.set_value(f"{tag}_progress", pos)
                    dpg.set_value(f"{tag}_progress_axis", pos)
                else:
                    pos = 0.0

                player.seek(pos)

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
        trims = get_trims()
        loop_start, loop_end, loop_active = get_loop_state()
        
        if loop_active:
            # A bit of a weird interaction between loop points and trims, 
            # but seems to always use the inner ones
            if trim_enabled:
                loop_start = max(loop_start, trims[0])
                loop_end = min(loop_end, player.duration - trims[1])

            if pos >= loop_end:
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
        # Use trimming only when not in loop testing mode
        elif trim_enabled:
            if pos < trims[0]:
                player.seek(trims[0])
            elif pos >= player.duration + trims[1]:
                player.seek(trims[0])

        dpg.set_value(f"{tag}_progress", pos)
        dpg.set_value(f"{tag}_progress_value", f"{pos:.03f} / {player.duration:.3f}")
        dpg.set_value(f"{tag}_progress_axis", pos)
        dpg.set_frame_callback(dpg.get_frame_count() + 2, progress_update)

    # LOOP MARKERS

    def get_loop_state() -> tuple[float, float, bool]:
        start = dpg.get_value(f"{tag}_loop_start")
        end = dpg.get_value(f"{tag}_loop_end")

        if dpg.does_item_exist(f"{tag}_loop_enabled"):
            active = dpg.get_value(f"{tag}_loop_enabled")
        else:
            active = True

        return (start, end, active)

    def set_loop_marker_pos(sender: str, pos: float, loop_marker: str) -> None:
        dpg.set_value(f"{tag}_{loop_marker}", pos)
        if on_loop_changed:
            on_loop_changed(tag, get_loop_state(), user_data)

    def update_loop_widgets() -> None:
        loop_start, loop_end, active = get_loop_state()
        loop_start = get_valid_pos(loop_start)
        loop_end = get_valid_pos(loop_end)

        # Can't have overlap
        loop_start = min(loop_start, loop_end)

        dpg.set_value(f"{tag}_loop_start", loop_start)
        dpg.set_value(f"{tag}_loop_start_value", loop_start)
        dpg.set_value(f"{tag}_loop_start_axis", loop_start)

        dpg.set_value(f"{tag}_loop_end", loop_end)
        dpg.set_value(f"{tag}_loop_end_value", loop_end)
        dpg.set_value(f"{tag}_loop_end_axis", loop_end)

    def on_loop_marker_moved() -> None:
        update_loop_widgets()

        if on_loop_changed:
            on_loop_changed(tag, get_loop_state(), user_data)

    # TRIMS

    def get_trims() -> tuple[float, float]:
        if not trim_enabled:
            return (0.0, 0.0)

        begin_trim = dpg.get_value(f"{tag}_begin_trim_value")
        end_trim = dpg.get_value(f"{tag}_end_trim_value")
        return (begin_trim, end_trim)

    def set_trim_marker_pos(sender: str, pos: float, trim_marker: str) -> None:
        if trim_marker == "begin_trim":
            dpg.set_value(f"{tag}_begin_trim", (-10, -1, pos, 1))
        if trim_marker == "end_trim":
            dpg.set_value(f"{tag}_end_trim", (pos, -1, 1000, 1))

        if on_trim_marker_changed:
            on_trim_marker_changed(tag, get_trims(), user_data)

    def update_trim_widgets() -> None:
        begin_trim, end_trim = get_trims()
        begin_trim = get_valid_pos(begin_trim)

        # end trim is always negative
        end_trim_pos = get_valid_pos(player.duration + end_trim)

        # Can't have overlap
        begin_trim = min(begin_trim, end_trim_pos)

        dpg.set_value(f"{tag}_begin_trim", (-1000, -1, begin_trim, 1))
        dpg.set_value(f"{tag}_begin_trim_value", begin_trim)
        dpg.set_value(f"{tag}_begin_trim_axis", begin_trim)

        dpg.set_value(f"{tag}_end_trim", (end_trim_pos, -1, 1000, 1))
        dpg.set_value(f"{tag}_end_trim_value", end_trim)  # raw value
        dpg.set_value(f"{tag}_end_trim_axis", end_trim_pos)

    def on_trim_marker_moved() -> None:
        # Storing the value in the float widget instead
        begin_drag = dpg.get_value(f"{tag}_begin_trim")[2]
        end_drag = dpg.get_value(f"{tag}_end_trim")[0]
        dpg.set_value(f"{tag}_begin_trim_value", begin_drag)
        dpg.set_value(f"{tag}_end_trim_value", -(player.duration - end_drag))

        update_trim_widgets()

        if on_trim_marker_changed:
            on_trim_marker_changed(tag, get_trims(), user_data)

    # USER MARKERS

    def set_user_marker_pos(sender: str, pos: float, marker: str) -> None:
        dpg.set_value(f"{tag}_marker_{marker}", pos)
        if on_user_marker_changed:
            on_user_marker_changed(tag, (marker, pos), user_data)

    def update_user_marker_widget(marker: str) -> None:
        marker_drag = f"{tag}_marker_{marker}"
        pos = dpg.get_value(marker_drag)
        pos = get_valid_pos(pos)

        dpg.set_value(marker_drag, pos)
        dpg.set_value(f"{tag}_marker_{marker}_value", pos)
        dpg.set_value(f"{tag}_marker_{marker}_axis", pos)

    def on_user_marker_moved(marker: str) -> None:
        update_user_marker_widget(marker)

        if on_user_marker_changed:
            on_user_marker_changed(tag, (marker, pos), user_data)

    # EDIT DIALOG

    def on_loop_marker_edit(
        sender: str, new_loop_info: tuple[float, float, bool], user_data: Any
    ) -> None:
        loop_start, loop_end, _ = new_loop_info
        dpg.set_value(f"{tag}_loop_start", loop_start)
        dpg.set_value(f"{tag}_loop_end", loop_end)
        on_loop_marker_moved()

    def on_trim_marker_edit(
        sender: str, trims: tuple[float, float], user_data: Any
    ) -> None:
        dpg.set_value(f"{tag}_begin_trim", (-1000, -1, trims[0], 1))
        dpg.set_value(f"{tag}_end_trim", (trims[1], -1, 1000, 1))
        on_trim_marker_moved()

    def on_user_marker_edit(
        sender: str, marker: tuple[str, float], user_data: Any
    ) -> None:
        name, pos = marker
        dpg.set_value(f"{tag}_marker_{name}", pos)
        on_user_marker_moved(name)

    def open_edit_markers_dialog() -> None:
        from yonder.gui.dialogs.edit_markers_dialog import edit_markers_dialog

        dpg.hide_item(f"{tag}_markers_popup")
        loop_start, loop_end, _ = get_loop_state()

        edit_markers_dialog(
            audio,
            loop_markers_enabled=loop_markers_enabled,
            loop_start=loop_start,
            loop_end=loop_end,
            on_loop_changed=on_loop_marker_edit,
            trim_enabled=trim_enabled,
            begin_trim=begin_trim,
            end_trim=end_trim,
            on_trim_marker_changed=on_trim_marker_edit,
            user_markers_enabled=user_markers_enabled,
            user_markers=user_markers,
            on_user_marker_changed=on_user_marker_edit,
        )

    # RENDERING

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
        dpg.delete_item(f"{tag}_yaxis", children_only=True)

        if not player:
            try:
                create_player()
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

        # frames is [L, R, L, R, ...] -> shape (n_frames, n_channels)
        samples = player.frames
        time = np.linspace(0, player.duration, num=player.num_frames)

        factors = [1, -1]
        colors = [style.themes.plot_blue, style.themes.plot_red]

        # Numerical progress display
        dpg.set_value(f"{tag}_progress_value", f"0.000 / {player.duration:.3f}")

        # If there are multiple channels we only want the first two (usually FL and FR)
        for i in range(min(player.num_channels, 2)):
            signal = samples[:, i].astype(np.float32)
            t_env, y_env = minmax_envelope(signal, time, n_buckets=max_points // 2)
            y_env = factors[i % 2] * np.abs(y_env)

            dpg.add_line_series(
                t_env.tolist(),
                y_env.tolist(),
                shaded=True,
                no_clip=True,
                tag=f"{tag}_channel_{i}",
                label=f"Ch{i}",
                parent=f"{tag}_xaxis",
            )
            dpg.bind_item_theme(f"{tag}_channel_{i}", colors[i])

        if loop_markers_enabled:
            update_loop_widgets()

        if user_markers_enabled:
            for marker, _, _ in user_markers:
                update_user_marker_widget(marker)

        if trim_enabled:
            update_trim_widgets()

        dpg.set_axis_limits_constraints(f"{tag}_xaxis", 0.0, player.duration)
        dpg.fit_axis_data(f"{tag}_xaxis")
        dpg.fit_axis_data(f"{tag}_yaxis")

    with dpg.group(tag=tag):
        dpg.add_text(
            "Audio not found", color=style.yellow, show=False, tag=f"{tag}_audio_error"
        )

        with dpg.group(horizontal=True):
            if allow_change_file:
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
                dpg.add_text(label, color=style.pink.mix(style.white))

            dpg.add_spacer(height=2)

        with dpg.group(tag=f"{tag}_plot_group", parent=parent):
            # We want the markers to be at the top, but placing them on e.g. x-axis 2 will make 
            # their position independent from x-axis 1 where the plot is. So we make two plots,
            # one for the markers with no visible plot area, and one for the series itself, then
            # link their x-axis.
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
                        label="markers",
                        opposite=True,
                        no_label=True,
                        no_highlight=True,
                        no_tick_labels=True,
                        no_tick_marks=True,
                        no_initial_fit=True,
                        tag=f"{tag}_marker_axis",
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
                    tag=f"{tag}_plot",
                ):
                    dpg.add_plot_axis(
                        dpg.mvXAxis,
                        label="amp",
                        no_label=True,
                        no_highlight=True,
                        tag=f"{tag}_xaxis",
                    )
                    dpg.add_plot_axis(
                        dpg.mvYAxis,
                        label="time",
                        no_label=True,
                        no_highlight=True,
                        no_tick_labels=True,
                        no_tick_marks=True,
                        auto_fit=True,
                        tag=f"{tag}_yaxis",
                    )

                    # Playback marker
                    dpg.add_drag_line(
                        show_label=False,
                        thickness=2,
                        color=style.light_blue,
                        callback=on_progress_update,
                        tag=f"{tag}_progress",
                    )
                    dpg.add_axis_tag(
                        label=" ",
                        default_value=loop_start,
                        color=style.light_blue,
                        parent=f"{tag}_marker_axis",
                        tag=f"{tag}_progress_axis",
                    )

                    # Loop markers
                    if loop_markers_enabled:
                        dpg.add_drag_line(
                            label="loop_start",
                            color=style.green,
                            default_value=loop_start,
                            callback=on_loop_marker_moved,
                            no_inputs=not edit_markers_inplace,
                            tag=f"{tag}_loop_start",
                        )
                        dpg.add_axis_tag(
                            label="L0",
                            default_value=loop_start,
                            color=style.green,
                            parent=f"{tag}_marker_axis",
                            tag=f"{tag}_loop_start_axis",
                        )
                        dpg.add_drag_line(
                            label="loop_end",
                            color=style.green,
                            default_value=loop_end,
                            callback=on_loop_marker_moved,
                            no_inputs=not edit_markers_inplace,
                            tag=f"{tag}_loop_end",
                        )
                        dpg.add_axis_tag(
                            label="L1",
                            default_value=loop_end,
                            color=style.green,
                            parent=f"{tag}_marker_axis",
                            tag=f"{tag}_loop_end_axis",
                        )

                    # Trimming
                    if trim_enabled:
                        dpg.add_drag_rect(
                            label="begin_trim",
                            color=style.red,
                            no_fit=True,
                            no_inputs=not edit_markers_inplace,
                            callback=on_trim_marker_moved,
                            tag=f"{tag}_begin_trim",
                        )
                        dpg.add_axis_tag(
                            label="T0",
                            color=style.red,
                            parent=f"{tag}_marker_axis",
                            tag=f"{tag}_begin_trim_axis",
                        )
                        dpg.add_drag_rect(
                            label="end_trim",
                            color=style.red,
                            no_fit=True,
                            no_inputs=not edit_markers_inplace,
                            callback=on_trim_marker_moved,
                            tag=f"{tag}_end_trim",
                        )
                        dpg.add_axis_tag(
                            label="T1",
                            color=style.red,
                            parent=f"{tag}_marker_axis",
                            tag=f"{tag}_end_trim_axis",
                        )

                    # User markers
                    if user_markers_enabled:
                        for i, (marker, pos, color) in enumerate(user_markers):
                            dpg.add_drag_line(
                                label=marker,
                                color=color,
                                default_value=pos,
                                no_inputs=not edit_markers_inplace,
                                callback=on_user_marker_moved,
                                tag=f"{tag}_marker_{marker}",
                            )
                            dpg.add_axis_tag(
                                label=f"m{i}",
                                default_value=pos,
                                color=color,
                                parent=f"{tag}_marker_axis",
                                tag=f"{tag}_marker{marker}_axis",
                            )

            with dpg.group(horizontal=True):
                dpg.add_button(
                    arrow=True,
                    direction=dpg.mvDir_Right,
                    callback=on_play_pause,
                )

                if loop_markers_enabled:
                    dpg.add_checkbox(
                        label="Loop",
                        default_value=True,
                        callback=on_loop_marker_moved,
                        tag=f"{tag}_loop_enabled",
                    )
                    dpg.add_checkbox(
                        label="Test",
                        default_value=False,
                        tag=f"{tag}_loop_test",
                    )

                if loop_markers_enabled or user_markers_enabled or trim_enabled:
                    dpg.add_text("|")
                    if edit_markers_inplace:
                        dpg.add_button(
                            label="Markers",
                            callback=lambda s, a, u: dpg.show_item(
                                f"{tag}_markers_popup"
                            ),
                        )
                    else:
                        dpg.add_button(
                            label="Edit",
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
                default_value=loop_start,
                width=130,
                callback=set_loop_marker_pos,
                user_data="loop_start",
                tag=f"{tag}_loop_start_value",
            )
            dpg.add_input_float(
                label="loop_end",
                default_value=loop_end,
                width=130,
                callback=set_loop_marker_pos,
                user_data="loop_end",
                tag=f"{tag}_loop_end_value",
            )

        if trim_enabled:
            if loop_markers_enabled:
                dpg.add_separator()

            dpg.add_input_float(
                label="begin_trim",
                default_value=begin_trim,
                min_value=0.0,
                min_clamped=True,
                width=130,
                callback=set_trim_marker_pos,
                user_data="begin_trim",
                tag=f"{tag}_begin_trim_value",
            )
            dpg.add_input_float(
                label="end_trim",
                default_value=-abs(end_trim),
                max_value=0.0,
                max_clamped=True,
                width=130,
                callback=set_trim_marker_pos,
                user_data="end_trim",
                tag=f"{tag}_end_trim_value",
            )

        if user_markers_enabled:
            if loop_markers_enabled or trim_enabled:
                dpg.add_separator()

            # TODO Make this a widget table instead
            for marker, pos, _ in user_markers:
                dpg.add_input_float(
                    label=marker,
                    default_value=pos,
                    width=130,
                    callback=set_user_marker_pos,
                    user_data=marker,
                    tag=f"{tag}_marker_{marker}_value",
                )

    if initial_file:
        regenerate()

    return tag
