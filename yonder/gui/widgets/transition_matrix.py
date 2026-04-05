from typing import Any, Callable, TypeAlias
from copy import deepcopy
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.types import MusicSwitchContainer, MusicRandomSequenceContainer
from yonder.types.rewwise_base_types import (
    MusicTransitionRule,
    MusicTransSrcRule,
    MusicTransDstRule,
)
from yonder.gui import style
from yonder.gui.dialogs.edit_transition_dialog import edit_transition_dialog


TransitionNode: TypeAlias = MusicSwitchContainer | MusicRandomSequenceContainer


_base_transition_rule = MusicTransitionRule(
    source_transition_rule=MusicTransSrcRule(
        transition_time=500,
        fade_offet=500,
    ),
    destination_transition_rule=MusicTransDstRule(
        transition_time=500,
    ),
)


def add_transition_matrix(
    bnk: Soundbank,
    node: TransitionNode,
    on_transition_rules_changed: Callable[[str, TransitionNode, Any], None] = None,
    *,
    parent: str | int = 0,
    tag: str | int = 0,
    user_data: Any = None,
) -> str | int:
    if not tag:
        tag = dpg.generate_uuid()

    cell_size = 30
    table_h = min(400, 60 + cell_size * 1.8 + len(node.children) * (cell_size + 5))
    color_gen = style.HighContrastColorGenerator(0.4, 0.27, saturation=0.7, value=0.6)
    color_cache = {}

    def get_rule_color(rule: dict, rule_idx: int) -> tuple[int, int, int, int]:
        color = color_cache.get(rule_idx)

        if not color:
            color = color_gen()
            color_cache[rule_idx] = color

        return color

    def find_best_rule(
        rules: list[dict],
        src_id: int,
        dst_id: int,
    ) -> tuple[int, dict]:
        # Return the most specific rule for a (src, dst) pair.
        # Specificity:
        #  - exact src + exact dst >
        #  - exact src + wildcard >
        #  - wildcard + exact dst >
        #  - wildcard + wildcard
        # Among equal specificity, first encountered wins.
        best_rule_idx = -1
        best_rule = None
        best_score = -1

        for i, rule in enumerate(rules):
            src_ids = rule.get("source_ids", [-1])
            dst_ids = rule.get("destination_ids", [-1])

            src_match = src_id in src_ids
            dst_match = dst_id in dst_ids
            src_wild = -1 in src_ids
            dst_wild = -1 in dst_ids

            if src_match and dst_match:
                score = 3
            elif src_match and dst_wild:
                score = 2
            elif src_wild and dst_match:
                score = 1
            elif src_wild and dst_wild:
                score = 0
            else:
                continue

            if score > best_score:
                best_score = score
                best_rule_idx = i
                best_rule = rule

        return (best_rule_idx, best_rule)

    def id_label(id: int) -> str:
        if id == -1:
            return "any"

        return str(id)

    def get_cell_label(rule: dict) -> str:
        return "x" if rule.get("transition_object", {}).get("segment_id", 0) > 0 else ""

    def make_cell_theme(color: tuple[int, int, int, int]) -> int:
        theme_tag = dpg.generate_uuid()

        with dpg.theme(tag=theme_tag):
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, color)
                dpg.add_theme_color(
                    dpg.mvThemeCol_ButtonHovered,
                    (
                        min(color[0] + 40, 255),
                        min(color[1] + 40, 255),
                        min(color[2] + 40, 255),
                        230,
                    ),
                )
                dpg.add_theme_color(
                    dpg.mvThemeCol_ButtonActive,
                    (
                        min(color[0] + 60, 255),
                        min(color[1] + 60, 255),
                        min(color[2] + 60, 255),
                        255,
                    ),
                )
                dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))

        return theme_tag

    def add_rule_for_cell(
        sender: str, app_data: Any, cell_info: tuple[int, int, int]
    ) -> None:
        src, dst, _ = cell_info
        new_rule = deepcopy(_base_transition_rule)
        new_rule.source_ids = [src]
        new_rule.destination_ids = [dst]

        edit_transition_dialog(node, new_rule, on_rule_changed, user_data=True)

    def delete_rule_for_cell(
        sender: str, app_data: Any, cell_info: tuple[int, int, int]
    ) -> None:
        _, _, rule_idx = cell_info
        # Rule 0 (any -> any) cannot be deleted
        if rule_idx > 0:
            node.transition_rules.pop(rule_idx)
            regenerate()

    def open_context_menu(
        sender: str, app_data: Any, cell_info: tuple[int, int, int]
    ) -> None:
        with dpg.window(
            popup=True,
            min_size=(50, 20),
            no_saved_settings=True,
            tag=f"{tag}_context_menu",
            on_close=lambda: dpg.delete_item(context_win),
        ) as context_win:
            dpg.add_menu_item(
                label="Add rule",
                callback=add_rule_for_cell,
                user_data=cell_info,
            )
            dpg.add_menu_item(
                label="Delete rule",
                callback=delete_rule_for_cell,
                user_data=cell_info,
            )

    def register_context_menu(tag: str, cell_info: tuple[int, int, int]) -> None:
        registry = f"{tag}_handlers"

        if not dpg.does_item_exist(registry):
            dpg.add_item_handler_registry(tag=registry)

        dpg.add_item_clicked_handler(
            dpg.mvMouseButton_Right,
            callback=open_context_menu,
            user_data=cell_info,
            parent=registry,
        )
        dpg.bind_item_handler_registry(tag, registry)

    def open_edit_transition_dialog(sender: str, app_data: Any, rule: dict) -> None:
        is_new = not rule
        if is_new:
            rule = deepcopy(_base_transition_rule)

        edit_transition_dialog(node, rule, on_rule_changed, user_data=is_new)

    def on_rule_changed(sender: str, rule: dict, is_new: bool) -> None:
        if is_new:
            node.transition_rules.append(rule)

        if on_transition_rules_changed:
            on_transition_rules_changed(tag, node, user_data)

        regenerate()

    def regenerate() -> None:
        dpg.delete_item(tag, children_only=True, slot=0)
        dpg.delete_item(tag, children_only=True, slot=1)

        dpg.push_container_stack(tag)

        children = [-1] + list(node.children)

        # Row-label column (no header text — the header row shows destination IDs)
        dpg.add_table_column()

        # One column per destination ID
        for dst in children:
            dpg.add_table_column(
                label=id_label(dst),
                angled_header=True,
                width_fixed=True,
                init_width_or_weight=cell_size,
            )

        # One row per source ID
        for src in children:
            with dpg.table_row():
                # Row header cell
                dpg.add_text(id_label(src) + " ")

                for dst in children:
                    rule_idx, rule = find_best_rule(node.transition_rules, src, dst)

                    if rule:
                        src_trans_time = rule["source_transition_rule"][
                            "transition_time"
                        ]
                        dst_trans_time = rule["destination_transition_rule"][
                            "transition_time"
                        ]
                        total_time = src_trans_time + dst_trans_time
                        color = get_rule_color(rule, rule_idx)
                        cell_label = get_cell_label(rule)
                    else:
                        color = (60, 60, 60, 200)
                        cell_label = ""
                        total_time = 0

                    theme_tag = make_cell_theme(color)

                    btn = dpg.add_button(
                        label=cell_label,
                        width=cell_size - 4,
                        height=cell_size - 4,
                        callback=open_edit_transition_dialog,
                        user_data=rule,
                    )
                    register_context_menu(btn, (src, dst, rule_idx))
                    dpg.bind_item_theme(btn, theme_tag)

                    if rule:
                        sources = rule["source_ids"]
                        if len(sources) == 1:
                            source_label = id_label(sources[0])
                        else:
                            source_label = f"[{len(sources)}]"

                        destinations = rule["destination_ids"]
                        if len(destinations) == 1:
                            dest_label = id_label(destinations[0])
                        else:
                            dest_label = f"({len(destinations)})"

                        sync_type = rule["source_transition_rule"]["sync_type"]

                        with dpg.tooltip(btn):
                            dpg.add_text(f"Rule #{rule_idx}")
                            dpg.add_text(f"{source_label} -> {dest_label}")
                            dpg.add_text(f"Total transition time: {total_time}ms")
                            dpg.add_text(f"Sync type: {sync_type}")

        dpg.pop_container_stack()

    # TODO consider using a heatmap for better performance instead
    dpg.add_text("Transition rules")
    dpg.add_table(
        header_row=True,
        no_pad_innerX=True,
        scrollX=True,
        scrollY=True,
        height=table_h,
        policy=dpg.mvTable_SizingFixedFit,
        parent=parent,
        tag=tag,
    )

    regenerate()
    return tag
