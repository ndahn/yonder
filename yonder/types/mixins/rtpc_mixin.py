from yonder.types.base_types import RTPC


# NOTE: mixed class must expose an "rtpcs" member
class RtpcMixin:
    # Dummies, just for the type checker
    rtpcs: list[RTPC]

    # Only serves to identify classes with rtpc support for now, 
    # may add stuff to this later
