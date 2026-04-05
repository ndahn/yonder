from typing import Any, Generator, Iterator
from pathlib import Path
from random import randrange
from collections import deque
import json
import shutil
import networkx as nx

from yonder.hash import calc_hash
from yonder.util import logger, resource_data
from yonder.query import query_nodes

from .structure import Section, BKHDSection, HIRCSection, HIRCNode
from .rewwise_parse import serialize, deserialize
from yonder.enums import SourceType
from .action import ActionType

from . import (
    Action,
    Event,
    LayerContainer,
    MusicRandomSequenceContainer,
    MusicSwitchContainer,
    MusicSegment,
    MusicTrack,
    RandomSequenceContainer,
    Sound,
    SwitchContainer,
)


class Soundbank:
    @classmethod
    def create_empty_soundbank(
        cls, bnk_dir: Path | str, name: str, save: bool = True
    ) -> "Soundbank":
        if not bnk_dir.is_dir():
            raise ValueError(f"{bnk_dir} is not a directory")

        bnk_data = json.loads(resource_data("empty_soundbank.json"))
        bnk = cls.from_dict(bnk_dir / "soundbank.json", bnk_data)
        bnk.bkhd.bank_id = calc_hash(name)

        if save:
            bnk.save(backup=False)

        return bnk

    def __init__(self, json_path: Path, sections: list[Section]):
        self.json_path = json_path
        self.sections = {sec.section_name(): sec for sec in sections}

        # A helper dict for mapping object IDs to HIRC indices
        self._id2index: dict[int, int] = {}
        self._regenerate_index_table()

    def _regenerate_index_table(self):
        table = self._id2index
        table.clear()

        for idx, obj in enumerate(self.hirc.objects):
            table[obj.id] = idx
            if obj.name:
                table[obj.name] = idx

    @classmethod
    def from_file(cls, bnk_path: Path | str) -> "Soundbank":
        bnk_path: Path = Path(bnk_path).absolute()
        if bnk_path.is_dir():
            json_path = bnk_path / "soundbank.json"
        else:
            json_path = bnk_path

        with json_path.open() as f:
            bnk_data = json.load(f)

        return cls.from_dict(json_path, bnk_data)

    @classmethod
    def from_dict(cls, json_path: Path, data: dict) -> list[Section]:
        sections = [deserialize(Section, sec) for sec in data["sections"]]
        return Soundbank(json_path, sections)

    def to_dict(self) -> dict:
        return {"sections": serialize(list(self.sections.values()))}

    @property
    def bkhd(self) -> BKHDSection:
        return self.sections["BKHD"]

    @property
    def hirc(self) -> HIRCSection:
        return self.sections["HIRC"]

    @property
    def bank_id(self) -> int:
        return self.bkhd.bank_id

    @bank_id.setter
    def bank_id(self, new_id: int) -> None:
        self.bkhd.bank_id = new_id

    @property
    def name(self) -> str:
        return self.bkhd.name

    @name.setter
    def name(self, new_name: str) -> None:
        self.bkhd.name = new_name

    def get_name(self, default: str = None) -> str:
        name = self.bkhd.name
        if name:
            return name
        return default

    @property
    def bnk_dir(self) -> Path:
        return self.json_path.parent

    def wems(self) -> list[int]:
        wems = []
        # TODO not covering music tracks
        for sound in self.query("type=Sound"):
            wid = sound["bank_source_data/media_information/source_id"]
            wems.append(wid)

        return wems

    def add_wem(self, wem: Path, source_type: SourceType) -> Path:
        if source_type == "Embedded":
            target = self.bnk_dir / f"{wem.stem}.wem"
            if wem.is_file() and target.is_file() and wem.samefile(target):
                return target

            if target.is_file():
                target.unlink()

            shutil.copy(wem, target)
            return target

        elif source_type == "Streaming":
            streaming_dir = self.bnk_dir.parent / "wem" / wem.stem[:2]
            streaming_dir.mkdir(parents=True, exist_ok=True)

            target = streaming_dir / f"{wem.stem}.wem"
            if wem.is_file() and target.is_file() and wem.samefile(target):
                return target

            if target.is_file():
                target.unlink()

            shutil.copy(wem, streaming_dir)
            return target

        elif source_type == "PrefetchStreaming":
            # TODO create snippet
            # Sounds in cs_smain are all <= 20kB
            if wem.stat().st_size > 20000:
                raise ValueError("Wem is too large for a prefetch snippet")

            target = self.bnk_dir / f"{wem.stem}.wem"
            if wem.is_file() and target.is_file() and wem.samefile(target):
                return target

            if target.is_file():
                target.unlink()

            shutil.copy(wem, self.bnk_dir)
            return target

        else:
            raise ValueError(f"Unknown source type {source_type}")

    def remove_unused_wems(self) -> None:
        used = set(self.wems())
        removed = []
        for file in self.bnk_dir.glob("*.wem"):
            wem = int(file.stem)
            if wem not in used:
                removed.append(wem)
                file.unlink()

        logger.info(f"Removed {len(removed)} unused wems")

    def save(self, path: Path | str = None, backup: bool = True) -> None:
        logger.info(f"Saving {self}")

        # Solve the dependency graph
        self.solve()
        self.verify()

        if path:
            path = Path(path).absolute()
            if path.is_dir():
                path = path / "soundbank.json"
        else:
            path = self.json_path

        if backup and path.is_file():
            shutil.copy(path, str(path) + ".bak")
        else:
            backup = False

        with path.open("w") as f:
            json.dump(self.to_dict(), f, indent=2)

        if backup:
            logger.info(f"Saved {self} to {path}, a backup was created")
        else:
            logger.info(f"Saved {self} to {path}")

    def new_id(self) -> int:
        while True:
            # IDs should be signed 32bit integers, although in practice
            # I've rarely seen any below 1000000 (expected I guess?)
            id = randrange(2**24, 2**31 - 1)
            if id not in self._id2index:
                return id

    def add_nodes(self, *nodes: HIRCNode) -> None:
        for n in nodes:
            if n.id <= 0:
                raise ValueError(f"Node {n} has invalid ID {n.id}")
            if n.id in self._id2index:
                raise ValueError(f"Soundbank already contains a node with ID {n.id}")

            self.hirc.objects.append(n)

        self._regenerate_index_table()

    def delete_nodes(self, *nodes: int | HIRCNode) -> None:
        abandoned = []
        for n in nodes:
            if not isinstance(n, HIRCNode):
                n = self[n]
            abandoned.append(n.id)

        for nid in abandoned:
            # Don't use `del self[nid]` as it will regenerate the index table on every delete
            idx = self._id2index[nid]
            del self.hirc.objects[idx]

        # Search for any nodes referencing the deleted nodes and clear those references
        for node in self.hirc.objects:
            for path, ref in node.get_references(node):
                if ref not in abandoned:
                    continue

                # Remove reference from an array
                parts = path.rsplit("/", maxsplit=1)
                if ":" in parts[-1]:
                    parent_value: list[int] = node[parts[0]]
                    # Luckily the X_count fields don't matter to rewwise,
                    # otherwise we'd have to update them here, too
                    parent_value.remove(ref)
                else:
                    # Unset reference field
                    node[path] = 0

        self._regenerate_index_table()

    def get_full_tree(self, valid_only: bool = True) -> nx.DiGraph:
        g = nx.DiGraph()

        for node in self.hirc.objects:
            g.add_node(node.id, type=node.type_name)
            references = node.get_references()
            for _, ref in references:
                if not valid_only or ref in self:
                    g.add_edge(node.id, ref)

        return g

    def get_subtree(
        self,
        entrypoint: int | HIRCNode,
        children_only: bool = True,
        include_external: bool = True,
    ) -> nx.DiGraph:
        if isinstance(entrypoint, int):
            entrypoint = self[entrypoint]

        g = nx.DiGraph()
        todo = deque([(entrypoint.id, None)])

        # Depth first search to recover all nodes part of the wwise hierarchy
        while todo:
            node_id, parent_id = todo.pop()

            if node_id in g:
                continue

            idx = self._id2index.get(node_id)
            if idx is None:
                if include_external:
                    g.add_node(node_id, type="(external)")
                    g.add_edge(parent_id, node_id)
                continue

            node = self.hirc.objects[idx]
            g.add_node(node_id, type=node.type_name)

            if parent_id is not None:
                g.add_edge(parent_id, node_id)

            if children_only:
                if isinstance(node, (Action, Event)):
                    todo.extend((ref, node_id) for _, ref in node.get_references())
                elif hasattr(node, "children"):
                    todo.extend((cid, node_id) for cid in node.children)
            else:
                todo.extend((ref, node_id) for _, ref in node.get_references())

        return g

    def get_parent_chain(self, entrypoint: HIRCNode) -> list[int]:
        """Go up in the HIRC from the specified entrypoint and collect all node IDs along the way until we reach the top."""
        if not hasattr(entrypoint, "parent"):
            raise ValueError("Must start from a parentable object")

        parent_id = entrypoint.parent
        upchain = []

        # Parents are sometimes located in other soundbanks, too
        while parent_id in self._id2index:
            # No early exit, we want to recover the entire upwards chain. We'll handle the
            # parts we actually need later

            # Check for loops. No clue if that ever happens, but better be safe than sorry
            if parent_id in upchain:
                # Print the loop
                logger.error(f"Reference loop detected: {upchain}")
                for pid in upchain:
                    debug_obj: HIRCNode = self[pid]
                    debug_parent = debug_obj.parent
                    print(f"{pid} -> {debug_parent}")

                print(f"{debug_parent} -> {parent_id}")

                raise ValueError(
                    f"Parent chain for node {entrypoint} contains a loop at node {parent_id}"
                )

            upchain.append(parent_id)
            parent_id = self[parent_id].parent

        return upchain

    def query(self, query: str) -> Generator[HIRCNode, None, None]:
        yield from query_nodes(self.hirc.objects, query)

    def query_one(self, query: str, default: Any = None) -> HIRCNode:
        return next(self.query(query), default)

    def find_orphans(self) -> list[HIRCNode]:
        g = self.get_full_tree()

        search_types = {
            c.__name__
            for c in (
                LayerContainer,
                MusicRandomSequenceContainer,
                MusicSwitchContainer,
                MusicSegment,
                MusicTrack,
                RandomSequenceContainer,
                Sound,
                SwitchContainer,
            )
        }

        return [
            self[nid]
            for nid, tp in g.nodes.data("type")
            if tp in search_types and g.in_degree(nid) == 0
        ]

    def delete_orphans(self, cascade: bool = True) -> None:
        g = self.get_full_tree()
        indices = set()

        search_types = {
            c.__name__
            for c in (
                LayerContainer,
                MusicRandomSequenceContainer,
                MusicSwitchContainer,
                MusicSegment,
                MusicTrack,
                RandomSequenceContainer,
                Sound,
                SwitchContainer,
            )
        }

        while True:
            # Collect non-event nodes with no references to them
            orphans = [
                nid
                for nid, tp in g.nodes.data("type")
                if tp in search_types and g.in_degree(nid) == 0
            ]
            if not orphans:
                break

            indices.update(self._id2index[n] for n in orphans)
            g.remove_nodes_from(orphans)

            # Check if new orphans appeared in the graph from the removal of the
            # discovered orphans
            if not cascade:
                break

        # Clear the hirc
        orphan_nodes = [str(self.hirc.objects[i]) for i in indices]
        logger.info(
            f"The following {len(indices)} nodes have been orphaned (cascade={cascade}):\n{'  \n'.join(orphan_nodes)}"
        )
        self.hirc.objects = [
            x for i, x in enumerate(self.hirc.objects) if i not in indices
        ]
        self._regenerate_index_table()

        logger.info(f"Found and deleted {len(indices)} orphans")

    def find_events(
        self, action_type: ActionType = ActionType.Play
    ) -> Generator[HIRCNode, None, None]:
        events: list[Event] = list(self.query("type=Event"))
        for evt in events:
            for aid in evt.actions:
                action: Action = self[aid]
                if not action_type or action_type == action.action_type_enum:
                    yield evt
                    break

    def find_event_subgraphs_for(
        self, node: int | HIRCNode
    ) -> Generator[tuple[HIRCNode, nx.DiGraph], None, None]:
        if isinstance(node, HIRCNode):
            node = node.id

        # TODO cache nodes by type
        # TODO cache full graph
        events: list[Event] = list(self.query("type=Event"))

        g = self.get_full_tree()
        for evt in events:
            desc = nx.descendants(g, evt.id)
            if node in desc:
                yield evt, g.subgraph({evt.id} | desc)

    def solve(self) -> None:
        g = self.get_full_tree()
        objects = []

        if not nx.is_directed_acyclic_graph(g):
            logger.warning("HIRC is not acyclic")

        # These will be appended at the very end
        events: list[Event] = []
        actions: list[Action] = []

        # Reverse g so we get the children before their parents. This means that any objects
        # with no references to other nodes (like Attenuations) will come at the very beginning.
        # Since references must appear before the nodes referencing them this is exactly what
        # we need.
        for generation in nx.topological_generations(g.reverse()):
            nodes: list[HIRCNode] = []

            for nid in generation:
                node = self[nid]
                if isinstance(node, Event):
                    events.append(node)
                elif isinstance(node, Action):
                    actions.append(node)
                else:
                    nodes.append(node)

            # Sort by type first, then ID
            nodes.sort(key=lambda n: f"{n.type_name} {n.id:010d}")
            objects.extend(n for n in nodes)

        # Actions are usually placed immediately before their events, but this way
        # is both easier and more reliable
        events.sort(key=lambda n: n.id)
        objects.extend(events)

        actions.sort(key=lambda n: n.id)
        objects.extend(actions)

        self.hirc.objects = objects
        logger.info(f"Solved structure for {len(g)} nodes ({len(events)} events)")
        self._regenerate_index_table()

    def verify(self) -> int:
        severity = 0
        discovered_ids = set([0])

        logger.info(f"Verifying {self}...")

        for node in self.hirc.objects:
            node_id = node.id

            if node_id <= 0:
                logger.error(f"{node}: invalid node ID {node_id}")
            elif node_id in discovered_ids:
                logger.error(f"{node}: ID {node_id} has been defined before")
                severity = max(severity, 2)
                continue

            discovered_ids.add(node_id)

            if hasattr(node, "parent"):
                parent_id = node.parent
                parent = self.get(parent_id)

                if parent_id <= 0:
                    logger.warning(f"{node}: node has no parent")
                    severity = max(severity, 1)
                elif parent_id in discovered_ids:
                    logger.error(f"{node}: defined after its parent {parent_id}")
                    severity = max(severity, 2)

                if parent_id > 0 and not parent:
                    logger.error(f"{node}: parent {parent_id} does not exist")
                    severity = max(severity, 2)

                if parent and hasattr(parent, "children"):
                    if node_id not in parent.children:
                        logger.error(
                            f"{node}: parent {parent_id} does not include node in its children"
                        )
                        severity = max(severity, 2)

            for _, ref in node.get_references():
                if ref in self and ref not in discovered_ids:
                    logger.error(f"{node}: defined before referenced node {ref}")
                    severity = max(severity, 2)

            if hasattr(node, "children"):
                prev_child_id = -1
                wrong_order = False

                for child_id in node.children:
                    if not wrong_order and child_id < prev_child_id:
                        logger.error(f"{node}: children are not sorted")
                        severity = max(severity, 2)
                        # log only once
                        wrong_order = True

                    prev_child_id = child_id

                    # Non-existing children are actually pretty okay here
                    # if child_id not in self:
                    #     logger.warning(f"{node}: child {child_id} does not exist")
                    #     severity = max(severity, 1)

                    # Any node that can be added to children will also have a parent attribute
                    if child_id in self:
                        child = self[child_id]
                        if child.parent is not None and child.parent != node.id:
                            logger.error(
                                f"{node}: child {child_id} has different parent {child.parent}"
                            )
                            severity = max(severity, 2)

        if severity == 0:
            logger.info("Seems surprisingly fine - yay!")
        elif severity == 1:
            logger.warning("Found some potential issues, but probably okay")
        else:
            logger.error("Severe issues found, soundbank will most likely be broken")

        return severity

    def get(self, nid: int | str, default: Any = None) -> HIRCNode:
        try:
            return self[nid]
        except (KeyError, IndexError):
            return default

    def __iter__(self) -> Iterator[HIRCNode]:
        yield from self.hirc.objects

    def __contains__(self, key: Any) -> HIRCNode:
        if isinstance(key, HIRCNode):
            key = key.id
        elif isinstance(key, str):
            key = calc_hash(key)

        return key in self._id2index

    def __getitem__(self, key: int | str) -> HIRCNode:
        if isinstance(key, str):
            if key.startswith("#"):
                key = int(key[1:])
            else:
                key = calc_hash(key)

        idx = self._id2index[key]
        return self.hirc.objects[idx]

    def __delitem__(self, key: int | str | HIRCNode) -> None:
        if isinstance(key, HIRCNode):
            key = key.id
        elif isinstance(key, str):
            if key.startswith("#"):
                key = int(key[1:])
            else:
                key = calc_hash(key)

        idx = self._id2index.pop(key)
        del self.hirc.objects[idx]

        self._regenerate_index_table()

    def __str__(self):
        return f"Soundbank {self.bank_id} ({self.name})"
