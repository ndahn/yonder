from typing import Any, Callable, get_args
from copy import deepcopy
from dearpygui import dearpygui as dpg

from yonder.node_types import MusicSwitchContainer, MusicRandomSequenceContainer
from yonder.enums import CurveType, SyncType
from yonder.util import deepmerge
from yonder.gui import style


def edit_transition_dialog(
    node: MusicSwitchContainer | MusicRandomSequenceContainer,
    base_rule: dict,
    on_rule_changed: Callable[[str, dict, Any], None],
    *,
    tag: str = 0,
    user_data: Any = None,
) -> None:
    if not tag:
        tag = dpg.generate_uuid()
    elif dpg.does_item_exist(tag):
        dpg.delete_item(tag)

    def refresh(table: str, rule_key: str) -> None:
        dpg.delete_item(table, children_only=True, slot=1)

        for src_id in rule[rule_key]:
            add_row(table, src_id, rule_key)

        add_footer(table, rule_key)
        dpg.configure_item(table, height=min(150, 30 + len(rule[rule_key]) * 30))

    def on_remove_clicked(
        sender: str, app_data: Any, info: tuple[str, int, str]
    ) -> None:
        table, id, rule_key = info
        ref_nodes: list[int] = rule[rule_key]
        ref_nodes.remove(id)

        if not ref_nodes:
            ref_nodes.append(-1)

        refresh(table, rule_key)

    def on_add_clicked(sender: str, app_data: Any, info: tuple[str, str]) -> None:
        table, rule_key = info
        new_ref = dpg.get_value(f"{tag}_{rule_key}_add_item")

        if not new_ref:
            return

        ref_nodes: list[int] = rule[rule_key]
        if -1 in ref_nodes:
            ref_nodes.remove(-1)

        ref_nodes.append(int(new_ref))
        ref_nodes.sort()

        refresh(table, rule_key)

    def add_row(table: str, id: int, rule_key: str) -> None:
        with dpg.table_row(parent=table):
            dpg.add_text(str(id))
            dpg.add_button(
                label="-",
                callback=on_remove_clicked,
                user_data=(table, id, rule_key),
            )

    def add_footer(table: str, rule_key: str) -> None:
        missing = sorted(set(node.children).difference(rule[rule_key]))

        with dpg.table_row(parent=table):
            dpg.add_combo(
                missing,
                width=-1,
                tag=f"{tag}_{rule_key}_add_item",
            )
            dpg.add_button(
                label="+",
                callback=on_add_clicked,
                user_data=(table, rule_key),
            )

    def on_okay():
        # Other fields are update by the widgets directly
        rule["source_transition_rule_count"] = len(rule["source_ids"])
        rule["destination_transition_rule_count"] = len(rule["destination_ids"])

        deepmerge(base_rule, rule)

        on_rule_changed(tag, base_rule, user_data)
        dpg.delete_item(window)

    rule = deepcopy(base_rule)
    src_rule: dict = rule.setdefault("source_transition_rule", {})
    dst_rule: dict = rule.setdefault("destination_transition_rule", {})

    with dpg.window(
        label=f"Edit Transition ({node.id})",
        width=400,
        height=400,
        autosize=True,
        no_saved_settings=True,
        tag=tag,
        on_close=lambda: dpg.delete_item(window),
    ) as window:
        dpg.add_text("Source Transition Rule", color=(200, 120, 80, 255))
        dpg.add_separator()

        dpg.add_input_int(
            label="Transition time (ms)",
            default_value=src_rule["transition_time"],
            min_value=0,
            max_value=60000,
            step=500,
            step_fast=1000,
            min_clamped=True,
            max_clamped=True,
            tag=f"{tag}_src_transition_time",
            callback=lambda s, a, u: src_rule.update({"transition_time": a}),
        )
        dpg.add_input_int(
            label="Fade offset (ms)",
            default_value=src_rule.get("fade_offet", 0),
            min_value=-60000,
            max_value=60000,
            step=500,
            step_fast=1000,
            min_clamped=True,
            max_clamped=True,
            tag=f"{tag}_src_fade_offset",
            callback=lambda s, a, u: src_rule.update({"fade_offet": a}),
        )
        dpg.add_combo(
            label="Fade curve",
            items=get_args(CurveType),
            default_value=src_rule.get("fade_curve", "Linear"),
            tag=f"{tag}_src_fade_curve",
            callback=lambda s, a, u: src_rule.update({"fade_curve": a}),
        )
        dpg.add_combo(
            label="Sync Type",
            items=get_args(SyncType),
            default_value=src_rule.get("sync_type", "Immediate"),
            tag=f"{tag}_sync_type",
            callback=lambda s, a, u: src_rule.update({"sync_type": a}),
        )

        dpg.add_spacer(height=10)
        dpg.add_text("Destination Transition Rule", color=(80, 120, 200, 255))
        dpg.add_separator()

        dpg.add_input_int(
            label="Transition time (ms)",
            default_value=dst_rule["transition_time"],
            min_value=0,
            max_value=60000,
            step=500,
            step_fast=1000,
            min_clamped=True,
            max_clamped=True,
            tag=f"{tag}_dst_transition_time",
            callback=lambda s, a, u: dst_rule.update({"transition_time": a}),
        )
        dpg.add_input_int(
            label="Fade offset (ms)",
            default_value=dst_rule.get("fade_offet", 0),
            min_value=-60000,
            max_value=60000,
            min_clamped=True,
            max_clamped=True,
            tag=f"{tag}_dst_fade_offset",
            callback=lambda s, a, u: dst_rule.update({"fade_offet": a}),
        )
        dpg.add_combo(
            label="Fade curve",
            items=get_args(CurveType),
            default_value=dst_rule.get("fade_curve", "Linear"),
            tag=f"{tag}_dst_fade_curve",
            callback=lambda s, a, u: dst_rule.update({"fade_curve": a}),
        )

        dpg.add_spacer(height=10)
        dpg.add_text("Affected nodes", color=(180, 180, 180, 255))
        dpg.add_separator()

        with dpg.group(horizontal=True):
            with dpg.child_window(border=False, width=200, auto_resize_y=True):
                dpg.add_text("Source IDs: ")
                with dpg.table(
                    header_row=False,
                    no_host_extendX=True,
                    no_host_extendY=True,
                    height=100,
                    scrollY=True,
                    policy=dpg.mvTable_SizingFixedFit,
                    tag=f"{tag}_src_ids_table",
                ) as table:
                    dpg.add_table_column(
                        label="File", width_stretch=True, init_width_or_weight=100
                    )
                    dpg.add_table_column(label="")

                    refresh(table, "source_ids")

            with dpg.child_window(border=False, width=200, auto_resize_y=True):
                dpg.add_text("Destination IDs: ")
                with dpg.table(
                    header_row=False,
                    no_host_extendX=True,
                    no_host_extendY=True,
                    height=100,
                    scrollY=True,
                    policy=dpg.mvTable_SizingFixedFit,
                    tag=f"{tag}_dst_ids_table",
                ) as table:
                    dpg.add_table_column(
                        label="File", width_stretch=True, init_width_or_weight=100
                    )
                    dpg.add_table_column(label="")

                    refresh(table, "destination_ids")

        dpg.add_separator()
        dpg.add_text(show=False, tag=f"{tag}_notification", color=style.red)

        with dpg.group(horizontal=True):
            dpg.add_button(label="Okay", callback=on_okay, tag=f"{tag}_button_okay")
            dpg.add_button(
                label="Cancel",
                callback=lambda: dpg.delete_item(window),
            )
