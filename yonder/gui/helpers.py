from __future__ import annotations
import sys
import os
from typing import Any, Iterable
from pathlib import Path
import shutil
import tempfile
import atexit
from copy import deepcopy
import subprocess
from dearpygui import dearpygui as dpg

from yonder.util import logger
from yonder.types.base_types import RTPCGraphPoint
from yonder.enums import CurveInterpolation
from yonder.gui.localization import µ
from yonder.gui import style


url_regex = r"https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)"

_tmp_dir = Path(tempfile.gettempdir()).absolute() / "yonder"
atexit.register(shutil.rmtree, _tmp_dir)
logger.info(f"Temporary files will be stored in {_tmp_dir}")


def get_temp_dir() -> Path:
    _tmp_dir.mkdir(parents=True, exist_ok=True)
    return _tmp_dir


def estimate_drawn_text_size(
    textlen: int,
    num_lines: int = 1,
    font_size: int = 12,
    scale: float = 1.0,
    margin: int = 5,
) -> tuple[int, int]:
    # 6.5 for 12, around 5.3 for 10?
    len_est_factor = -0.7 + 0.6 * font_size
    len_est = len_est_factor * textlen

    w = (len_est + margin * 2) * scale
    h = (font_size * num_lines + margin * 2) * scale
    return w, h


def center_window(window: str, parent: str = None) -> None:
    if parent:
        dpos = dpg.get_item_pos(parent)
        dsize = dpg.get_item_rect_size(parent)
    else:
        dpos = (0.0, 0.0)
        dsize = (dpg.get_viewport_width(), dpg.get_viewport_height())

    psize = dpg.get_item_rect_size(window)

    dpg.set_item_pos(
        window,
        (
            dpos[0] + (dsize[0] - psize[0]) / 2,
            dpos[1] + (dsize[1] - psize[1]) / 2,
        ),
    )


def shorten_path(path: str | Path, maxlen: int = 30) -> str:
    if not path:
        return ""

    parts = Path(path).parts
    short = parts[-1]

    for p in reversed(parts[:-1]):
        short = Path(p, short)
        if len(str(short)) > maxlen:
            short = Path("...", short)
            break

    return str(short)


def dpg_section(
    label: str,
    color: tuple,
    *,
    spacer: int = 10,
    parent: str = 0,
    tag: str = 0,
) -> None:
    if spacer > 0:
        dpg.add_spacer(height=spacer)

    dpg.add_text(label, color=color, parent=parent, tag=tag)
    dpg.add_separator()


def exec_file_native(filename: str | Path):
    if sys.platform == "win32":
        os.startfile(str(filename))
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, str(filename)])


def success_countdown(
    window: int, label: int, countdown: int = 3, delete: bool = True
) -> None:
    def close():
        if delete:
            dpg.delete_item(window)
        else:
            dpg.hide_item(window)

    def callback():
        nonlocal countdown

        if countdown > 0:
            dpg.set_item_label(label, µ("Yay!") + f" ({countdown})")
            countdown -= 1
            dpg.set_frame_callback(
                int(dpg.get_frame_count() + dpg.get_frame_rate()), callback
            )
        else:
            close()

    dpg.bind_item_theme(label, style.themes.get_color_theme(style.light_blue))
    if dpg.get_item_type(label) == "mvButton":
        dpg.set_item_callback(label, close)

    callback()


class GraphCurve:
    def __init__(self, curve_type: Any, points: list[RTPCGraphPoint]):
        self.curve_type = curve_type
        self.points = points

    def copy(self) -> GraphCurve:
        return deepcopy(self)

    @property
    def x(self) -> Iterable[float]:
        for p in self:
            yield p.from_

    @property
    def y(self) -> Iterable[float]:
        for p in self:
            yield p.to

    @property
    def interp(self) -> Iterable[CurveInterpolation]:
        for p in self:
            yield p.interpolation

    @property
    def coords(self) -> Iterable[tuple[float, float]]:
        for p in self:
            yield (p.from_, p.to)

    def __getitem__(self, idx: int) -> RTPCGraphPoint:
        return self.points[idx]

    def __setitem__(self, idx: int, val: RTPCGraphPoint) -> None:
        self.points[idx] = val

    def __delitem__(self, idx: int) -> None:
        del self.points[idx]

    def __len__(self) -> int:
        return len(self.points)

    def __iter__(self) -> Iterable[RTPCGraphPoint]:
        yield from self.points

    def __str__(self) -> str:
        return f"GraphCurve<{self.curve_type}> [{len(self)} points]"
