from typing import TYPE_CHECKING

from yonder.hash import Hash, calc_hash
from yonder.types.state import State
from yonder.types.base_types import StateChunk, StateGroupChunk, StatePropertyInfo, AkState
from yonder.enums import PropID, RtpcAccum

if TYPE_CHECKING:
    from yonder import Soundbank


# NOTE: mixed class must expose a "states" member
# (node) -> StatePropertyInfo & StateChunk -> StateGroupChunk -> AkState -> State
class StateMixin:
    # Dummies, just for the type checker
    states: StateChunk

    def get_free_properties(self) -> list[PropID]:
        used = {p.property for p in self.states.state_property_info}
        return [p for p in PropID if p not in used]

    def get_controlled_properties(self) -> dict[int, PropID]:
        return {i: p.property for i, p in enumerate(self.states.state_property_info)}

    def get_states_affecting_property(self, prop: PropID) -> dict[int, list[AkState]]:
        for prop_idx, prop_info in enumerate(self.states.state_property_info):
            if prop_info.property == prop:
                break
        else:
            return {}

        ret = {}
        for group in self.states.state_group_chunks:
            affecting = []
            for state_value in group.states:
                state: State = self._bnk.get(state_value.state_instance_id)
                if state and prop_idx in state.parameters:
                    affecting.append(state_value)

            if affecting:
                ret[group.state_group_id] = affecting

        return ret

    def get_state(self, bnk: Soundbank, state_group_id: Hash, state_value_id: Hash, unique: bool = True) -> State:
        if isinstance(state_group_id, str):
            state_group_id = calc_hash(state_group_id)

        if isinstance(state_value_id, str):
            state_value_id = calc_hash(state_value_id)

        # Locate state group
        for group in self.states.state_group_chunks:
            if group.state_group_id == state_group_id:
                break
        else:
            group = StateGroupChunk(state_group_id)
            self.states.state_group_chunks.append(group)

        # Check if state value is already present
        for value in group.states:
            if value.state_id == state_value_id:
                break
        else:
            value = AkState(state_value_id, 0)
            group.states.append(value)

        # Locate the state object
        state_obj = bnk.get(value.state_instance_id)
        if state_obj and unique:
            if state_obj.is_shared():
                # It's shared with other nodes, don't use it
                state_obj = None
            
        if not state_obj:
            state_obj = State(bnk.new_id())
            value.state_instance_id = state_obj.id
            bnk.add_nodes(state_obj)

        return state_obj

    def remove_ctrl_state(self, bnk: Soundbank, state_group_id: Hash, *state_value_ids: Hash) -> None:
        if isinstance(state_group_id, str):
            state_group_id = calc_hash(state_group_id)

        state_value_ids = list(state_value_ids)
        for idx, value_id in enumerate(state_value_ids):
            if isinstance(value_id, str):
                state_value_ids[idx] = calc_hash(value_id)

        # Locate state group
        for group in self.states.state_group_chunks:
            if group.state_group_id == state_group_id:
                break
        else:
            return

        # Remove 
        for idx, value in enumerate(group.states):
            if not state_value_ids or value.state_id in state_value_ids:
                group.states.pop(idx)
                state: State = bnk.get(value.state_instance_id)
                if state and not state.is_shared():
                    bnk.delete_nodes(state)

    def remove_ctrl_property(self, bnk: Soundbank, property: PropID) -> None:
        for prop_idx, info in enumerate(self.states.state_property_info):
            if info.property == property:
                break
        else:
            return

        self.states.state_property_info.pop(prop_idx)

        for group in self.states.state_group_chunks:
            del_values = set()
            del_states = []

            for val_idx, value in enumerate(group.states):
                state_obj: State = bnk.get(value.state_instance_id)
                
                if not state_obj:
                    continue

                if prop_idx not in state_obj.parameters:
                    continue

                state_obj.delete_param(prop_idx)
                if not state_obj.parameters:
                    # Mark empty states and state values for deletion
                    del_values.add(val_idx)
                    del_states.append(state_obj)

            # Empty groups are allowed to remain
            group.states = [s for i, s in enumerate(group.states) if i not in del_values]
            bnk.delete_nodes(*del_states)
    
    def set_state_ctrl(self, bnk: Soundbank, state_group_id: Hash, state_value_id: Hash, modifiers: dict[PropID, float], update: bool = False, unique: bool = True) -> State:
        state_obj = self.get_state(bnk, state_group_id, state_value_id, unique=unique)
        if not update:
            state_obj.clear_params()
        
        # Update property info
        property_map = {p.property: i for i, p in enumerate(self.states.state_property_info)}
        for prop in modifiers.keys():
            if prop not in property_map:
                self.states.state_property_info.append(
                    StatePropertyInfo(
                        prop,
                        RtpcAccum.Additive,
                    )
                )
                property_map[prop] = len(self.states.state_property_info)

        # Set the property values on the state object
        for prop, val in modifiers.items():
            prop_idx = property_map[prop]
            state_obj.set_param(prop_idx, val)

        return state_obj
