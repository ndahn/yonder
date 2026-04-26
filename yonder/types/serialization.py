from __future__ import annotations
import sys
from typing import Any, Type, get_origin, get_args, Union
from dataclasses import is_dataclass, fields, InitVar, Field
import keyword
import inspect
from enum import Enum, StrEnum

from yonder.util import resolve_typehint, get_module_for_field, logger


class WrongValueTypeError(RuntimeError):
    def __init__(
        self, obj: Any, fields: list[str], mismatches: list[tuple[type, type]]
    ):
        super().__init__()
        self.obj = obj
        self.fields = fields
        self.mismatches = mismatches

    def __str__(self):
        if len(self.fields) == 1:
            m = self.mismatches[0]
            return (
                f"{self.obj}: field {self.fields[0]} does not match expected type"
                f"(expected: {m[0].__name__}, is: {m[1].__name__})"
            )
        else:
            details = "\n".join(
                f" - {f} (expected: {m[0].__name__}, is: {m[1].__name__})"
                for f, m in zip(self.fields, self.mismatches)
            )
            return f"{self.obj}: multiple fields don't match their expected types:\n{details}"


def serialize(obj: Any) -> Any:
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()

    return _serialize_value(obj)


def _serialize_value(obj: Any) -> Any:
    verify_values(obj, False)

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
        return obj.name.rstrip("_")

    return obj


def deserialize(target_type: Type, data: dict) -> Any:
    if hasattr(target_type, "from_dict") and callable(target_type.from_dict):
        return target_type.from_dict(data)

    return _deserialize_fields(target_type, data)


def _deserialize_fields(target_type: Type, data: dict) -> Any:
    if not is_dataclass(target_type):
        raise TypeError(f"{target_type} is not a dataclass and has no from_dict method")

    hints = _get_hints(target_type)
    kwargs = {}

    if "__init__" in target_type.__dict__:
        sig = inspect.signature(target_type.__init__)
        # Skip self, *args and **kwargs
        target_fields = [
            name
            for name, param in sig.parameters.items()
            if name != "self"
            and param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD)
        ]
    else:
        target_fields = [f.name for f in fields(target_type)]

    for f in target_fields:
        # Some words like "from" or "except" are valid in wwise but reserved in python
        value = data[f.rstrip("_")]
        field_type = hints[f]
        kwargs[f] = _parse_value(field_type, value)

    ret = target_type(**kwargs)
    verify_values(ret, False)

    return ret


def _parse_value(target_type: Type, value: Any) -> Any:
    origin = get_origin(target_type) or target_type
    args = get_args(target_type) or [Any, Any]

    if isinstance(origin, InitVar):
        origin = origin.type

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


def _get_hints(target_type: Type) -> dict[str, Any]:
    hints = {}
    for cls in reversed(target_type.__mro__):
        if cls is object:
            continue

        ann = cls.__dict__.get("__annotations__", {})
        module = sys.modules.get(cls.__module__, None)
        globalns = getattr(module, "__dict__", {}) if module else {}
        for name, hint in ann.items():
            if isinstance(hint, str):
                try:
                    hint = eval(hint, globalns)
                except NameError:
                    pass  # leave unresolvable hints as strings
            hints[name] = hint

    return hints


def verify_values(obj, raise_on_error: bool) -> None:
    if hasattr(obj, "validate") and callable(obj.validate):
        obj.validate()

    if not is_dataclass(obj):
        return

    ctx = str(obj)
    wrong_fields: list[str] = []
    mismatches: list[tuple[type, type]] = []

    def has_valid_type(val: Any, types: type | tuple[type]) -> bool:
        if isinstance(types, type):
            types = (types,)

        types = tuple(types)

        if isinstance(val, float) and int in types:
            if val.is_integer():
                return True

        if isinstance(val, int) and float in types:
            return True

        if not isinstance(val, types):
            return False

        return True

    for f in fields(obj):
        fmod = get_module_for_field(obj, f.name)
        tp = resolve_typehint(f.type, fmod)
        origin = get_origin(tp) or tp
        val = getattr(obj, f.name)

        if issubclass(origin, Enum):
            if not has_valid_type(val, (origin, str, int)):
                wrong_fields.append(f.name)
                mismatches.append((type(val), origin))
            
            continue

        if origin is Union:
            logger.warning(f"{ctx}: field {f.name} has union type")
            continue

        if not has_valid_type(val, origin):
            wrong_fields.append(f.name)
            mismatches.append((type(val), origin))

        if is_dataclass(val):
            verify_values(val, raise_on_error)
        elif isinstance(val, list):
            args = get_args(tp)
            if not args:
                logger.warning(
                    f"{ctx}: incomplete type annotation {tp} of field {f.name}"
                )
            else:
                item_tp = args[0]
                for idx, item in enumerate(val):
                    if not has_valid_type(item, item_tp):
                        wrong_fields.append(f"{f.name}:{idx}")
                        mismatches.append((type(item), item_tp))
                    verify_values(item, raise_on_error)

    if wrong_fields:
        e = WrongValueTypeError(obj, wrong_fields, mismatches)
        if raise_on_error:
            raise e
        else:
            logger.error(str(e))
