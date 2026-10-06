from __future__ import annotations
from typing import Any, Callable, TYPE_CHECKING
from dearpygui import dearpygui as dpg

from yonder.enums import MarkerId
from yonder.util import logger
from yonder.types import MusicSegment, MusicTrack
from yonder.types.base_types import MusicMarkerWwise
from yonder.gui import style
from yonder.gui.helpers import get_sound_path
from yonder.gui.localization import µ
from .dpg_item import DpgItem
from .editable_table import add_widget_table
from .hash_widget import add_hash_widget
from .state_value_input import add_state_value_input

if TYPE_CHECKING:
    from yonder import Soundbank


class add_marker_editor(DpgItem):
    """Editor for a MusicSegment's markers.

    Markers are named positions inside a segment, given in milliseconds. Wwise
    uses two of them by hash (`MarkerId.LoopStart` / `LoopEnd`) to define the
    looping region; the rest are free for cue points. The loop markers are shown
    under their enum name and their id is locked, since renaming one silently
    stops the segment from looping.

    Given a `bnk`, the editor also offers to place the loop markers on the
    waveform of one of the segment's tracks.

    The segment is edited in place and every change is reported through
    `on_value_changed`.

    Parameters
    ----------
    segment : MusicSegment
        The segment whose markers are edited. Modified in place.
    on_value_changed : callable
        Called as ``on_value_changed(tag, segment, user_data)`` after any change.
    bnk : Soundbank, optional
        Needed to resolve the segment's tracks for waveform editing. Without it
        only the table is shown.
    label : str, optional
        Heading above the table, defaults to "Markers".
    tag : int or str
        Explicit tag; auto-generated if 0.
    user_data : any
        Passed through to `on_value_changed`.
    """

    def __init__(
        self,
        segment: MusicSegment,
        on_value_changed: Callable[[str, MusicSegment, Any], None],
        *,
        bnk: Soundbank = None,
        label: str = None,
        compact: bool = False,
        tag: str | int = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self.segment = segment
        self._bnk = bnk
        self._on_value_changed = on_value_changed
        self._user_data = user_data

        self._table: add_widget_table = None
        # Combo label -> track id, so we don't have to parse ids back out
        self._tracks: dict[str, int] = {}

        self._build(label, compact)

    def destroy(self) -> None:
        self._delete_item(self._t("tracks"))
        self._delete_item(self._t("edit_on_track"))

    # === Build =========================================================

    def _build(self, label: str, compact: bool) -> None:
        with dpg.group(tag=self.tag):
            self._table = add_widget_table(
                self.segment.markers,
                self._make_row,
                new_item=self._new_marker,
                on_add=self._on_marker_added,
                on_remove=self._on_marker_removed,
                columns=[µ("Marker"), µ("Position (ms)")],
                add_item_label=µ("+ Add Marker"),
                label=label,
                compact=compact,
            )

            if self._bnk is not None:
                self._build_track_row()

    def _build_track_row(self) -> None:
        self._tracks = {
            µ("Track #{idx}").format(idx=cid): cid
            for cid in self.segment.children
            if isinstance(self._bnk.get(cid), MusicTrack)
        }

        if not self._tracks:
            dpg.add_text(
                µ("Segment has no tracks"),
                color=style.yellow,
                tag=self._t("no_tracks"),
            )
            return

        labels = list(self._tracks)
        with dpg.group(horizontal=True):
            dpg.add_combo(
                labels,
                default_value=labels[0],
                width=140,
                tag=self._t("tracks"),
            )
            dpg.add_button(
                label=µ("Edit on Track", "button"),
                callback=self._on_edit_on_track,
                tag=self._t("edit_on_track"),
            )
            with dpg.tooltip(dpg.last_item()):
                dpg.add_text(µ("Place the loop markers on the track's waveform"))

    def regenerate(self) -> None:
        """Rebuild the rows from the segment's markers."""
        self._table.items = self.segment.markers

    def _make_row(self, marker: MusicMarkerWwise, idx: int) -> None:
        add_state_value_input(
            [m.name for m in MarkerId],
            self._on_marker_renamed,
            default_value=marker.id,
            custom_values={m.name: m.value for m in MarkerId},
            width=80,
            user_data=marker,
        )

        dpg.add_input_float(
            default_value=marker.position,
            min_value=0.0,
            min_clamped=True,
            callback=self._on_marker_moved,
            user_data=marker,
            width=-1,
        )

    # === Public ========================================================

    def get_selected_track(self) -> MusicTrack:
        """The track currently picked for waveform editing, if any."""
        if not self._tracks or not dpg.does_item_exist(self._t("tracks")):
            return None

        track_id = self._tracks.get(dpg.get_value(self._t("tracks")))
        return self._bnk.get(track_id) if track_id else None

    def notify_changed(self) -> None:
        if self._on_value_changed:
            self._on_value_changed(self.tag, self.segment, self._user_data)

    # === DPG callbacks =================================================

    def _new_marker(self, done: Callable[[MusicMarkerWwise], None]) -> None:
        # set_marker already appends to the segment, the table just mirrors it
        done(self.segment.set_marker(f"m{len(self.segment.markers)}", 0.0))

    def _on_marker_added(
        self,
        sender: str,
        info: tuple[int, MusicMarkerWwise, list[MusicMarkerWwise]],
        cb_user_data: Any,
    ) -> None:
        self.notify_changed()

    def _on_marker_removed(
        self,
        sender: str,
        info: tuple[int, MusicMarkerWwise, list[MusicMarkerWwise]],
        cb_user_data: Any,
    ) -> None:
        marker = info[1]
        if marker is None:
            # The table was cleared
            self.segment.markers.clear()
        else:
            self.segment.remove_marker(marker.id)

        self.notify_changed()

    def _on_marker_renamed(
        self, sender: str, new_name: tuple[int, str], marker: MusicMarkerWwise
    ) -> None:
        mid, name = new_name

        if any(m is not marker and m.id == mid for m in self.segment.markers):
            logger.error(
                µ("A marker with ID {mid} already exists", "log").format(mid=mid)
            )
            return

        if name.startswith("#"):
            name = None

        # Edited in place so the row order and the open hash widget both survive
        marker.id = mid
        marker.string = name or ""
        marker.string_length = len(name) + 1 if name else 0
        self.notify_changed()

    def _on_marker_moved(
        self, sender: str, pos: float, marker: MusicMarkerWwise
    ) -> None:
        marker.position = pos
        self.notify_changed()

    def _on_loop_changed(
        self, sender: str, loop_info: tuple[float, float, bool], cb_user_data: Any
    ) -> None:
        loop_start, loop_end, _ = loop_info
        self.segment.set_marker(MarkerId.LoopStart, loop_start)
        self.segment.set_marker(MarkerId.LoopEnd, loop_end)

        self.regenerate()
        self.notify_changed()

    def _on_edit_on_track(self) -> None:
        from yonder.gui.dialogs.edit_markers_dialog import edit_markers_dialog

        track = self.get_selected_track()
        if not track:
            return

        if not track.sources:
            logger.warning(
                µ("{track} has no sources", "log").format(track=track)
            )
            return

        source = track.sources[0]
        path = get_sound_path(
            self._bnk, source.media_information.source_id, source.source_type
        )
        if not path:
            logger.error(
                µ("No sound file found for {track}", "log").format(track=track)
            )
            return

        edit_markers_dialog(
            path,
            accept_on_okay=True,
            loop_markers_enabled=True,
            loop_start=self.segment.get_marker_pos(MarkerId.LoopStart, 1000.0),
            loop_end=self.segment.get_marker_pos(MarkerId.LoopEnd, -1000.0),
            on_loop_changed=self._on_loop_changed,
        )
