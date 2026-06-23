from typing import TYPE_CHECKING

from yonder.hash import Hash, calc_hash
from yonder.types.state import State
from yonder.types.base_types import StateChunk, StateGroupChunk, StateGroup, StatePropertyInfo, AkState
from yonder.enums import PropID, RtpcAccum, SyncType

if TYPE_CHECKING:
    from yonder import Soundbank


# NOTE: mixed class must expose a "states" member
# (node) -> StatePropertyInfo & StateChunk -> StateGroupChunk -> AkState -> State
class StateMixin:
    # TODO move helper functions from states_table here
    
    def set_state_ctrl(self, bnk: Soundbank, state_group: Hash, state_value: str, modifiers: dict[PropID, float], update: bool = False) -> State:
        if isinstance(state_group, str):
            state_group = calc_hash(state_group)

        if isinstance(state_value, str):
            state_value = calc_hash(state_value)

        # Update property info
        property_map = {p.property: i for i, p in enumerate(self.state_property_info)}
        for prop in modifiers.keys():
            if prop not in property_map:
                self.state_property_info.append(
                    StatePropertyInfo(
                        prop,
                        RtpcAccum.Additive,
                    )
                )
                property_map[prop] = len(self.state_property_info)

        # Locate state group
        for group in self.state_group_chunks:
            if group.state_group_id == state_group:
                break
        else:
            group = StateGroupChunk(state_group)
            self.state_group_chunks.append(group)

        # Check if state value is already present
        for value in group.states:
            if value.state_id == state_value:
                break
        else:
            value = AkState(state_value, 0)
            group.states.append(value)

        # Locate the state object
        state_obj = bnk.get(value.state_instance_id)
        if state_obj and not update:
            # There is a state object and all values should be replaced
            refs = len(bnk.get_tree().in_degree(state_obj.id))
            if refs <= 1:
                # It's only used by this node, fine to clear
                state_obj.clear_params()
            else:
                # Also used by other nodes, we'll create our own object
                state_obj = None

        # No usable state object found, create a new one
        if not state_obj:
            state_obj = State(bnk.new_id())
            value.state_instance_id = state_obj.id
            bnk.add_nodes(state_obj)

        # Set the property values on the state object
        for prop, val in modifiers.items():
            prop_idx = property_map[prop]
            state_obj.set_param(prop_idx, val)

        return state_obj
