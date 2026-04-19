from __future__ import annotations
from typing import Any, Callable, Iterable, TYPE_CHECKING
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

from yonder.enums import SoundType
from yonder.hash import calc_hash

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
    return res.read_text(encoding="utf8")


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
                if hasattr(builtins, ptype):
                    ptype = getattr(builtins, ptype)
                else:
                    ptype = resolve_typehint(ptype, func.__module__)

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


def resolve_typehint(hint: str, context_module: str | object) -> type:
    # get_type_hints can have some weird effects I don't want to encounter again,
    # like two different versions of the same class, so we use a much simpler way
    if isinstance(context_module, str):
        module = sys.modules[context_module]
    return eval(hint, vars(module))


def to_typed_dict(data: dataclass, resolve_strings: bool) -> dict[str, tuple[type, Any]]:
    def delve(d: Any) -> Any:
        if is_dataclass(d):
            ret = {}
            for f in fields(d):
                val = getattr(d, f.name)
                tp = f.type
                if resolve_strings and isinstance(tp, str):
                    tp = resolve_typehint(f.type, d.__module__)

                ret[f.name] = (tp, delve(val))
            return ret

        elif isinstance(d, dict):
            return {k: delve(v) for k, v in d.items()}

        elif isinstance(d, list):
            return [delve(x) for x in d]

        return d

    return delve(data)


def parse_state_path(state_path: list[str]) -> list[int]:
    """Convert a string state path to a list of integer hashes.

    ``"*"`` maps to 0 (wildcard), ``"#N"`` is parsed as a raw integer,
    and any other string is hashed via ``calc_hash``.
    """
    keys = []
    for val in state_path:
        if isinstance(val, int):
            keys.append(val)
        elif val == "*":
            keys.append(0)
        elif val.startswith("#"):
            try:
                keys.append(int(val[1:]))
            except ValueError:
                raise ValueError(f"{val}: value is not a valid hash")
        else:
            keys.append(calc_hash(val))

    return keys
