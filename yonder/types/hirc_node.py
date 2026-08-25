from __future__ import annotations
from typing import Any, ClassVar, TYPE_CHECKING
from dataclasses import InitVar, dataclass, field, fields, is_dataclass
import pyo

from .mixins import DataNode
from .serialization import _serialize_value, _deserialize_fields
from .object_id import ObjectId

if TYPE_CHECKING:
    from yonder.audio import PlayContext


@dataclass(slots=True)
class HIRCNodeHeader:
    # These two are just here to make rewwise happy
    body_type: int = 0
    size: int = 0
    id: ObjectId = None

    def to_dict(self) -> dict:
        ser = _serialize_value(self)
        ser.pop("_id", None)
        ser["id"] = self.id.to_dict()
        return ser

    @classmethod
    def from_dict(cls, data: dict) -> HIRCNode:
        return _deserialize_fields(cls, data)


@dataclass(repr=False, eq=False)
class HIRCNode(DataNode):
    # Expected to be set on class definition
    body_type: ClassVar[int] = 0
    id: InitVar[int]
    _header: HIRCNodeHeader = field(init=False)

    def __post_init__(self, id: int):
        if isinstance(id, dict):
            oid = ObjectId.from_dict(id)
        else:
            oid = ObjectId(id)

        self._header = HIRCNodeHeader(self.body_type, 0, oid)

    @property
    def id(self) -> int:
        return self._header.id.hash

    @id.setter
    def id(self, new_id: int) -> None:
        self._header.id.hash = new_id

    @property
    def name(self) -> str:
        return self._header.id.name

    @name.setter
    def name(self, new_name: str) -> None:
        self._header.id.name = new_name

    @property
    def type_name(self) -> str:
        return type(self).__name__

    @property
    def type_name_short(self) -> str:
        return "".join(s for s in self.type_name if s.isupper())

    def get_name(self, default: str = None) -> str:
        if default is None:
            default = f"#{self.id}"

        return self._header.id.get_name(default)

    def to_dict(self) -> dict:
        # rewwise inserts the class name of the node type into the hierarchy
        # (e.g. body: {Sound: ...})
        data = _serialize_value(self)
        trans = {
            **data.pop("_header"),
            "body": {
                self.type_name: {**data},
            },
        }
        return trans

    @classmethod
    def from_dict(cls, data: dict) -> HIRCNode:
        node_type = next(iter(data["body"].keys()))
        header = {
            "body_type": data.pop("body_type"),
            "size": data.pop("size"),
            "id": data.pop("id"),
        }

        # It's much more convenient to store all the header data in a nested dataclass
        # and keep the actual node params at root level, so we have to massage the data
        # rewwise spits out a little bit
        trans = {
            "id": next(iter(header["id"].values())),
            "_header": header,
            **data["body"][node_type],
        }

        if cls.__name__ == node_type:
            return _deserialize_fields(cls, trans)

        for sub in cls.__subclasses__():
            if sub.__name__ == node_type:
                return _deserialize_fields(sub, trans)

        from .unknown import UnknownObject

        return UnknownObject.from_dict(trans, node_type)

    def get_references(self) -> list[tuple[str, int]]:
        def delve(obj: Any, path: str = "") -> list[tuple[str, int]]:
            ret = []

            # Use get_references() only on objects other than self
            if (
                obj is not self
                and hasattr(obj, "get_references")
                and callable(obj.get_references)
            ):
                for key, val in obj.get_references():
                    if isinstance(val, int) and val > 0:
                        ret.append((f"{path}/{key}", val))

                # Only this function is recursive, others can be shallow,
                # so we shouldn't return just yet

            if is_dataclass(obj):
                for f in fields(obj):
                    ret.extend(delve(getattr(obj, f.name), f"{path}/{f.name}"))
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    ret.extend(delve(item, f"{path}:{i}"))
            elif isinstance(obj, dict):
                for key, val in obj.items():
                    ret.extend(delve(val, f"{path}/{key}"))

            return ret

        return delve(self)

    def pyo(self, ctx: PlayContext) -> tuple[PlayContext, pyo.PyoObject]:
        ctx = ctx.merge(self)

        my_pyo = getattr(self, "_pyo", None)
        if my_pyo is None:
            my_pyo = self._build_pyo(ctx)
            self._pyo = my_pyo

        return (ctx, my_pyo)

    def is_pyo_initialized(self) -> bool:
        return hasattr(self, "_pyo")

    def reset_pyo(self, ctx: PlayContext) -> None:
        # Don't merge, just forward
        self.stop(ctx)

        if hasattr(self, "_pyo"):
            delattr(self, "_pyo")

        # Don't call pyo here to avoid reinitializing the audio backend
        ctx = ctx.merge(self)
        for _, ref in self.get_references():
            node = ctx.bank.get(ref)
            if node:
                node.reset_pyo(ctx)

    def _build_pyo(ctx: PlayContext) -> pyo.PyoObject:
        """Return a pyo object for this node. Must always return a valid, playable object - return `pyo.Sig(0)` if the node doesn't have anything to play.

        This should be implemented by deriving classes.

        Parameters
        ----------
        ctx : PlayContext
            The current playback context.

        Returns
        -------
        pyo.PyoObject
            Whatever signal this node wants to add into playback. In most cases this will be one of the children's pyo object, possibly with some filters applied.
        """
        return pyo.Sig(0)

    def play(self, ctx: PlayContext) -> None:
        """Initialize this node's audio backend and start playback. 

        This should be implemented by deriving classes. The first call in the implementation should always go to `self.pyo` to initialize the backend and retrieve the updated context and pyo objects. The last call should go to `play` on the object's pyo object.

        Parameters
        ----------
        ctx : PlayContext
            The current playback context.
        """
        pass

    def stop(self, ctx: PlayContext) -> None:
        if self.is_pyo_initialized():
            ctx, my_pyo = self.pyo(ctx)
            my_pyo.stop()
        else:
            ctx = ctx.merge(self)

        for _, ref in self.get_references():
            node = ctx.bank.get(ref)
            if node and node.is_pyo_initialized():
                node.stop(ctx)

    def update_playback(self, ctx: PlayContext) -> None:
        """Called when the context changed (properties, rtpcs, states, etc). 
        
        Deriving classes may override this to react to state changes, but should still call `super` to cascade down.

        Parameters
        ----------
        ctx : PlayContext
            The updated playback context.
        """
        # Merge manually to avoid initializing pyo if we don't actually need it
        ctx = ctx.merge(self)

        for _, ref in self.get_references():
            node = ctx.bank.get(ref)
            if node and node.is_pyo_initialized():
                node.update_playback(ctx)

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HIRCNode):
            return NotImplemented
        return self.id == other.id

    def __lt__(self, other: HIRCNode) -> bool:
        return self.id < other.id

    def __str__(self) -> str:
        type_name = self.type_name_short
        name = self.get_name("")
        if name:
            return f"[{type_name}] {name} #{self.id}"
        return f"[{type_name}] #{self.id}"

    def __repr__(self) -> str:
        name = self.get_name("<?>")
        return f"[{self.type_name}] {name} #{self.id}"


NODE_TYPE_MAP = {cls.body_type: cls for cls in HIRCNode.__subclasses__()}
