from typing import Any
import dataclasses
import dacite
from enum import Enum

from .rewwise_action_params import (
    ActionParams,
    ACTION_TYPE_MAP,
)
from .rewwise_nodes import BODY_TYPE_MAP
from .rewwise_soundbank import ObjectId, HIRCObjectBody
from .rewwise_enums import (
    AkCurveInterpolation,
    AkPropID,
    AkParameterID,
    AkValueMeaning,
    AkPathMode,
    Ak3DSpatializationMode,
    AkSpeakerPanningType,
    Ak3DPositionType,
    AkVirtualQueueBehavior,
    AkBelowThresholdBehavior,
    AkSyncType,
    AkSyncTypeU8,
    AkRtpcAccum,
    AkRtpcType,
    AkCurveScaling,
    AkGroupType,
    AkDecisionTreeMode,
    AkClipAutomationType,
    SourceType,
    PluginId,
)


DACITE_CONFIG = dacite.Config(
    type_hooks={
        ObjectId: lambda d: ObjectId(next(d.values())),
        HIRCObjectBody: lambda d: dacite.from_dict(
            BODY_TYPE_MAP[d["body_type"]], d, DACITE_CONFIG
        ),
        # TODO needs custom deserialization to handle PlayEvent actions (str, not dict)
        ActionParams: lambda d, action_type: dacite.from_dict(
            ACTION_TYPE_MAP[action_type], d, DACITE_CONFIG
        ),
        # Enums are serialized by name
        AkCurveInterpolation: lambda v: AkCurveInterpolation[v],
        AkPropID: lambda v: AkPropID[v],
        AkParameterID: lambda v: AkParameterID[v],
        AkValueMeaning: lambda v: AkValueMeaning[v],
        AkPathMode: lambda v: AkPathMode[v],
        Ak3DSpatializationMode: lambda v: Ak3DSpatializationMode[v],
        AkSpeakerPanningType: lambda v: AkSpeakerPanningType[v],
        Ak3DPositionType: lambda v: Ak3DPositionType[v],
        AkVirtualQueueBehavior: lambda v: AkVirtualQueueBehavior[v],
        AkBelowThresholdBehavior: lambda v: AkBelowThresholdBehavior[v],
        AkSyncType: lambda v: AkSyncType[v],
        AkSyncTypeU8: lambda v: AkSyncTypeU8[v],
        AkRtpcAccum: lambda v: AkRtpcAccum[v],
        AkRtpcType: lambda v: AkRtpcType[v],
        AkCurveScaling: lambda v: AkCurveScaling[v],
        AkGroupType: lambda v: AkGroupType[v],
        AkDecisionTreeMode: lambda v: AkDecisionTreeMode[v],
        AkClipAutomationType: lambda v: AkClipAutomationType[v],
        SourceType: lambda v: SourceType[v],
        PluginId: lambda v: PluginId[v],
    },
)


def serialize(obj: Any) -> dict:
    if isinstance(obj, ObjectId):
        value = obj.value()
        if isinstance(value, str):
            return {"String": value}
        return {"Hash": value}

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        # NOTE not using asdict since we have a couple of custom serializations
        d = {k: serialize(v) for k, v in vars(obj).items()}
        if isinstance(obj, HIRCObjectBody.__args__):
            d["body_type"] = type(obj).body_type
        return d
    
    if isinstance(obj, list):
        return [serialize(i) for i in obj]
    
    if isinstance(obj, Enum):
        return obj.name
    
    return obj


def deserialize(data_cls: type, obj: dict) -> Any:
    return dacite.from_dict(data_cls, obj, DACITE_CONFIG)


# TODO needs proper testing
# TODO move node types into separate modules?
# TODO add helper functions where useful
