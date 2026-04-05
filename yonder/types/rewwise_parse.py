from typing import Any, Type, get_type_hints, get_origin, get_args
from dataclasses import is_dataclass, fields
import keyword
from enum import Enum, StrEnum


def serialize(obj: Any) -> Any:
    if hasattr(obj, "validate") and callable(obj.validate):
        obj.validate()

    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()

    return _serialize_value(obj)


def _serialize_value(obj: Any) -> Any:
    if not is_dataclass(obj) and hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
        
    if is_dataclass(obj) and not isinstance(obj, type):
        result = {}
        for f in fields(obj):
            value = getattr(obj, f.name)
            # Some words like "from" or "except" are valid in wwise but reserved in python
            key = f.name.rstrip("_")
            result[key] = _serialize_value(value)
        return result

    if isinstance(obj, list):
        return [_serialize_value(x) for x in obj]

    if isinstance(obj, dict):
        return {k: _serialize_value(v) for k, v in obj.items()}

    if isinstance(obj, Enum):
        if isinstance(obj, StrEnum):
            return obj.value
        return obj.name

    return obj


def deserialize(target_type: Type, data: dict) -> Any:
    if hasattr(target_type, "from_dict") and callable(target_type.from_dict):
        return target_type.from_dict(data)

    return _deserialize_fields(target_type, data)


def _deserialize_fields(target_type: Type, data: dict) -> Any:
    if not is_dataclass(target_type):
        raise TypeError(f"{target_type} is not a dataclass and has no from_dict method")

    hints = get_type_hints(target_type)
    kwargs = {}
    for f in fields(target_type):
        if not f.init:
            continue

        # Some words like "from" or "except" are valid in wwise but reserved in python
        key = f.name
        if keyword.iskeyword(key):
            key += "_"

        raw_key = f.name.rstrip("_") if key != f.name else f.name
        if raw_key not in data and f.name not in data:
            continue  # fall back to field default

        value = data.get(f.name, data.get(raw_key))
        field_type = hints[f.name]
        kwargs[key] = _parse_value(field_type, value)

    return target_type(**kwargs)


def _parse_value(target_type: Type, value: Any) -> Any:
    origin = get_origin(target_type) or target_type
    args = get_args(target_type) or [Any, Any]

    if issubclass(origin, Enum):
        if isinstance(value, str):
            if keyword.iskeyword(value):
                value += "_"
                
            if issubclass(origin, StrEnum):
                if value in origin:
                    return origin(value)
            return origin[value]
        return origin(value)

    if origin is list:
        item_type = args[0]
        return [_parse_value(item_type, item) for item in value]

    if origin is dict:
        key_type, val_type = args[0], args[1]
        return {
            _parse_value(key_type, k): _parse_value(val_type, v)
            for k, v in value.items()
        }

    if isinstance(value, dict):
        if hasattr(origin, "from_dict") and callable(origin.from_dict):
            return origin.from_dict(value)
        
        if is_dataclass(origin):
            return _deserialize_fields(origin, value)

    return value
