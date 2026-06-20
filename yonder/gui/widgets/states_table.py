from typing import Any, Callable, Literal
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode, Hash, lookup_name
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
from .editable_table import add_widget_table
from .hash_widget import add_hash_widget
from .dpg_item import DpgItem
from .select_node import add_select_node


# TODO there is also a STMG bnk section, do we need to manage that too?


class add_states_table(DpgItem):
    """Widget to give access to and edit state chunks. States work as global variables
    that can be set by the game to control how audio is played.

    Parameters
    ----------
    bnk : Soundbank
        Used to allocate new IDs for added RTPCs.
    states : StateChunk
        Initial states; mutated directly by the widget.
    on_value_changed : callable
        Fired as ``on_value_changed(tag, states, user_data)`` on any edit.
    jump_to : callable
        Lets the user jump to referenced State objects if provided.
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
        jump_to: Callable[[str, HIRCNode, Any], None] = None,
        label: str = "States",
        tag: str | int = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self._bnk = bnk
        self._states = states
        self._on_value_changed = on_value_changed
        self._user_data = user_data
        self._jump_to = jump_to

        if label:
            dpg.add_text(label)

        self._properties_table: add_widget_table = None
        self._states_table: add_widget_table = None
        self._build()

    # === Internal ======================================================

    def _build(self) -> None:
        with dpg.child_window(auto_resize_y=True, border=False, tag=self._tag):
            with dpg.tree_node(label=µ("Controlled Properties"), span_full_width=True):
                self._properties_table = add_widget_table(
                    self._states.state_property_info,
                    self._property_to_row,
                    new_item=self._new_property,
                    on_add=self._on_property_added,
                    on_remove=self._on_property_removed,
                    header_row=True,
                    columns=[
                        µ("Property"),
                        µ("Accumulation"),
                        µ("in dB"),
                        µ("Affected by"),
                    ],
                    column_policy=dpg.mvTable_SizingStretchProp,
                    add_item_label=µ("+ Property"),
                    tag=self._t("properties_table"),
                )

            with dpg.tree_node(
                label=µ("State Groups"), span_full_width=True, default_open=True
            ):
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

    def _bind_hash_context_menu(
        self, item_tag: str, obj: Any, attr: str, label: str
    ) -> None:
        def update_label(
            sender: str,
            info: tuple[StateGroupChunk, str, tuple[Hash, str]],
            user_data: Any,
        ) -> None:
            h = info[2]
            name = lookup_name(h, f"#{h}")
            dpg.set_item_label(item_tag, name)

        with dpg.popup(
            item_tag, mousebutton=dpg.mvMouseButton_Right, min_size=(100, 50)
        ):
            add_hash_widget(
                getattr(obj, attr),
                self._make_setter(obj, attr, lambda h: h[0], update_label),
                horizontal=False,
                string_label=label,
                width=120,
            )

    # === Properties ======================================================

    def _property_to_row(self, prop: StatePropertyInfo, idx: int) -> None:
        dpg.add_combo(
            [p.name for p in self.get_free_properties()],
            default_value=prop.property.name,
            callback=self._make_setter(
                prop, "property", lambda s: PropID[s], self.refresh
            ),
            width=-1,
            user_data=idx,
        )
        dpg.add_combo(
            [a.name for a in RtpcAccum],
            default_value=prop.accum_type.name,
            callback=self._make_setter(prop, "accum_type", lambda s: RtpcAccum[s]),
            width=-1,
            user_data=idx,
        )
        dpg.add_checkbox(
            default_value=(prop.in_db == 1),
            callback=self._make_setter(prop, "in_db", lambda b: int(b)),
            user_data=idx,
        )
        num_affecting_states = len(self.get_states_affecting_property(prop.property))
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
        from yonder.gui.dialogs.choice_dialog import simple_choice_dialog

        self._states.state_property_info.pop(info[0])

        # Let the user decide what to do with states that now would refer to a different property
        def choice_callback(sender: str, idx: int, cb_user_data: Any) -> None:
            if idx == 0:
                # Update all affected states
                self.update_states_on_property_removal(info[1].property, info[0], True)
                self.refresh()
            elif idx == 1:
                # Update affected non-shared states
                self.update_states_on_property_removal(info[1].property, info[0], False)
                self.refresh()

        simple_choice_dialog(
            µ("States refer to properties by index.\nUpdate affected states?"),
            [µ("All"), µ("Non-shared"), µ("No")],
            choice_callback,
            title=µ("Property removed"),
        )

        if self._on_value_changed:
            self._on_value_changed(self.tag, self._states, self._user_data)

    # === State Groups ======================================================

    def _state_group_to_row(self, group: StateGroupChunk, idx: int) -> None:
        name = lookup_name(group.state_group_id, f"#{group.state_group_id}")

        with dpg.tree_node(label=name, span_full_width=True) as tree_node:
            dpg.add_combo(
                [s.name for s in SyncType],
                default_value=group.sync_type.name,
                label=µ("Synchronization"),
                width=200,
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

        # Connect edit dialog
        self._bind_hash_context_menu(
            tree_node, group, "state_group_id", µ("State Group")
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
        name = lookup_name(state_value.state_id, f"#{state_value.state_id}")
        
        state: State = self._bnk.get(state_value.state_instance_id)
        properties = self.get_controlled_properties()
        longest_prop = max(len(p.name) for p in properties.values())

        if state:
            referees = len(list(self._bnk.tree.predecessors(state.id)))
        else:
            referees = "?"

        def new_state() -> State:
            new = State(self._bnk.new_id())
            self._bnk.add_nodes(new)
            return new

        with dpg.tree_node(label=name, span_full_width=True) as tree_node:
            add_select_node(
                self._bnk.query,
                µ("State ({num_references} refs)").format(num_references=referees),
                self._make_setter(state_value, "state_instance_id", lambda n: n.nid),
                jump_to=self._jump_to,
                create_new=new_state,
                get_node_details=self._get_state_summary,
                default=state_value.state_instance_id,
                textbox_width=300,
                node_type=State,
                user_data=idx,
            )
            dpg.add_spacer(height=5)

            for i, prop in properties.items():
                affected = state and (i in state.parameters)
                param_idx = state.parameters.index(i) if affected else -1
                value_widget_id = self._get_state_prop_value_widgets(state, prop)[-1]

                with dpg.group(horizontal=True):
                    dpg.add_text(prop.name.rjust(longest_prop))
                    dpg.add_checkbox(
                        #label=prop.name.ljust(longest_prop),
                        default_value=affected,
                        enabled=bool(state),
                        callback=self._set_state_property_connected,
                        user_data=(state, prop),
                    )
                    dpg.add_input_float(
                        default_value=(
                            state.values[param_idx] if param_idx >= 0 else 0.0
                        ),
                        width=220,
                        enabled=affected,
                        callback=self._set_state_property_value,
                        user_data=(state, prop),
                        tag=value_widget_id,
                    )

        # Connect edit dialog
        self._bind_hash_context_menu(
            tree_node, state_value, "state_id", µ("State Value")
        )

    def _get_state_prop_value_widgets(self, state: State, prop: PropID) -> list[str]:
        offset = 0
        ret = [self._t(f"{state.id}_{prop.name}_#{offset}")]

        while dpg.does_item_exist(ret[-1]):
            offset += 1
            ret.append(self._t(f"{state.id}_{prop.name}_#{offset}"))
        
        return ret

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

        value_widgets = self._get_state_prop_value_widgets(state, prop)[:-1]
        value = dpg.get_value(value_widgets[-1])

        if connected:
            if prop_idx in state.parameters:
                raise RuntimeError(
                    f"State {state} is already connected to {prop}, this should not happen"
                )

            state.parameters.append(prop_idx)
            state.values.append(value)
            
            for widget in value_widgets:
                dpg.configure_item(widget, enabled=True, default_value=value)
        else:
            if prop_idx not in state.parameters:
                raise RuntimeError(
                    f"State {state} is already disconnected from {prop}, this should not happen"
                )

            param_idx = state.parameters.index(prop_idx)
            state.parameters.pop(param_idx)
            state.values.pop(param_idx)
            
            for widget in value_widgets:
                dpg.disable_item(widget)

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
        done(AkState())

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

    def _get_state_summary(self, state: State) -> list[str]:
        properties = self.get_controlled_properties()
        ret = []

        for idx, val in zip(state.parameters, state.values):
            prop = properties.get(idx)
            label = prop.name if prop else f"(p{idx})"
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

            if affecting:
                ret[group.state_group_id] = affecting

        return ret

    def update_states_on_property_removal(self, prop: PropID, prop_idx: int, include_shared: bool = False) -> None:
        for group in self._states.state_group_chunks:
            for aks in group.states:
                if not include_shared and self._bnk.tree.in_degree(aks.state_instance_id) > 1:
                    continue

                state: State = self._bnk.get(aks.state_instance_id)
                if not state:
                    continue

                param_idx = state.parameters.index(prop_idx)
                state.parameters.pop(param_idx)
                state.values.pop(param_idx)

                # Subsequent params need to be shifted so they point at the correct property again
                for idx in range(param_idx, len(state.parameters)):
                    state.parameters[idx] -= 1
