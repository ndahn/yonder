from typing import Any, Callable, TypeAlias
from copy import deepcopy
from dearpygui import dearpygui as dpg

from yonder.types import MusicSwitchContainer, MusicRandomSequenceContainer
from yonder.types.base_types import (
    MusicTransitionRule,
    MusicTransSrcRule,
    MusicTransDstRule,
)
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.dialogs.edit_transition_dialog import edit_transition_dialog
from .dpg_item import DpgItem


TransitionNode: TypeAlias = MusicSwitchContainer | MusicRandomSequenceContainer


# Deep-copied for every new rule — never mutated directly
_base_transition_rule = MusicTransitionRule(
    source_transition_rule=MusicTransSrcRule(
        transition_time=500,
        fade_offet=500,
    ),
    destination_transition_rule=MusicTransDstRule(
        transition_time=500,
    ),
)


class add_transition_matrix(DpgItem):
    """A matrix widget showing transition rules between music container children.

    Renders an N×N table of clickable cells, where each cell represents the
    best-matching ``MusicTransitionRule`` for a (source, destination) child
    pair. Clicking a cell opens an edit dialog; right-clicking shows a context
    menu to add or delete the rule for that specific pair.

    The ``any`` row/column (id -1) represents wildcard matches and is always
    shown first. Rule specificity follows: exact+exact > exact+wildcard >
    wildcard+exact > wildcard+wildcard.

    Parameters
    ----------
    bnk : Soundbank
        Soundbank context (reserved for future use).
    node : TransitionNode
        Music container whose ``transition_rules`` are displayed and mutated.
    on_transition_rules_changed : callable, optional
        Fired as ``on_transition_rules_changed(tag, node, user_data)`` after
        any rule change.
    parent : int or str
        DPG parent item.
    tag : int or str
        Explicit tag; auto-generated if 0.
    user_data : any
        Passed through to ``on_transition_rules_changed``.
    """

    def __init__(
        self,
        node: TransitionNode,
        on_transition_rules_changed: Callable[[str, TransitionNode, Any], None] = None,
        *,
        label: str = "Transition Rules",
        parent: str | int = 0,
        tag: str | int = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self._node = node
        self._on_transition_rules_changed = on_transition_rules_changed
        self._user_data = user_data

        # Construction-time constants
        self._cell_size = 30
        table_h = min(
            400, 60 + self._cell_size * 1.8 + len(node.children) * (self._cell_size + 5)
        )

        # Per-instance color state; cache persists across regenerate() calls
        self._color_gen = style.HighContrastColorGenerator(
            0.4, 0.27, saturation=0.7, value=0.6
        )
        self._color_cache: dict[int, tuple] = {}
        self._theme_cache: dict[tuple, str] = {}

        # TODO consider using a heatmap for better performance instead
        if label:
            dpg.add_text(label, parent=parent, tag=self._t("transition_matrix/title"))
        dpg.add_table(
            header_row=True,
            no_pad_innerX=True,
            scrollX=True,
            scrollY=True,
            height=table_h,
            policy=dpg.mvTable_SizingFixedFit,
            parent=parent,
            tag=self._tag,
        )

        self.regenerate()

    # === Helpers =======================================================

    @staticmethod
    def _id_label(child_id: int) -> str:
        return "any" if child_id == -1 else str(child_id)

    @staticmethod
    def _get_cell_label(rule: MusicTransitionRule) -> str:
        return "x" if rule.transition_object.segment_id > 0 else ""

    def _get_rule_color(self, rule_idx: int) -> tuple:
        if rule_idx not in self._color_cache:
            self._color_cache[rule_idx] = self._color_gen()
        return self._color_cache[rule_idx]

    @staticmethod
    def _find_best_rule(
        rules: list[MusicTransitionRule],
        src_id: int,
        dst_id: int,
    ) -> tuple[int, MusicTransitionRule]:
        """Return ``(index, rule)`` of the most specific matching rule.

        Specificity: exact+exact > exact+wildcard > wildcard+exact >
        wildcard+wildcard. First encountered wins among equal scores.
        """
        best_idx = -1
        best_rule = None
        best_score = -1

        for i, rule in enumerate(rules):
            src_match = src_id in rule.source_ids
            dst_match = dst_id in rule.destination_ids
            src_wild = -1 in rule.source_ids
            dst_wild = -1 in rule.destination_ids

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
                best_idx = i
                best_rule = rule

        return (best_idx, best_rule)

    def _make_cell_theme(self, color: tuple) -> int:
        if color in self._theme_cache:
            return self._theme_cache[color]

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

        self._theme_cache[color] = theme_tag
        return theme_tag

    def _register_context_menu(
        self, btn: int | str, cell_info: tuple[int, int, int]
    ) -> None:
        registry = f"{btn}_handlers"
        if not dpg.does_item_exist(registry):
            dpg.add_item_handler_registry(tag=registry)
        dpg.add_item_clicked_handler(
            dpg.mvMouseButton_Right,
            callback=self._open_context_menu,
            user_data=cell_info,
            parent=registry,
        )
        dpg.bind_item_handler_registry(btn, registry)

    # === DPG callbacks =================================================

    def _add_rule_for_cell(
        self, sender: str, app_data: Any, cell_info: tuple[int, int, int]
    ) -> None:
        src, dst, _ = cell_info
        new_rule = deepcopy(_base_transition_rule)
        new_rule.source_ids = [src]
        new_rule.destination_ids = [dst]
        edit_transition_dialog(
            self._node, new_rule, self._on_rule_changed, user_data=True
        )

    def _delete_rule_for_cell(
        self, sender: str, app_data: Any, cell_info: tuple[int, int, int]
    ) -> None:
        _, _, rule_idx = cell_info
        # Rule 0 (any -> any) cannot be deleted
        if rule_idx > 0:
            self._node.transition_rules.pop(rule_idx)
            self.regenerate()

    def _open_context_menu(
        self, sender: str, app_data: Any, cell_info: tuple[int, int, int]
    ) -> None:
        with dpg.window(
            popup=True,
            min_size=(50, 20),
            no_saved_settings=True,
            tag=self._t("context_menu"),
            on_close=lambda: dpg.delete_item(context_win),
        ) as context_win:
            dpg.add_menu_item(
                label=µ("Add rule", "menu"),
                callback=self._add_rule_for_cell,
                user_data=cell_info,
            )
            dpg.add_menu_item(
                label=µ("Delete rule", "menu"),
                callback=self._delete_rule_for_cell,
                user_data=cell_info,
            )

    def _open_edit_transition_dialog(
        self, sender: str, app_data: Any, rule: MusicTransitionRule
    ) -> None:
        is_new = not rule
        if is_new:
            rule = deepcopy(_base_transition_rule)
        edit_transition_dialog(
            self._node, rule, self._on_rule_changed, user_data=is_new
        )

    def _on_rule_changed(self, sender: str, rule: dict, is_new: bool) -> None:
        if is_new:
            self._node.music_trans_node_params.transition_rules.append(rule)
        if self._on_transition_rules_changed:
            self._on_transition_rules_changed(self._tag, self._node, self._user_data)
        self.regenerate()

    # === Public ========================================================

    def regenerate(self) -> None:
        """Rebuild the full matrix from the node's current transition rules."""
        dpg.delete_item(self._tag, children_only=True, slot=0)
        dpg.delete_item(self._tag, children_only=True, slot=1)
        dpg.push_container_stack(self._tag)

        children = [-1] + list(self._node.children)
        cell_size = self._cell_size

        # Row-label column (no header — header row shows destination IDs)
        dpg.add_table_column()

        for dst in children:
            dpg.add_table_column(
                label=self._id_label(dst),
                angled_header=True,
                width_fixed=True,
                init_width_or_weight=cell_size,
            )

        for src in children:
            with dpg.table_row():
                dpg.add_text(self._id_label(src) + " ")

                for dst in children:
                    rule_idx, rule = self._find_best_rule(
                        self._node.music_trans_node_params.transition_rules, src, dst
                    )

                    if rule:
                        total_time = (
                            rule.source_transition_rule.transition_time
                            + rule.destination_transition_rule.transition_time
                        )
                        color = self._get_rule_color(rule_idx)
                        cell_label = self._get_cell_label(rule)
                    else:
                        color = (60, 60, 60, 200)
                        cell_label = ""
                        total_time = 0

                    btn = dpg.add_button(
                        label=cell_label,
                        width=cell_size - 4,
                        height=cell_size - 4,
                        callback=self._open_edit_transition_dialog,
                        user_data=rule,
                    )
                    self._register_context_menu(btn, (src, dst, rule_idx))
                    dpg.bind_item_theme(btn, self._make_cell_theme(color))

                    if rule:
                        source_label = (
                            self._id_label(rule.source_ids[0])
                            if len(rule.source_ids) == 1
                            else f"[{len(rule.source_ids)}]"
                        )
                        dest_label = (
                            self._id_label(rule.destination_ids[0])
                            if len(rule.destination_ids) == 1
                            else f"({len(rule.destination_ids)})"
                        )
                        with dpg.tooltip(btn):
                            dpg.add_text(
                                µ("Rule #{rule_idx}").format(
                                    rule_idx=rule_idx,
                                )
                            )
                            dpg.add_text(f"{source_label} -> {dest_label}")
                            dpg.add_text(
                                µ("Total transition time: {time}ms").format(
                                    time=total_time,
                                )
                            )
                            dpg.add_text(
                                µ("Sync type: {sync_type}").format(
                                    sync_type=rule.source_transition_rule.sync_type.name,
                                )
                            )

        dpg.pop_container_stack()
