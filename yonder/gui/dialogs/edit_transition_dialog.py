from typing import Any, Callable, TypeAlias
from copy import deepcopy
from dearpygui import dearpygui as dpg

from yonder.types import MusicSwitchContainer, MusicRandomSequenceContainer
from yonder.types.base_types import MusicTransitionRule
from yonder.enums import CurveInterpolation, SyncType
from yonder.util import deepmerge
from yonder.gui import style
from yonder.gui.localization import translate as t
from yonder.gui.helpers import dpg_section
from yonder.gui.widgets import DpgItem


TransitionNode: TypeAlias = MusicSwitchContainer | MusicRandomSequenceContainer


class edit_transition_dialog(DpgItem):
    """A dialog for editing a ``MusicTransitionRule`` in place.

    Shows source and destination transition parameters (transition time, fade
    offset, fade curve) along with sync type and affected node ID lists.
    Confirming deep-merges the edited copy back into ``base_rule`` and calls
    ``on_rule_changed``.

    Parameters
    ----------
    node : TransitionNode
        Parent music container; its children populate the ID selector combos.
    base_rule : MusicTransitionRule
        Rule to edit; a deep copy is used internally and merged back on confirm.
    on_rule_changed : callable
        Fired as ``on_rule_changed(tag, base_rule, user_data)`` on confirm.
    tag : int or str
        Explicit tag; auto-generated if 0. Existing item is deleted first.
    user_data : any
        Passed through to ``on_rule_changed``.
    """

    def __init__(
        self,
        node: TransitionNode,
        base_rule: MusicTransitionRule,
        on_rule_changed: Callable[[str, dict, Any], None],
        *,
        tag: int | str = 0,
        user_data: Any = None,
    ) -> None:
        if tag and dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        super().__init__(tag if tag else dpg.generate_uuid())

        self._node = node
        self._base_rule = base_rule
        self._rule = deepcopy(base_rule)
        self._src_rule = self._rule.source_transition_rule
        self._dst_rule = self._rule.destination_transition_rule
        self._on_rule_changed = on_rule_changed
        self._user_data = user_data
        self._window: int | str = None

        self._build()

    # === Helpers =======================================================

    def _table_tag(self, rule_key: str) -> str:
        prefix = "src" if rule_key == "source_ids" else "dst"
        return self._t(f"{prefix}_ids_table")

    def _add_item_tag(self, rule_key: str) -> str:
        return self._t(f"{rule_key}_add_item")

    # === ID table management ===========================================

    def _refresh(self, rule_key: str) -> None:
        table = self._table_tag(rule_key)
        dpg.delete_item(table, children_only=True, slot=1)
        for node_id in getattr(self._rule, rule_key):
            self._add_id_row(table, node_id, rule_key)
        self._add_id_footer(table, rule_key)
        dpg.configure_item(
            table, height=min(150, 30 + len(getattr(self._rule, rule_key)) * 30)
        )

    def _add_id_row(self, table: str, node_id: int, rule_key: str) -> None:
        with dpg.table_row(parent=table):
            dpg.add_text(str(node_id))
            dpg.add_button(
                label="-",
                callback=self._on_remove_clicked,
                user_data=(node_id, rule_key),
            )

    def _add_id_footer(self, table: str, rule_key: str) -> None:
        missing = sorted(
            set(self._node.children).difference(getattr(self._rule, rule_key))
        )
        with dpg.table_row(parent=table):
            dpg.add_combo(missing, width=-1, tag=self._add_item_tag(rule_key))
            dpg.add_button(
                label="+",
                callback=self._on_add_clicked,
                user_data=rule_key,
            )

    def _build_id_table(self, rule_key: str) -> None:
        with dpg.table(
            header_row=False,
            no_host_extendX=True,
            no_host_extendY=True,
            height=100,
            scrollY=True,
            policy=dpg.mvTable_SizingFixedFit,
            tag=self._table_tag(rule_key),
        ):
            dpg.add_table_column(
                label="File", width_stretch=True, init_width_or_weight=100
            )
            dpg.add_table_column(label="")

        self._refresh(rule_key)

    # === Build =========================================================

    def _build(self) -> None:
        src = self._src_rule
        dst = self._dst_rule

        with dpg.window(
            label=t(
                "Edit Transition ({node_id})",
                "edit_transition/title",
                node_id=self._node.id,
            ),
            width=400,
            height=400,
            autosize=True,
            no_saved_settings=True,
            tag=self._tag,
            on_close=lambda: dpg.delete_item(self._window),
        ) as self._window:
            dpg_section("Source Transition Rule", style.muted_orange, first=True, tag=self._t("edit_transition/src_transition_rule"))
            dpg.add_input_int(
                label="Transition time (ms)",
                default_value=src.transition_time,
                min_value=0,
                max_value=60000,
                step=500,
                step_fast=1000,
                min_clamped=True,
                max_clamped=True,
                callback=lambda s, a, u: setattr(self._src_rule, "transition_time", a),
                tag=self._t("edit_transition/src_transition_time"),
            )
            dpg.add_input_int(
                label="Fade offset (ms)",
                default_value=src.fade_offet,
                min_value=-60000,
                max_value=60000,
                step=500,
                step_fast=1000,
                min_clamped=True,
                max_clamped=True,
                callback=lambda s, a, u: setattr(self._src_rule, "fade_offet", a),
                tag=self._t("edit_transition/src_fade_offset"),
            )
            dpg.add_combo(
                label="Fade curve",
                items=[c.name for c in CurveInterpolation],
                default_value=src.fade_curve.name,
                callback=lambda s, a, u: setattr(
                    self._src_rule, "fade_curve", CurveInterpolation[a]
                ),
                tag=self._t("edit_transition/src_fade_curve"),
            )
            dpg.add_combo(
                label="Sync Type",
                items=[s.name for s in SyncType],
                default_value=src.sync_type.name,
                callback=lambda s, a, u: setattr(
                    self._src_rule, "sync_type", SyncType[a]
                ),
                tag=self._t("edit_transition/sync_type"),
            )

            dpg_section("Destination Transition Rule", style.muted_teal, tag=self._t("edit_transition/dst_transition_rule"))
            dpg.add_input_int(
                label="Transition time (ms)",
                default_value=dst.transition_time,
                min_value=0,
                max_value=60000,
                step=500,
                step_fast=1000,
                min_clamped=True,
                max_clamped=True,
                callback=lambda s, a, u: setattr(self._dst_rule, "transition_time", a),
                tag=self._t("edit_transition/dst_transition_time"),
            )
            dpg.add_input_int(
                label="Fade offset (ms)",
                default_value=dst.fade_offet,
                min_value=-60000,
                max_value=60000,
                min_clamped=True,
                max_clamped=True,
                callback=lambda s, a, u: setattr(self._dst_rule, "fade_offet", a),
                tag=self._t("edit_transition/dst_fade_offset"),
            )
            dpg.add_combo(
                label="Fade curve",
                items=[c.name for c in CurveInterpolation],
                default_value=dst.fade_curve.name,
                callback=lambda s, a, u: setattr(
                    self._dst_rule, "fade_curve", CurveInterpolation[a]
                ),
                tag=self._t("edit_transition/dst_fade_curve"),
            )

            dpg_section("Affected nodes", style.light_grey, tag=self._t("edit_transition/affected_nodes"))
            with dpg.group(horizontal=True):
                with dpg.child_window(border=False, width=200, auto_resize_y=True):
                    dpg.add_text("Source IDs:")
                    self._build_id_table("edit_transition/source_ids")

                with dpg.child_window(border=False, width=200, auto_resize_y=True):
                    dpg.add_text("Destination IDs:")
                    self._build_id_table("edit_transition/destination_ids")

            dpg.add_separator()
            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Okay", callback=self._on_okay, tag=self._t("button_okay")
                )
                dpg.add_button(
                    label="Cancel", callback=lambda: dpg.delete_item(self._window)
                )

    # === DPG Callbacks =================================================

    def _on_remove_clicked(
        self, sender: str, app_data: Any, info: tuple[int, str]
    ) -> None:
        node_id, rule_key = info
        ref_nodes: list[int] = getattr(self._rule, rule_key)
        ref_nodes.remove(node_id)
        if not ref_nodes:
            ref_nodes.append(-1)
        self._refresh(rule_key)

    def _on_add_clicked(self, sender: str, app_data: Any, rule_key: str) -> None:
        new_ref = dpg.get_value(self._add_item_tag(rule_key))
        if not new_ref:
            return

        ref_nodes: list[int] = getattr(self._rule, rule_key)
        if -1 in ref_nodes:
            ref_nodes.remove(-1)

        ref_nodes.append(int(new_ref))
        ref_nodes.sort()
        self._refresh(rule_key)

    def _on_okay(self) -> None:
        deepmerge(self._base_rule, self._rule)
        self._on_rule_changed(self._tag, self._base_rule, self._user_data)
        dpg.delete_item(self._window)

    # === Public ========================================================

    def show_message(self, msg: str = None, color: style.RGBA = style.red) -> None:
        """Show or hide the notification label. Pass ``msg=None`` to hide."""
        if not msg:
            dpg.hide_item(self._t("notification"))
            return
        dpg.configure_item(
            self._t("notification"), default_value=msg, color=color, show=True
        )
