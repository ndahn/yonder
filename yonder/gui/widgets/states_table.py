from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder import Soundbank, lookup_name
from yonder.game import GameObjects
from yonder.types.state import State
from yonder.types.base_types import (
    StateChunk,
    StateGroupChunk,
    StatePropertyInfo,
    AkState,
)
from yonder.enums import PropID, RtpcAccum, SyncType
from yonder.gui.localization import µ
from yonder.gui.dialogs.choice_dialog import simple_choice_dialog
from .editable_table import add_widget_table
from .hash_widget import add_hash_widget
from .incomplete_enum import add_incomplete_int_enum
from .dpg_item import DpgItem
from .select_node import add_select_node


# TODO there is also a STMG bnk section, do we need to manage that too?


class add_states_table(DpgItem):
    """TODO

    Parameters
    ----------
    bnk : Soundbank
        Used to allocate new IDs for added RTPCs.
    states : list of RTPC
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
        states: StateChunk,
        on_value_changed: Callable[[str, StateChunk, Any], None],
        *,
        label: str = "States",
        tag: str | int = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self._bnk = bnk
        self._states = states
        self._on_value_changed = on_value_changed
        self._user_data = user_data

        if label:
            dpg.add_text(label)

        self._properties_table: add_widget_table = None
        self._states_table: add_widget_table = None
        self._build()

    # === Internal ======================================================

    def _build(self) -> None:
        with dpg.child_window(auto_resize_y=True, tag=self._tag):
            with dpg.tree_node(label=µ("Controlled Properties")):
                self._properties_table = add_widget_table(
                    self._states.state_property_info,
                    self._property_to_row,
                    new_item=self._new_property,
                    on_add=self._on_property_added,
                    on_remove=self._on_property_removed,
                    on_select=self._on_property_selected,
                    header_row=True,
                    columns=[µ("Property"), µ("Accumulation"), µ("in dB"), µ("States")],
                    add_item_label=µ("+ Property"),
                    tag=self._t("properties_table"),
                )

            with dpg.tree_node(label=µ("States"), default_open=True):
                self._states_table = add_widget_table(
                    self._states.state_group_chunks,
                    self._state_group_to_row,
                    new_item=self._new_state_group,
                    on_add=self._on_state_group_added,
                    on_remove=self._on_state_group_removed,
                    add_item_label=µ("+ State Group"),
                    tag=self._t("states_table"),
                )

    def _make_setter(
        self,
        obj: Any,
        field: str,
        transformer: Callable[[Any], Any] = None,
        callback: Callable[[str, tuple, Any], None] = None,
    ) -> Callable:
        def cb(sender: str, new_val: Any, cb_user_data: Any) -> None:
            if transformer:
                new_val = transformer(new_val)
            setattr(obj, field, new_val)
            if callback:
                callback(sender, (obj, field, new_val), cb_user_data)

            if self._on_value_changed:
                self._on_value_changed(self._tag, self._states, self._user_data)

        return cb

    # === Properties ======================================================

    def _property_to_row(self, prop: StatePropertyInfo, idx: int) -> None:
        dpg.add_combo(
            [p.name for p in self.get_free_properties()],
            default_value=prop.property.name,
            callback=self._make_setter(
                prop, "property", lambda s: PropID[s], self._properties_table.refresh
            ),
            user_data=idx,
        )
        dpg.add_combo(
            [a.name for a in RtpcAccum],
            default_value=prop.accum_type.name,
            callback=self._make_setter(prop, "accum_type", lambda s: RtpcAccum[s]),
            user_data=idx,
        )
        dpg.add_checkbox(
            default_value=(prop.in_db == 1),
            callback=self._make_setter(prop, "in_db", lambda b: int(b)),
            user_data=idx,
        )
        num_affecting_states = len(self.get_states_affecting_property())
        dpg.add_text(num_affecting_states)

    def _new_property(self, done: Callable[[StatePropertyInfo], None]) -> None:
        available = self.get_free_properties()
        if not available:
            return

        done(StatePropertyInfo(sorted(available)[0], RtpcAccum.Additive, 0))

    def _on_property_added(
        self,
        sender: str,
        info: tuple[int, StatePropertyInfo, list[StatePropertyInfo]],
        user_data: Any,
    ) -> None:
        self._states.state_property_info.append(info[1])

        if self._on_value_changed:
            self._on_value_changed(self.tag, self._states, self._user_data)

    def _on_property_removed(
        self,
        sender: str,
        info: tuple[int, StatePropertyInfo, list[StatePropertyInfo]],
        user_data: Any,
    ) -> None:
        self._states.state_property_info.pop(info[0])

        # Let user decide what to do with states that now refer to a different property
        def choice_callback(sender: str, idx: int, cb_user_data: Any) -> None:
            if idx == 0:
                # TODO update all affected states
                pass
            elif idx == 1:
                # TODO update affected non-shared states
                pass

        simple_choice_dialog(
            µ("Update affected states?"),
            [µ("All", "Non-shared", "No")],
            choice_callback,
            title=µ("Property removed"),
        )

        if self._on_value_changed:
            self._on_value_changed(self.tag, self._states, self._user_data)

    def _on_property_selected(
        self,
        sender: str,
        info: tuple[int, StatePropertyInfo, list[StatePropertyInfo]],
        user_data: Any,
    ) -> None:
        # TODO highlight affecting states
        pass

    # === State Groups ======================================================

    def _state_group_to_row(self, group: StateGroupChunk, idx: int) -> None:
        name = lookup_name(group.state_group_id, f"#{group.state_group_id}")

        # TODO connect edit dialog
        with dpg.tree_node(label=name):
            dpg.add_combo(
                [s.name for s in SyncType],
                default_value=group.sync_type.name,
                callback=self._make_setter(group, "sync_type", lambda s: SyncType[s]),
                user_data=group,
            )

            add_widget_table(
                group.states,
                self._state_value_to_row,
                new_item=self._create_state_value,
                on_add=self._on_state_value_added,
                on_remove=self._on_state_value_removed,
                add_item_label=µ("+ State Value"),
                user_data=group,
            )

    def _new_state_group(self, done: Callable[[StateGroupChunk], None]) -> None:
        done(StateGroupChunk())

    def _on_state_group_added(
        self,
        sender: str,
        info: tuple[int, StateGroupChunk, list[StateGroupChunk]],
        user_data: Any,
    ) -> None:
        self._states.state_group_chunks.append(info[1])

        if self._on_value_changed:
            self._on_value_changed(self.tag, self._states, self._user_data)

    def _on_state_group_removed(
        self,
        sender: str,
        info: tuple[int, StateGroupChunk, list[StateGroupChunk]],
        user_data: Any,
    ) -> None:
        self._states.state_group_chunks.pop(info[0])

        if self._on_value_changed:
            self._on_value_changed(self.tag, self._states, self._user_data)

    # === States ======================================================

    def _state_value_to_row(self, state_value: AkState, idx: int) -> None:
        with dpg.group():
            add_select_node(
                self._bnk.query,
                µ("State"),
                self._make_setter(state_value, "state_instance_id", lambda n: n.nid),
                self._get_state_summary,
                default=state_value.state_instance_id,
                node_type=State,
                user_data=idx,
            )
            dpg.add_spacer(height=5)

            state: State = self._bnk.get(state_value.state_instance_id)

            for i, prop in self.get_controlled_properties().items():
                affected = state and (i in state.parameters)
                param_idx = state.parameters.index(i) if affected else -1

                with dpg.group(horizontal=True):
                    dpg.add_checkbox(
                        label=prop.name,
                        default_value=affected,
                        enabled=bool(state),
                        callback=self._set_state_property_connected,
                        user_data=(state, prop),
                    )
                    dpg.add_input_double(
                        default_value=(
                            state.values[param_idx] if param_idx >= 0 else 0.0
                        ),
                        enabled=affected,
                        callback=self._set_state_property_value,
                        user_data=(state, prop),
                        # TODO will cause problems if the state is reused within the same chunk
                        tag=self._t(f"{state.id}_{prop.name}"),
                    )

    def _set_state_property_connected(
        self, sender: str, connected: bool, info: tuple[State, PropID]
    ) -> None:
        state, prop = info
        for prop_idx, p in self.get_controlled_properties():
            if p == prop:
                break
        else:
            raise RuntimeError(
                f"Requested to update connection for {prop}, but property is not controlled by state chunk"
            )

        prop_value_widget = self._t(f"{state.id}_{prop.name}")

        if connected:
            if prop_idx in state.parameters:
                raise RuntimeError(
                    f"State {state} is already connected to {prop}, this should not happen"
                )

            state.parameters.append(prop_idx)
            state.values.append(dpg.get_value(prop_value_widget))
            dpg.enable_item(prop_value_widget)
        else:
            if prop_idx not in state.parameters:
                raise RuntimeError(
                    f"State {state} is already disconnected from {prop}, this should not happen"
                )

            param_idx = state.parameters.index(prop_idx)
            state.parameters.pop(param_idx)
            state.values.pop(param_idx)
            dpg.disable_item(prop_value_widget)

    def _set_state_property_value(
        self, sender: str, new_val: float, info: tuple[State, PropID]
    ) -> None:
        state, prop = info
        for prop_idx, p in self.get_controlled_properties():
            if p == prop:
                break
        else:
            raise RuntimeError(
                f"Requested to update state value for {prop}, but property is not controlled by state chunk"
            )

        param_idx = state.parameters.index(prop_idx)
        state.values[param_idx] = new_val

    def _create_state_value(self, done: Callable[[AkState], None]) -> None:
        # TODO dialog with value hash and state node selector
        pass

    def _on_state_value_added(
        self,
        sender: str,
        info: tuple[int, AkState, list[AkState]],
        group: StateGroupChunk,
    ) -> None:
        group.states.append(info[1])

        if self._on_value_changed:
            self._on_value_changed(self.tag, self._states, self._user_data)

    def _on_state_value_removed(
        self,
        sender: str,
        info: tuple[int, AkState, list[AkState]],
        group: StateGroupChunk,
    ) -> None:
        group.states.pop(info[0])

        if self._on_value_changed:
            self._on_value_changed(self.tag, self._states, self._user_data)

    def _on_state_value_changed(self, sender: str, app_data: Any, idx: int) -> None:
        # TODO apply value to state value
        if self._on_value_changed:
            self._on_value_changed(self.tag, self._states, self._user_data)

    def _get_state_summary(self, state: State) -> list[str]:
        properties = self.get_controlled_properties()
        ret = []

        for idx, val in zip(state.parameters, state.values):
            prop = properties.get(idx)
            label = prop.name if prop else "?"
            ret.append(f"{label}: {val}")

        return ret

    # === Public ======================================================

    def refresh(self) -> None:
        self._properties_table.refresh()
        self._states_table.refresh()

    def get_free_properties(self) -> list[PropID]:
        used = {p.property for p in self._states.state_property_info}
        return [p for p in PropID if p not in used]

    def get_controlled_properties(self) -> dict[int, PropID]:
        return {i: p.property for i, p in enumerate(self._states.state_property_info)}

    def get_states_affecting_property(self, prop: PropID) -> dict[int, list[AkState]]:
        for prop_idx, prop_info in enumerate(self._states.state_property_info):
            if prop_info.property == prop:
                break
        else:
            return {}

        ret = {}
        for group in self._states.state_group_chunks:
            affecting = []
            for state_value in group.states:
                state: State = self._bnk.get(state_value.state_instance_id)
                if state and prop_idx in state.parameters:
                    affecting.append(state_value)

        return ret
