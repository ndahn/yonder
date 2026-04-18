from typing import Any, Callable
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder.gui import style
from yonder.gui.widgets import DpgItem, add_wav_player


class edit_markers_dialog(DpgItem):
    """A dialog wrapping ``add_wav_player`` for in-place marker editing.

    When ``accept_on_okay=True`` marker changes are buffered internally and
    only forwarded to the outer callbacks when the user confirms. Otherwise
    each marker drag fires the callbacks immediately and no Okay/Cancel
    buttons are shown.

    Parameters
    ----------
    sound : Path
        Audio file loaded into the player (not changeable inside the dialog).
    title : str
        Window title bar label.
    accept_on_okay : bool
        Buffer changes until Okay; show Okay/Cancel buttons when True.
    loop_markers_enabled : bool
        Enable loop start/end markers on the player.
    loop_start : float
        Initial loop start position.
    loop_end : float
        Initial loop end position.
    on_loop_changed : callable, optional
        Fired as ``on_loop_changed(tag, (start, end, enabled), user_data)``.
    user_markers_enabled : bool
        Enable user-defined named markers.
    user_markers : dict, optional
        Initial user marker positions.
    on_user_marker_changed : callable, optional
        Fired as ``on_user_marker_changed(tag, markers, user_data)``.
    trim_enabled : bool
        Enable begin/end trim markers.
    begin_trim : float
        Initial begin trim position.
    end_trim : float
        Initial end trim position.
    on_trim_marker_changed : callable, optional
        Fired as ``on_trim_marker_changed(tag, (begin, end), user_data)``.
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
        title: str = "Edit Loop Markers",
        accept_on_okay: bool = False,
        loop_markers_enabled: bool = False,
        loop_start: float = 1.0,
        loop_end: float = -1.0,
        on_loop_changed: Callable[[str, tuple[float, float, bool], Any], None] = None,
        user_markers_enabled: bool = False,
        user_markers: dict[int | str, float] = None,
        on_user_marker_changed: Callable[
            [str, dict[int | str, float], Any], None
        ] = None,
        trim_enabled: bool = False,
        begin_trim: float = 0.0,
        end_trim: float = 0.0,
        on_trim_marker_changed: Callable[[str, tuple[float, float], Any], None] = None,
        markers_in_ms: bool = True,
        tag: int | str = None,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag if tag else dpg.generate_uuid())

        self._accept_on_okay = accept_on_okay
        self._loop_markers_enabled = loop_markers_enabled
        self._user_markers_enabled = user_markers_enabled
        self._trim_enabled = trim_enabled
        self._on_loop_changed = on_loop_changed
        self._on_user_marker_changed = on_user_marker_changed
        self._on_trim_marker_changed = on_trim_marker_changed
        self._user_data = user_data

        # Buffered state used when accept_on_okay=True
        self._loop_info: tuple[float, float, bool] = (loop_start, loop_end, True)
        self._user_markers: dict[int | str, float] = (
            dict(user_markers) if user_markers else {}
        )
        self._trims: tuple[float, float] = (begin_trim, end_trim)

        self._window: int | str = None

        self._build(
            title, sound, loop_start, loop_end, begin_trim, end_trim, markers_in_ms
        )

    # === Build =========================================================

    def _build(
        self,
        title: str,
        sound: Path,
        loop_start: float,
        loop_end: float,
        begin_trim: float,
        end_trim: float,
        markers_in_ms: bool,
    ) -> None:
        with dpg.window(
            label=title,
            width=700,
            height=350,
            autosize=False,
            no_saved_settings=True,
            tag=self._tag,
            on_close=lambda: dpg.delete_item(self._window),
        ) as self._window:
            dpg.add_spacer(height=10)

            add_wav_player(
                sound,
                allow_change_file=False,
                edit_markers_inplace=True,
                loop_markers_enabled=self._loop_markers_enabled,
                loop_start=loop_start,
                loop_end=loop_end,
                on_loop_changed=self._dlg_on_loop_changed,
                user_markers_enabled=self._user_markers_enabled,
                user_markers=self._user_markers,
                on_user_markers_changed=self._dlg_on_user_marker_changed,
                trim_enabled=self._trim_enabled,
                begin_trim=begin_trim,
                end_trim=end_trim,
                on_trim_marker_changed=self._dlg_on_trim_marker_changed,
                markers_in_ms=markers_in_ms,
                max_points=10000,
                width=-1,
                height=-60,
            )

            dpg.add_separator()
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            if self._accept_on_okay:
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Okay",
                        callback=self._on_okay,
                        tag=self._t("button_okay"),
                    )
                    dpg.add_button(
                        label="Cancel",
                        callback=lambda: dpg.delete_item(self._window),
                    )

    # === DPG callbacks =================================================

    def _dlg_on_loop_changed(
        self, sender: str, info: tuple[float, float, bool], cb_user_data: Any
    ) -> None:
        if self._accept_on_okay:
            self._loop_info = info
        elif self._on_loop_changed:
            self._on_loop_changed(self._tag, info, self._user_data)

    def _dlg_on_user_marker_changed(
        self, sender: str, info: tuple[int, float], cb_user_data: Any
    ) -> None:
        if self._accept_on_okay:
            self._user_markers[info[0]] = info[1]
        elif self._on_user_marker_changed:
            self._on_user_marker_changed(self._tag, info, self._user_data)

    def _dlg_on_trim_marker_changed(
        self, sender: str, info: tuple[float, float], cb_user_data: Any
    ) -> None:
        if self._accept_on_okay:
            self._trims = info
        elif self._on_trim_marker_changed:
            self._on_trim_marker_changed(self._tag, info, self._user_data)

    def _on_okay(self) -> None:
        if self._loop_markers_enabled and self._on_loop_changed:
            self._on_loop_changed(self._tag, self._loop_info, self._user_data)
        if self._user_markers_enabled and self._on_user_marker_changed:
            self._on_user_marker_changed(self._tag, self._user_markers, self._user_data)
        if self._trim_enabled and self._on_trim_marker_changed:
            self._on_trim_marker_changed(self._tag, self._trims, self._user_data)
        dpg.delete_item(self._window)

    # === Public ========================================================

    def show_message(self, msg: str = None, color: style.Color = style.red) -> None:
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
