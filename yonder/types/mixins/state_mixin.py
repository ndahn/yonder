from yonder.types.state import State
from yonder.types.base_types import StateChunk, StateGroupChunk, StateGroup, StatePropertyInfo, AkState
from yonder.enums import PropID, RtpcAccum, SyncType


# NOTE: mixed class must expose a "states" member
# (node) -> StatePropertyInfo & StateChunk -> StateGroupChunk -> AkState -> State
class StateMixin:
    pass
