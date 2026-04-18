from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.enums import RtpcType, RtpcAccum, CurveScaling
from yonder.game import GameObjects
from yonder.types.base_types import RTPC, RTPCGraphPoint
from yonder.gui.helpers import GraphCurve
from .hash_widget import add_hash_widget
from .incomplete_enum import add_incomplete_int_enum
from .interpolation_curve import add_interpolation_curve
from .dpg_item import DpgItem


class add_rtpc_table(DpgItem):
    """An editable list of RTPC entries for Dear PyGui.

    Each row expands into a tree node showing type, accumulation mode,
    parameter ID, curve scaling, and an interpolation curve editor.
    Right-clicking the tree node opens a hash widget to rename the RTPC.
    The passed-in ``rtpcs`` list is mutated in place; callbacks receive a
    shallow copy.

    Parameters
    ----------
    bnk : Soundbank
        Used to allocate new IDs for added RTPCs.
    rtpcs : list of RTPC
        Initial RTPC list; mutated directly by the widget.
    on_value_changed : callable
        Fired as ``on_value_changed(tag, rtpcs_copy, user_data)`` on any edit.
    label : str, optional
        Text label rendered above the table.
    tag : int or str
        Explicit tag; auto-generated if 0 or None.
    user_data : any
        Passed through to ``on_value_changed``.
    """

    def __init__(
        self,
        bnk: Soundbank,
        rtpcs: list[RTPC],
        on_value_changed: Callable[[str, list[RTPC], Any], None],
        *,
        label: str = "RTPCs",
        tag: str | int = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag if tag not in (None, 0, "") else dpg.generate_uuid())

        self._bnk = bnk
        self._rtpcs = rtpcs
        self._on_value_changed = on_value_changed
        self._user_data = user_data

        if label:
            dpg.add_text(label)

        dpg.add_child_window(auto_resize_y=True, tag=self._tag)
        self.refresh()

    # === Internal ======================================================

    def _item_tag(self, idx: int, suffix: str) -> str:
        return self._t(f"item_{idx}_{suffix}")

    def refresh(self) -> None:
        dpg.delete_item(self._tag, children_only=True, slot=1)
        for idx, rtpc in enumerate(self._rtpcs):
            self._add_row(idx, rtpc)
        self._add_footer()

    def _make_setter(
        self,
        rtpc: RTPC,
        field: str,
        transformer: Callable[[Any], Any] = None,
        callback: Callable[[str, tuple, Any], None] = None,
    ) -> Callable:
        def cb(sender: str, new_val: Any, cb_user_data: Any) -> None:
            if transformer:
                new_val = transformer(new_val)
            setattr(rtpc, field, new_val)
            if callback:
                callback(sender, (rtpc, field, new_val), cb_user_data)
            self._on_value_changed(self._tag, list(self._rtpcs), self._user_data)

        return cb

    def _update_label(self, sender: str, info: tuple[RTPC, str, Any], ud: Any) -> None:
        rtpc = info[0]
        idx = self._rtpcs.index(rtpc)

        try:
            param = GameObjects.RTPCParameter(rtpc.param_id).name
        except KeyError:
            param = str(rtpc.param_id)

        name = rtpc.get_name(f"#{rtpc.id}")
        dpg.set_item_label(
            self._item_tag(idx, "tree_node"), f"{name} ({param})".ljust(50)
        )

    def _bind_context_menu(self, item_tag: str, rtpc: RTPC) -> None:
        with dpg.popup(
            item_tag, mousebutton=dpg.mvMouseButton_Right, min_size=(100, 50)
        ):
            add_hash_widget(
                rtpc.id,
                self._on_hash_changed,
                horizontal=False,
                string_label="Name",
                user_data=rtpc,
                width=120,
            )

    def _add_row(self, idx: int, rtpc: RTPC) -> None:
        with dpg.group(horizontal=True, parent=self._tag):
            with dpg.child_window(auto_resize_y=True, width=-20, border=False):
                with dpg.tree_node(
                    span_full_width=True,
                    tag=self._item_tag(idx, "tree_node"),
                ):
                    dpg.add_combo(
                        [t.name for t in RtpcType],
                        label="Type",
                        default_value=rtpc.rtpc_type.name,
                        callback=self._make_setter(rtpc, "rtpc_type"),
                        tag=self._item_tag(idx, "rtpc_type"),
                    )
                    dpg.add_combo(
                        [a.name for a in RtpcAccum],
                        label="Accumulation",
                        default_value=rtpc.rtpc_accum.name,
                        callback=self._make_setter(rtpc, "rtpc_accum"),
                        tag=self._item_tag(idx, "rtpc_accum"),
                    )
                    add_incomplete_int_enum(
                        GameObjects.RTPCParameter,
                        GameObjects.RTPCParameter(rtpc.param_id),
                        "<unknown>",
                        self._make_setter(
                            rtpc, "param_id", callback=self._update_label
                        ),
                        label="Parameter",
                        sort=False,
                        tag=self._item_tag(idx, "param_id"),
                    )
                    with dpg.child_window(auto_resize_x=True, auto_resize_y=True):
                        dpg.add_combo(
                            [c.name for c in CurveScaling],
                            label="Curve scaling",
                            default_value=rtpc.curve_scaling.name,
                            callback=self._make_setter(
                                rtpc, "curve_scaling", lambda v: CurveScaling[v]
                            ),
                            tag=self._item_tag(idx, "curve_scaling"),
                        )
                        add_interpolation_curve(
                            GraphCurve(rtpc.curve_scaling, rtpc.graph_points),
                            self._make_setter(rtpc, "graph_points", lambda v: v.points),
                            tag=self._item_tag(idx, "curve"),
                        )
                    dpg.add_spacer(height=5)

            dpg.add_button(
                label="x",
                callback=self._on_remove_clicked,
                user_data=idx,
            )

        tree_tag = self._item_tag(idx, "tree_node")
        self._bind_context_menu(tree_tag, rtpc)
        self._update_label(None, (rtpc, "id", rtpc.id), None)

    def _add_footer(self) -> None:
        dpg.add_button(
            label="+ Add RTPC", callback=self._on_add_clicked, parent=self._tag
        )

    # === DPG callbacks =================================================

    def _on_hash_changed(
        self, sender: str, hash_info: tuple[int, str], rtpc: RTPC
    ) -> None:
        rtpc.id = hash_info[0]
        self._update_label(sender, (rtpc, "id", hash_info[0]), None)
        self._on_value_changed(self._tag, list(self._rtpcs), self._user_data)

    def _on_add_clicked(self) -> None:
        self._rtpcs.append(
            RTPC(
                id=self._bnk.new_id(),
                curve_id=self._bnk.new_id(),
                graph_points=[RTPCGraphPoint()],
            )
        )
        self.refresh()
        self._on_value_changed(self._tag, list(self._rtpcs), self._user_data)

    def _on_remove_clicked(self, sender: str, app_data: Any, idx: int) -> None:
        self._rtpcs.pop(idx)
        self.refresh()
        self._on_value_changed(self._tag, list(self._rtpcs), self._user_data)

    # === Public ========================================================

    @property
    def rtpcs(self) -> list[RTPC]:
        return list(self._rtpcs)

    @rtpcs.setter
    def rtpcs(self, value: list[RTPC]) -> None:
        self._rtpcs = list(value)
        self.refresh()
