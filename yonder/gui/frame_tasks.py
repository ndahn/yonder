from __future__ import annotations
from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder.util import logger


# dpg keeps exactly one callback per frame number and silently drops anything
# else registered for the same frame. Two widgets running an update loop at
# the same interval - a signal preview and the track arranger both following
# their playback, say - starve each other that way, and the one that lost
# looks frozen rather than broken. So the queue lives here and only one real
# frame callback per frame is handed to dpg.
_pending: dict[int, list[Callable[[], None]]] = {}


def call_in_frames(callback: Callable[[], None], frames: int = 2) -> None:
    """Run ``callback`` a few frames from now.

    Drop-in for ``dpg.set_frame_callback(dpg.get_frame_count() + n, cb)`` that
    does not lose callbacks when several land on the same frame. A callback
    that re-registers itself keeps a loop running.

    Parameters
    ----------
    callback : callable
        Called with no arguments. Exceptions are logged, not propagated, so
        one misbehaving task cannot take the others down with it.
    frames : int
        How many frames to wait, at least one.
    """
    target = dpg.get_frame_count() + max(1, frames)
    queue = _pending.get(target)

    if queue is None:
        queue = _pending[target] = []
        # The frame goes through user_data rather than a closure or a partial:
        # dpg reads the callback's __code__ to decide how to call it, which
        # functools.partial does not have
        dpg.set_frame_callback(target, _run, user_data=target)

    queue.append(callback)


def _run(sender: Any, app_data: Any, frame: int) -> None:
    for callback in _pending.pop(frame, ()):
        try:
            callback()
        except Exception as e:
            logger.error(f"Frame task {callback} failed", exc_info=e)


def clear() -> None:
    """Forget every queued task. For shutdown, nothing else should need it."""
    _pending.clear()
