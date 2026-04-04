from typing import Any, Type, TypeVar, get_type_hints, get_origin, get_args
from dataclasses import is_dataclass, fields
import keyword
from enum import Enum, StrEnum


def serialize(obj: Any) -> dict:
    if hasattr(obj, "validate") and callable(obj.validate):
        obj.validate()
    
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()

    if is_dataclass(obj) and not isinstance(obj, type):
        result = {}
        for f in fields(obj):
            value = getattr(obj, f.name)
            # Some words like "from" or "except" are valid in wwise but reserved in python
            key = f.name.rstrip("_")
            result[key] = serialize(value)
        return result

    if isinstance(obj, list):
        return [serialize(x) for x in obj]

    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}

    if isinstance(obj, Enum):
        if isinstance(obj, StrEnum):
            return obj.value
        return obj.name

    return obj


def _parse_value(target_type: Type, value: Any):
    if issubclass(target_type, Enum):
        if isinstance(value, str):
            if issubclass(target_type, StrEnum):
                if value in target_type:
                    return target_type(value)
            return target_type[value]
        return target_type(value)

    if issubclass(target_type, TypeVar):
        origin = target_type.__bound__
        args = [Any, Any]
    else:
        origin = get_origin(target_type) or target_type
        args = get_args(target_type) or [Any, Any]

    if origin is list:
        item_type = args[0]
        return [_parse_value(item_type, item) for item in value]

    if origin is dict:
        key_type, val_type = (args[0], args[1])
        return {
            _parse_value(key_type, k): _parse_value(val_type, v)
            for k, v in value.items()
        }

    # Concrete dataclass or class with from_dict
    if isinstance(value, dict):
        if hasattr(target_type, "from_dict") and callable(target_type.from_dict):
            return target_type.from_dict(value)

        if is_dataclass(target_type):
            return deserialize(target_type, value)

    return value


def deserialize(target_type: Type, data: dict) -> Any:
    if hasattr(target_type, "from_dict") and callable(target_type.from_dict):
        return target_type.from_dict(data)

    if not is_dataclass(target_type):
        raise TypeError(f"{target_type} is not a dataclass and has no from_dict method")

    hints = get_type_hints(target_type)
    kwargs = {}

    for f in fields(target_type):
        if f.name not in data:
            # Missing keys fall back to the field's default
            continue

        value = data[f.name]
        field_type = hints[f.name]
        
        # Some words like "from" or "except" are valid in wwise but reserved in python
        key = f.name
        if keyword.iskeyword(key):
            key += "_"

        kwargs[key] = _parse_value(field_type, value)

    return target_type(**kwargs)
