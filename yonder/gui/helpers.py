from typing import Any, Iterable
from pathlib import Path
import tempfile
import atexit
from copy import deepcopy
from dearpygui import dearpygui as dpg

from yonder.util import logger
from yonder.types.base_types import RTPCGraphPoint
from yonder.enums import CurveInterpolation


url_regex = r"https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)"

tmp_dir = tempfile.TemporaryDirectory(prefix="yonder_")
atexit.register(tmp_dir.cleanup)
logger.info(f"Temporary files will be stored in {tmp_dir.name}")


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


class GraphCurve():
    def __init__(self, curve_type: Any, points: list[RTPCGraphPoint]):
        self.curve_type = curve_type
        self.points = points

    def copy(self) -> "GraphCurve":
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
