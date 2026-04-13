from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.enums import RtpcType, RtpcAccum, CurveScaling
from yonder.types.base_types import RTPC
from yonder.gui.helpers import GraphCurve
from .interpolation_curve import add_interpolation_curve


def add_rtpc_table(
    bnk: Soundbank,
    rtpcs: list[RTPC],
    on_value_changed: Callable[[str, list[RTPC], Any], None],
    *,
    label: str = "Properties",
    tag: str | int = 0,
    user_data: Any = None,
) -> None:
    if tag in (None, 0, ""):
        tag = dpg.generate_uuid()

    def make_setter(rtpc: RTPC, field: str, transformer: Callable[[Any], Any] = None):
        def cb(sender: str, new_val: Any, cb_user_data: Any) -> None:
            if transformer:
                new_val = transformer(new_val)

            setattr(rtpc, field, new_val)
            on_value_changed(tag, list(rtpcs), user_data)

        return cb

    def refresh_table() -> None:
        dpg.delete_item(tag, children_only=True, slot=1)
        for idx, item in enumerate(rtpcs):
            add_row(idx, item)

        add_footer()

    def on_add_clicked() -> None:
        rtpcs.append(RTPC(id=bnk.new_id(), curve_id=bnk.new_id()))
        refresh_table()
        on_value_changed(tag, list(rtpcs), user_data)

    def on_remove_clicked(sender: str, app_data: Any, idx: int) -> None:
        rtpcs.pop(idx)
        refresh_table()
        on_value_changed(tag, list(rtpcs), user_data)

    def add_row(idx: int, item: RTPC) -> None:
        label = f"{item.get_name('?')} #{item.id} ({item.param_id})".ljust(50)
        
        with dpg.group(horizontal=True, parent=tag):
            with dpg.child_window(auto_resize_y=True, width=-50, border=False):
                with dpg.tree_node(label=label, span_full_width=True):
                    dpg.add_combo(
                        [t.name for t in RtpcType],
                        label="Type",
                        default_value=item.rtpc_type.name,
                        callback=make_setter(item, "rtpc_type"),
                        tag=f"{tag}_item_{idx}_rtpc_type",
                    )
                    dpg.add_combo(
                        [a.name for a in RtpcAccum],
                        label="Accumulation",
                        default_value=item.rtpc_accum.name,
                        callback=make_setter(item, "rtpc_accum"),
                        tag=f"{tag}_item_{idx}_rtpc_accum",
                    )
                    # TODO Apparently the IDs are stored in a Wwise_IDs.h created on soundbank creation
                    # Maybe we can locate them in ghidra?
                    dpg.add_input_int(
                        label="Parameter",
                        default_value=item.param_id,
                        min_value=0,
                        min_clamped=True,
                        callback=make_setter(item, "param_id"),
                        tag=f"{tag}_item_{idx}_param_id",
                    )
                    
                    with dpg.child_window(auto_resize_x=True, auto_resize_y=True):
                        dpg.add_combo(
                            [c.name for c in CurveScaling],
                            label="Curve scaling",
                            default_value=item.curve_scaling.name,
                            callback=make_setter(item, "curve_scaling", lambda v: CurveScaling[v]),
                            tag=f"{tag}_item_{idx}_curve_scaling",
                        )
                        add_interpolation_curve(
                            GraphCurve(item.curve_scaling, item.graph_points),
                            make_setter(item, "graph_points", lambda v: v.points),
                            tag=f"{tag}_item_{idx}_curve",
                        )
                    
                    dpg.add_spacer(height=5)

            dpg.add_button(label="x", callback=on_remove_clicked, user_data=idx)

    def add_footer() -> None:
        dpg.add_button(label="+ Add Property", callback=on_add_clicked, parent=tag)

    # The actual widgets
    if label:
        dpg.add_text(label)

    dpg.add_group(tag=tag)
    refresh_table()
