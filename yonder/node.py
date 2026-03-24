from typing import Any, Iterator, Generator, TypeAlias
import json
import copy
from collections import deque

from yonder.hash import calc_hash, lookup_name
from yonder.util import resource_data, deepmerge


_undefined = object()
NodeLike: TypeAlias = "Node | int | str"


class Node:
    _templates: dict[str, dict] = {}

    @classmethod
    def load_template(cls, name: str) -> dict:
        if name.endswith(".json"):
            name = name[:-5]

        if name not in cls._templates:
            template_txt = resource_data("templates/" + name + ".json")
            cls._templates[name] = json.loads(template_txt)

        return copy.deepcopy(cls._templates[name])

    @classmethod
    def wrap(cls, node_dict: dict, *args, **kwargs):
        # Make sure the subclasses have been loaded
        import yonder.node_types

        def all_subclasses(c: type) -> dict[str, type]:
            result = {}
            for subclass in c.__subclasses__():
                result[subclass.__name__] = subclass
                result.update(all_subclasses(subclass))
            return result

        node_type = next(iter(node_dict["body"].keys()))
        node_cls = all_subclasses(cls).get(node_type, cls)
        return node_cls(node_dict, *args, **kwargs)

    def __init__(self, node_dict: dict):
        self._attr = node_dict
        self._type = next(iter(self._attr["body"].keys()))

    def cast(self) -> "Node":
        return Node.wrap(self._attr)

    def json(self) -> str:
        return json.dumps(self._attr, indent=2)

    def update(self, data: dict, delete_missing: bool = False) -> None:
        # Merge with our attr so that references stay valid and the soundbank's
        # HIRC this node belongs to is updated, too
        deepmerge(self._attr, data, delete_missing=delete_missing)

    @property
    def dict(self) -> dict:
        return self._attr

    @property
    def type(self) -> str:
        """Type of a HIRC node (e.g. RandomSequenceContainer)."""
        return self._type

    @property
    def id(self) -> int:
        """ID of a HIRC node (i.e. its hash)."""
        idsec = self._attr["id"]
        h = idsec.get("Hash")
        if not h:
            h = calc_hash(idsec["String"])

        return h

    @id.setter
    def id(self, id: int) -> None:
        idsec = self._attr["id"]
        # Only one or the other can be set, not both!
        idsec["Hash"] = int(id)
        idsec.pop("String", None)

    @property
    def name(self) -> str:
        idsec = self._attr["id"]
        n = idsec.get("String")
        if not n:
            n = self.lookup_name()
            if n:
                # If the name lookup succeeded use
                self.name = n

        return n

    @name.setter
    def name(self, name: str) -> None:
        idsec: dict = self._attr["id"]
        # Only one or the other can be set, not both!
        idsec.pop("Hash", None)
        idsec["String"] = name

    def lookup_name(self, default: str = None) -> str:
        name = self._attr["id"].get("String")
        if not name:
            name = lookup_name(self.id)

        if name is None:
            return default

        return name

    @property
    def parent(self) -> int:
        return None

    @parent.setter
    def parent(self, parent: "Node | int") -> None:
        raise ValueError(f"{self} is not a parentable node")

    @property
    def body(self) -> dict:
        """Return the body of a node where the relevant attributes are stored."""
        return self._attr["body"][self.type]

    def copy(self, new_id: int = None, parent: int = None) -> "Node":
        attr = copy.deepcopy(self._attr)
        n = Node.wrap(attr)

        if new_id is not None:
            n.id = new_id
        if parent is not None:
            n.parent = parent

        return n

    def paths(self) -> Iterator[str]:
        def delve(item: dict, path: str):
            if path:
                yield path

            # if isinstance(item, list):
            #     for idx, value in enumerate(item):
            #         delve(value, path + f":{idx}")

            if isinstance(item, dict):
                for key, value in item.items():
                    delve(value, path + "/" + key)

        yield from delve(self.body, "")

    def get(self, path: str, default: Any = _undefined) -> Any:
        try:
            return self[path]
        except KeyError as e:
            if default != _undefined:
                return default

            raise e

    def set(self, path: str, value: Any, create: bool = False) -> bool:
        try:
            self[path] = value
            return True
        except KeyError:
            if create:
                obj: dict = self.body
                parts = path.strip("/").split("/")
                for p in parts[:-1]:
                    obj = obj.setdefault(p, {})
                    if not isinstance(obj, dict):
                        raise ValueError(
                            f"Tried to set new path, but {p} already exists"
                        )

                obj[-1] = value
                return True

            return False

    def resolve_path(
        self, path: str, default: Any = _undefined
    ) -> list[tuple[str, Any]]:
        if not path:
            raise ValueError("Empty path")

        parts = path.strip("/").split("/")

        def bfs_search(
            data: dict, target_key: str
        ) -> Generator[tuple[list[str], dict], None, None]:
            queue = deque([(data, [])])

            while queue:
                current, current_path = queue.popleft()

                if isinstance(current, dict):
                    if target_key in current:
                        yield current_path, current

                    for key, value in current.items():
                        queue.append((value, current_path + [key]))

                elif isinstance(current, list):
                    for i, item in enumerate(current):
                        queue.append((item, current_path + [str(i)]))

        def flatten(results: list) -> list[tuple[str, Any]]:
            flat = []
            for r in results:
                if isinstance(r, list):
                    flat.extend(r)
                elif r:
                    flat.append(r)
            return flat

        def delve(
            obj: Any, key_index: int, resolved: list[str]
        ) -> tuple[str, Any] | list[tuple[str, Any]]:
            if key_index >= len(parts):
                return ("/".join(resolved), obj)

            key = parts[key_index]

            if key == "*":
                if not isinstance(obj, dict):
                    raise KeyError(
                        f"{path} resulted in '*' being applied on non-dict item"
                    )

                results = [
                    delve(sub, key_index + 1, resolved + [k])
                    for k, sub in obj.items()
                    if sub
                ]

                # Combine lists from different branches and filter out empty ones
                return flatten(results)

            elif key == "**":
                if key_index >= len(parts):
                    raise KeyError(f"'**' can not appear at the end ({path})")

                if not isinstance(obj, dict):
                    raise KeyError(
                        f"{path} resulted in '**' being applied on non-dict item"
                    )

                next_key = parts[key_index + 1]
                results = [
                    delve(sub, key_index + 1, resolved + bfs_path)
                    for bfs_path, sub in bfs_search(obj, next_key)
                    if sub
                ]

                # Combine lists from different branches and filter out empty ones
                return flatten(results)

            elif ":" in key:
                key, idx = key.split(":")
                obj = obj[key]

                if not isinstance(obj, list):
                    raise KeyError(
                        f"{path} resulted in array access on a non-list item"
                    )

                if idx == "*":
                    return [
                        delve(item, key_index + 1, resolved + [f"{key}:{i}"])
                        for i, item in enumerate(obj)
                    ]
                else:
                    idx = int(idx)
                    return delve(obj[idx], key_index + 1, resolved + [f"{key}:{idx}"])

            else:
                return delve(obj[key], key_index + 1, resolved + [key])

        try:
            res = delve(self.body, 0, [])
            if isinstance(res, tuple):
                res = [res]
            return res
        except (KeyError, TypeError) as e:
            if default != _undefined:
                return default

            raise e

    def get_references(self) -> list[tuple[str, int]]:
        return []

    def __eq__(self, value: "Node") -> bool:
        if not isinstance(value, Node):
            return False
        return self.id == value.id

    def __lt__(self, other: "Node") -> bool:
        return self.id < other.id

    def __contains__(self, item: Any) -> bool:
        if not isinstance(item, str):
            return False

        return self.get(item, None) is not None

    def __getitem__(self, path: str) -> Any | list[Any]:
        if not path:
            raise ValueError("Empty path")

        # TODO not required anymore when using PathDict
        parts = path.strip("/").split("/")
        value = self.body

        for key in parts:
            value = value[key]

        return value

    def __setitem__(self, path: str, val: Any) -> None:
        try:
            # TODO not required anymore when using PathDict
            parts = path.strip("/").split("/")
            attr = self.body

            for sub in parts[:-1]:
                attr = attr[sub]

            attr[parts[-1]] = val
        except KeyError as e:
            raise KeyError(f"Path '{path}' not found in node {self}") from e

    def __hash__(self):
        return self.id

    def __str__(self):
        return f"{self.type} ({self.id})"
