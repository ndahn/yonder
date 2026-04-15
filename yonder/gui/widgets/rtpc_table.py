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


def add_rtpc_table(
    bnk: Soundbank,
    rtpcs: list[RTPC],
    on_value_changed: Callable[[str, list[RTPC], Any], None],
    *,
    label: str = "RTPCs",
    tag: str | int = 0,
    user_data: Any = None,
) -> None:
    if tag in (None, 0, ""):
        tag = dpg.generate_uuid()

    def make_setter(
        rtpc: RTPC,
        field: str,
        transformer: Callable[[Any], Any] = None,
        callback: Callable[[RTPC, str, Any], None] = None,
    ):
        def cb(sender: str, new_val: Any, cb_user_data: Any) -> None:
            if transformer:
                new_val = transformer(new_val)

            setattr(rtpc, field, new_val)
            if callback:
                callback(sender, (rtpc, field, new_val), cb_user_data)

            on_value_changed(tag, list(rtpcs), user_data)

        return cb

    def refresh_table() -> None:
        dpg.delete_item(tag, children_only=True, slot=1)
        for idx, item in enumerate(rtpcs):
            add_row(idx, item)

        add_footer()

    def on_add_clicked() -> None:
        rtpcs.append(
            RTPC(
                id=bnk.new_id(),
                curve_id=bnk.new_id(),
                graph_points=[RTPCGraphPoint()],
            )
        )
        refresh_table()
        on_value_changed(tag, list(rtpcs), user_data)

    def on_remove_clicked(sender: str, app_data: Any, idx: int) -> None:
        rtpcs.pop(idx)
        refresh_table()
        on_value_changed(tag, list(rtpcs), user_data)

    def on_hash_changed(sender: str, param_id: int, rtpc: RTPC) -> None:
        rtpc.id = param_id
        update_label(sender, (rtpc, "id", param_id), None)
        on_value_changed(tag, list(rtpcs), user_data)

    def update_label(sender: str, info: tuple[RTPC, str, Any], user_data: Any) -> None:
        rtpc = info[0]
        idx = rtpcs.index(rtpc)

        try:
            param = GameObjects.RTPCParameter(rtpc.param_id).name
        except KeyError:
            param = str(rtpc.param_id)

        name = rtpc.get_name(f"#{rtpc.id}")
        label = f"{name} ({param})".ljust(50)
        dpg.set_item_label(f"{tag}_tree_node_{idx}", label)

    def bind_context_menu(item: str, rtpc: RTPC) -> None:
        with dpg.popup(item, mousebutton=dpg.mvMouseButton_Right, min_size=(100, 50)):
            add_hash_widget(
                rtpc.id,
                on_hash_changed,
                horizontal=False,
                string_label="Name",
                user_data=rtpc,
                width=120,
            )

    def add_row(idx: int, rtpc: RTPC) -> None:
        with dpg.group(horizontal=True, parent=tag):
            with dpg.child_window(auto_resize_y=True, width=-20, border=False):
                with dpg.tree_node(
                    label=label, span_full_width=True, tag=f"{tag}_tree_node_{idx}"
                ):
                    dpg.add_combo(
                        [t.name for t in RtpcType],
                        label="Type",
                        default_value=rtpc.rtpc_type.name,
                        callback=make_setter(rtpc, "rtpc_type"),
                        tag=f"{tag}_item_{idx}_rtpc_type",
                    )
                    dpg.add_combo(
                        [a.name for a in RtpcAccum],
                        label="Accumulation",
                        default_value=rtpc.rtpc_accum.name,
                        callback=make_setter(rtpc, "rtpc_accum"),
                        tag=f"{tag}_item_{idx}_rtpc_accum",
                    )

                    add_incomplete_int_enum(
                        GameObjects.RTPCParameter,
                        GameObjects.RTPCParameter(rtpc.param_id),
                        "<unknown>",
                        make_setter(rtpc, "param_id", callback=update_label),
                        label="Parameter",
                        sort=False,
                        tag=f"{tag}_item_{idx}_param_id",
                    )

                    with dpg.child_window(auto_resize_x=True, auto_resize_y=True):
                        dpg.add_combo(
                            [c.name for c in CurveScaling],
                            label="Curve scaling",
                            default_value=rtpc.curve_scaling.name,
                            callback=make_setter(
                                rtpc, "curve_scaling", lambda v: CurveScaling[v]
                            ),
                            tag=f"{tag}_item_{idx}_curve_scaling",
                        )
                        add_interpolation_curve(
                            GraphCurve(rtpc.curve_scaling, rtpc.graph_points),
                            make_setter(rtpc, "graph_points", lambda v: v.points),
                            tag=f"{tag}_item_{idx}_curve",
                        )

                    dpg.add_spacer(height=5)

            dpg.add_button(label="x", callback=on_remove_clicked, user_data=idx)

            bind_context_menu(f"{tag}_tree_node_{idx}", rtpc)
            update_label(None, (rtpc, "id", rtpc.id), None)

    def add_footer() -> None:
        dpg.add_button(label="+ Add RTPC", callback=on_add_clicked, parent=tag)

    # The actual widgets
    if label:
        dpg.add_text(label)

    dpg.add_child_window(auto_resize_y=True, tag=tag)
    refresh_table()
