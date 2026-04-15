from __future__ import annotations
from typing import Any
import re
import json
from copy import deepcopy
from dataclasses import dataclass, is_dataclass, fields, replace

from yonder.util import deepmerge
from yonder.types.serialization import serialize


@dataclass
class DataNode:
    def get_value(self, path: str) -> Any:
        obj = self
        for part in path.split("/"):
            if ":" in part:
                key, idx = part.split(":")
                obj = getattr(obj, key)[int(idx)]
            else:
                obj = getattr(obj, part)

        return obj

    def set_value(self, path: str, new_val: Any, strict: bool = True) -> None:
        if "/" in path:
            trail, key = path.rsplit("/", maxsplit=1)
            obj = self.get_value(trail)
        else:
            key = path
            obj = self

        if strict:
            old_val = getattr(obj, key)
            if old_val is not None and type(old_val) is not type(new_val):
                raise ValueError(
                    f"Cannot set {path}: incompatible types ({old_val}, {new_val})"
                )

        setattr(obj, key, new_val)

    def json(self) -> str:
        return json.dumps(serialize(self), indent=2)

    def copy(self) -> DataNode:
        def delve(obj):
            if not is_dataclass(obj):
                return deepcopy(obj)

            repl = {f.name: getattr(obj, f.name) for f in fields(obj) if f.init}
            return replace(obj, **repl)

        return delve(self)

    def merge(self, other: dict | DataNode) -> None:
        deepmerge(self, other)

    def glob(self, pattern: str) -> list[tuple[str, object]]:
        segs = re.split(r"/|(?=:)", pattern)
        results = []

        def match(node: Any, seg_idx: int, path: str):
            if seg_idx == len(segs):
                results.append((path, node))
                return

            seg = segs[seg_idx]

            if seg == "**":
                # Check if this object already matches
                match(node, seg_idx + 1, path)

                # Recurse deeper through fields and list items
                if is_dataclass(node):
                    for f in fields(node):
                        child_path = f"{path}/{f.name}" if path else f.name
                        match(getattr(node, f.name), seg_idx, child_path)
                
                elif isinstance(node, list):
                    for i, child in enumerate(node):
                        match(child, seg_idx, f"{path}:{i}")

            elif seg.startswith(":"):
                if not isinstance(node, list):
                    raise ValueError(f"{pattern} with array access {seg} lead to non-array value")
                
                index = seg[1:]
                indices = range(len(node)) if index == "*" else [int(index)]
                for i in indices:
                    child_path = f"{path}:{i}" if path else f":{i}"
                    match(node[i], seg_idx + 1, child_path)

            elif is_dataclass(node):
                for f in fields(node):
                    if seg in ("*", f.name):
                        child_path = f"{path}/{f.name}" if path else f.name
                        match(getattr(node, f.name), seg_idx + 1, child_path)

        match(self, 0, "")
        return results

    def __contains__(self, item: str) -> bool:
        if not isinstance(item, str):
            return False

        try:
            self.get_value(item)
            return True
        except Exception:
            return False

    def __getitem__(self, path: str) -> Any:
        return self.get_value(path)

    def __setitem__(self, path: str, val: Any) -> Any:
        self.set_value(path, val)
