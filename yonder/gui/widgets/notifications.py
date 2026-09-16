from typing import Any
from logging import getLevelName
import time
from dearpygui import dearpygui as dpg

from yonder.gui import style


_level_to_color = {
    "CRITICAL": style.purple,
    "ERROR": style.red,
    "WARNING": style.yellow,
    "INFO": style.light_blue,
    "DEBUG": style.light_grey,
    "NOTSET": style.light_grey,
}


class _NotificationManager:
    def __init__(self, timeout: float = 3.0, max_message_len: int = 250):
        self._window_cache: list[int] = []
        self._active_notifications: dict[int, int] = {}
        self._timeout = timeout
        self._max_message_len = max_message_len
        self._handler_registry = None

    def get_color(self, severity: int | str) -> style.RGBA:
        if isinstance(severity, int):
            severity = getLevelName(severity)

        return _level_to_color.get(severity, style.light_blue)

    def add_notification(self, message: str, severity: int | str) -> None:
        color = self.get_color(severity)
        if len(message) > self._max_message_len:
            message = message[:self._max_message_len] + "..."

        if not self._handler_registry:
            self._handler_registry = dpg.add_handler_registry()

        try:
            # Using a cache helps with the problem where dpg doesn't know the window size
            # until several frames later
            window = self._window_cache.pop()
            dpg.configure_item(
                f"{window}_text", default_value=message, color=color, show=True
            )
        except IndexError:
            with dpg.window(
                autosize=True,
                no_title_bar=True,
                no_move=True,
                no_close=True,
                no_resize=True,
                no_saved_settings=True,
                min_size=(300, 10),
                pos=(9000, 9000),
            ) as window:
                with dpg.group(width=-1):
                    dpg.add_text(message, wrap=400, color=color, tag=f"{window}_text")

            dpg.bind_item_theme(window, style.themes.notification_frame)
            dpg.add_mouse_click_handler(
                callback=self._on_notification_clicked,
                user_data=window,
                parent=self._handler_registry,
            )

        now = time.time()
        self._active_notifications[window] = now
        self._rearrange()
        # We need another rearrange pass to adjust for the changed size
        dpg.set_frame_callback(dpg.get_frame_count() + 3, self._rearrange)
        # Fallback to hide the message eventually
        dpg.set_frame_callback(
            dpg.get_frame_count() + int(self._timeout * 60), self._rearrange
        )

    def _on_notification_clicked(self, sender: str, app_data: Any, tag: int) -> None:
        if dpg.is_item_focused(tag):
            self._active_notifications[tag] = 0
            self._rearrange()

    def _rearrange(self) -> None:
        try:
            dpg.split_frame()
        except Exception:  # noqa: BLE001
            pass

        # dicts keep their insertion order
        notifications = list(self._active_notifications.items())
        finished: set[int] = set()
        now = time.time()
        vpw = dpg.get_viewport_width()
        vph = dpg.get_viewport_height()

        pad_x = 40
        pad_y = 70
        gap_y = 8
        offset = 0

        with dpg.mutex():
            for tag, timestamp in reversed(notifications):
                if now >= timestamp + self._timeout:
                    dpg.hide_item(tag)
                    finished.add(tag)
                else:
                    dpg.show_item(tag)
                    w = dpg.get_item_width(tag)
                    h = dpg.get_item_height(tag)
                    dpg.configure_item(
                        tag, pos=(vpw - pad_x - w, vph - pad_y - offset - h), show=True
                    )
                    offset += h + gap_y

            self._window_cache.extend(finished)
            self._active_notifications = {
                n: f for n, f in self._active_notifications.items() if n not in finished
            }


global_notification_man = _NotificationManager()
