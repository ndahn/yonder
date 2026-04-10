from __future__ import annotations
from typing import Any, Callable, Iterable, ClassVar, TYPE_CHECKING
from collections.abc import MutableMapping
import sys
import re
from pathlib import Path
from dataclasses import dataclass, is_dataclass, fields, asdict
from docstring_parser import parse as doc_parse
import inspect
import builtins
import logging
import subprocess
import shutil
import networkx as nx
from field_properties.field_properties import BaseFieldProperty

from yonder.enums import SoundType

if TYPE_CHECKING:
    from yonder import Soundbank


logging.basicConfig(
    level=logging.DEBUG,
    format="[%(levelname)s]\t%(message)s",
    handlers=[
        # logging.FileHandler(logfile),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("yonder")


def resource_dir() -> Path:
    return Path(sys.argv[0]).parent / "resources"


def resource_data(res_path: str, binary: bool = False) -> str | bytes:
    res = resource_dir() / res_path
    if binary:
        return res.read_bytes()
    return res.read_text()


def unpack_soundbank(bnk2json_exe: Path, bnk_path: Path) -> Path:
    # NOTE in a compiled application (pyinstaller), check_output
    # will not work anymore after importing sounddevice...
    # See https://github.com/spatialaudio/python-sounddevice/issues/461
    subprocess.check_call([str(bnk2json_exe), str(bnk_path)])
    return bnk_path.parent / bnk_path.stem / "soundbank.json"


def repack_soundbank(bnk2json_exe: Path, bnk_dir: Path) -> Path:
    if bnk_dir.name == "sounbank.json":
        bnk_dir = bnk_dir.parent

    subprocess.check_call([str(bnk2json_exe), str(bnk_dir)])

    # Rename the backup and new soundbank to make things a little easier for the user
    old_file = bnk_dir.parent / (bnk_dir.stem + ".bnk")
    new_file = bnk_dir.parent / (bnk_dir.stem + ".created.bnk")
    shutil.move(old_file, str(old_file) + ".bak")
    shutil.move(new_file, old_file)

    return bnk_dir.parent / (bnk_dir.stem + ".bnk")


def is_event_name_valid(name: str) -> bool:
    return bool(re.match(rf"{SoundType.values()}[0-9]+"))


def format_hierarchy(bnk: Soundbank, graph: nx.DiGraph) -> str:
    visited = set()
    ret = ""

    def delve(nid: Any, prefix: str):
        nonlocal ret

        if nid in visited:
            return

        visited.add(nid)
        children = list(graph.successors(nid))

        for i, child_id in enumerate(children):
            is_last = i == len(children) - 1
            branch = "└──" if is_last else "├──"
            node = bnk.get(child_id, f"#{child_id}")
            ret += f"{prefix}{branch} {node}\n"

            new_prefix = prefix + ("    " if is_last else "│   ")
            delve(child_id, new_prefix)

    # Find root node
    roots = [n for n in graph.nodes() if graph.in_degree(n) == 0]
    if not roots:
        logger.warning("Could not determine root node")
        return

    root = roots[0]
    if len(roots) > 1:
        logger.warning(f"Multiple roots found, using {root}")

    delve(root, "")
    return ret.rstrip("\n")


@dataclass
class FuncArg:
    undefined = object()

    name: str
    type: type
    default: Any = None
    doc: str = None


def get_function_spec(
    func: Callable, undefined: Any = FuncArg.undefined
) -> dict[str, FuncArg]:
    func_args = {}
    sig = inspect.signature(func)

    param_doc = {}
    if func.__doc__:
        parsed_doc = doc_parse(func.__doc__)
        param_doc = {p.arg_name: p.description for p in parsed_doc.params}

    # Create CLI options for click
    for param in sig.parameters.values():
        ptype = None
        default = undefined

        if param.annotation is not param.empty:
            ptype = param.annotation
            if ptype and isinstance(ptype, str):
                # If it's a primitive type we can parse it, otherwise ignore it
                # NOTE use the proper builtins module here, __builtins__ is unreliable
                ptype = getattr(builtins, ptype, None)

        if param.default is not inspect.Parameter.empty:
            default = param.default

            if ptype is None and default is not None:
                ptype = type(default)

        func_args[param.name] = FuncArg(
            param.name, ptype, default, param_doc.get(param.name)
        )

    return func_args


def deepmerge(base: dataclass, updates: "dict | dataclass") -> None:
    def apply_dict(obj, data: dict) -> None:
        for f in fields(obj):
            if f.name not in data:
                continue

            if hasattr(type(obj), f.name):
                true_field_type = type(getattr(type(obj), f.name))
                if issubclass(true_field_type, property):
                    if not true_field_type.fset:
                        continue
                    if issubclass(true_field_type, BaseFieldProperty):
                        continue

            value = data[f.name]
            current = getattr(obj, f.name)

            if is_dataclass(current):
                apply_dict(current, value)
            elif isinstance(current, dict):
                current.clear()
                current.update(value)
            elif isinstance(current, list):
                current.clear()
                current.extend(value)
            else:
                setattr(obj, f.name, value)

    if is_dataclass(updates):
        updates = asdict(updates)

    return apply_dict(base, updates)


def to_typed_dict(data: dataclass) -> dict[str, tuple[type, Any]]:
    def delve(d: Any) -> Any:
        if is_dataclass(d):
            ret = {}
            for f in fields(d):
                val = getattr(d, f.name)
                ret[f.name] = (f.type, delve(val))
            return ret

        elif isinstance(d, dict):
            return {k: delve(v) for k, v in d.items()}

        elif isinstance(d, list):
            return [delve(x) for x in d]

        return d

    return delve(data)


class PathDict(MutableMapping):
    @classmethod
    def from_paths(cls, paths: Iterable[tuple[str, Any]]) -> PathDict:
        d = PathDict({})
        for key, val in paths:
            d[key] = val

        return d

    def __init__(self, d: dict):
        self._d = d

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str) and "/" in key:
            node = self._d
            for k in key.split("/"):
                node = node[k]
            return node

        return self._d[key]

    def __setitem__(self, key: Any, value: Any) -> None:
        if isinstance(key, str) and "/" in key:
            *parts, last = key.split("/")
            node = self._d
            for k in parts:
                node = node[k]
            node[last] = value
        else:
            self._d[key] = value

    def __delitem__(self, key):
        del self._d[key]

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)

    def __getattr__(self, name) -> Any:
        return getattr(self._d, name)
