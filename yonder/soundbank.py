from typing import Any, Generator, Iterator
from pathlib import Path
from random import randrange
from collections import deque
import json
import copy
import shutil
import networkx as nx

from yonder.hash import calc_hash
from yonder.util import logger, resource_data
from yonder.enums import SourceType
from yonder.node import Node
from yonder.query import query_nodes


class Soundbank:
    @classmethod
    def load(cls, bnk_path: Path | str) -> "Soundbank":
        """Load a soundbank and return a more manageable representation."""
        # Resolve the path to the unpacked soundbank
        bnk_path: Path = Path(bnk_path).resolve()
        if bnk_path.name == "soundbank.json":
            json_path = bnk_path
            bnk_path = bnk_path.parent
        else:
            if bnk_path.name.endswith(".bnk"):
                bnk_path = bnk_path.parent / bnk_path.stem
            json_path = bnk_path / "soundbank.json"

        with json_path.open() as f:
            bnk_json: dict = json.load(f)

        # Read the sections
        sections = bnk_json.get("sections", None)

        if not sections:
            raise ValueError("Could not find 'sections' in bnk")

        for sec in sections:
            body = sec["body"]

            if "BKHD" in body:
                bnk_id = body["BKHD"]["bank_id"]
            elif "HIRC" in body:
                hirc: list[Node] = [Node.wrap(obj) for obj in body["HIRC"]["objects"]]
                cleaned = {n.id: n for n in hirc}
                if len(cleaned) < len(hirc):
                    logger.warning(
                        f"Removed {len(hirc) - len(cleaned)} duplicate nodes from soundbank"
                    )
                    hirc = list(cleaned.values())
            else:
                pass

        return cls(bnk_path, bnk_json, bnk_id, hirc)

    @classmethod
    def create_empty_soundbank(path: Path | str, name: str) -> "Soundbank":
        if not path.is_dir():
            raise ValueError(f"{path} is not a directory")

        bnk = json.loads(resource_data("empty_soundbank.json"))
        name_hash = calc_hash(name)
        bnk["sections"][0]["body"]["BKHD"]["bank_id"] = name_hash

        bnk_path = Path(path) / name / "soundbank.json"
        json.dump(bnk, bnk_path.open("w"))

        return Soundbank.load(bnk_path)

    def __init__(
        self,
        bnk_dir: Path,
        json: dict,
        id: int,
        hirc: list[Node],
    ):
        self.bnk_dir = bnk_dir
        self.id = id
        self._json = json
        self._hirc = hirc

        # A helper dict for mapping object IDs to HIRC indices
        self._id2index: dict[int, int] = {}
        self._regenerate_index_table()

    def _regenerate_index_table(self):
        self._id2index.clear()

        for idx, node in enumerate(self._hirc):
            idsec = node.dict["id"]
            if "Hash" in idsec:
                oid = idsec["Hash"]
                self._id2index[oid] = idx
            elif "String" in idsec:
                eid = idsec["String"]
                self._id2index[eid] = idx
                # Events are sometimes referred to by their hash, but it's not included in the json
                oid = calc_hash(eid)
                self._id2index[oid] = idx
            else:
                logger.error(f"Don't know how to handle object with id {idsec}")

    @property
    def name(self) -> str:
        return self.bnk_dir.name

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
            if wem.samefile(target):
                return target

            if target.is_file():
                target.unlink()
            
            shutil.copy(wem, target)
            return target

        elif source_type == "Streaming":
            streaming_dir = self.bnk_dir.parent / "wem" / wem.stem[:2]
            streaming_dir.mkdir(parents=True, exist_ok=True)

            target = streaming_dir / f"{wem.stem}.wem"
            if wem.samefile(target):
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
            if wem.samefile(target):
                return target
            
            if target.is_file():
                target.unlink()

            shutil.copy(wem, self.bnk_dir)
            return target

        else:
            raise ValueError(f"Unknown source type {source_type}")

    def _apply_hirc_to_json(self) -> None:
        """Update this soundbank's json with its current HIRC."""
        sections = self._json["sections"]
        for sec in sections:
            if "HIRC" in sec["body"]:
                sec["body"]["HIRC"]["objects"] = [n.dict for n in self._hirc]
                break

    def copy(self, name: str, new_bnk_id: int = None) -> "Soundbank":
        self._apply_hirc_to_json()

        bnk = Soundbank(
            self.bnk_dir.parent / name,
            copy.deepcopy(self._json),
            self.id,
            [n.copy() for n in self._hirc],
        )

        if new_bnk_id is not None:
            bnk.id = new_bnk_id
            for action in bnk.query("type=Action"):
                bid = action.get("params/bank_id", None)
                if bid == self.id:
                    action["params/bank_id"] = new_bnk_id

        return bnk

    def save(self, path: Path | str = None, backup: bool = True) -> None:
        logger.info(f"Saving {self}")

        # Solve the dependency graph
        self.solve()
        self.verify()
        self._apply_hirc_to_json()

        if path:
            path = Path(path).resolve()
        else:
            path = self.bnk_dir

        if path.name != "soundbank.json":
            if not path.is_dir():
                raise ValueError(f"Not a directory: {path}")
            path = path / "soundbank.json"

        if backup and path.is_file():
            shutil.copy(path, str(path) + ".bak")

        with path.open("w") as f:
            json.dump(self._json, f, indent=2)

        logger.info(f"Saved {self} to {path}, a backup was created")

    def new_id(self) -> int:
        while True:
            # IDs should be signed 32bit integers, although in practice
            # I've rarely seen any below 1000000 (expected I guess?)
            id = randrange(2**24, 2**31 - 1)
            if id not in self._id2index:
                return id

    def get_insertion_index(self, nodes: list[Node]) -> tuple[int, int]:
        min_idx = 0
        max_idx = len(self._hirc)

        for node in nodes:
            try:
                parent = node.parent
                max_idx = min(max_idx, self._id2index[parent])
            except KeyError:
                pass

            if "children" in node:
                children: list = node["children/items"]
                # Nodes must appear before any nodes referencing them
                for child in children:
                    min_idx = max(min_idx, self._id2index[child])

        if min_idx > max_idx:
            raise ValueError(f"Invalid index constraints: {min_idx} >= {max_idx}")

        return min_idx

    def get(self, nid: int | str, default: Any = None) -> Node:
        try:
            return self[nid]
        except (KeyError, IndexError):
            return default

    def add_nodes(self, *nodes: Node) -> None:
        for n in nodes:
            if n.id <= 0:
                raise ValueError(f"Node {n} has invalid ID {n.id}")
            if n.id in self._id2index:
                raise ValueError(f"Soundbank already contains a node with ID {n.id}")

            self._hirc.append(n)

        self._regenerate_index_table()

    def delete_nodes(self, *nodes: int | Node) -> None:
        abandoned = []
        for n in nodes:
            if not isinstance(n, Node):
                n = self[n]
            abandoned.append(n.id)

        for nid in abandoned:
            # Don't use `del self[nid]` as it will regenerate the index table on every delete
            idx = self._id2index[nid]
            del self._hirc[idx]

        # Search for any nodes referencing the deleted nodes and clear those references
        for node in self._hirc:
            for path, ref in node.get_references(node):
                if ref not in abandoned:
                    continue

                # Remove reference from an array
                if ":" in path.rsplit("/", maxsplit=1)[-1]:
                    parent_value: list[int] = node[path.rsplit("/", maxsplit=1)[0]]
                    # Luckily the X_count fields don't matter to rewwise,
                    # otherwise we'd have to update them here, too
                    parent_value.remove(ref)
                else:
                    # Unset reference field
                    node[path] = 0

        self._regenerate_index_table()

    def find_orphans(self) -> list[Node]:
        g = self.get_full_tree()
        
        forbidden_types = {
            "ActorMixer",
            "Attenuation",
            "Bus",
            "EffectCustom",
            "Event",
        }

        return [
            self[nid]
            for nid, tp in g.nodes.data("type")
            if tp not in forbidden_types and g.in_degree(nid) == 0
        ]

    def delete_orphans(self, cascade: bool = True) -> None:
        g = self.get_full_tree()
        indices = set()

        forbidden_types = {
            "ActorMixer",
            "Attenuation",
            "Bus",
            "EffectCustom",
            "Event",
        }

        while True:
            # Collect non-event nodes with no references to them
            orphans = [
                nid
                for nid, tp in g.nodes.data("type")
                if tp not in forbidden_types and g.in_degree(nid) == 0
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
        orphan_nodes = [str(self._hirc[i]) for i in indices]
        logger.info(
            f"The following {len(indices)} nodes have been orphaned (cascade={cascade}):\n{'  \n'.join(orphan_nodes)}"
        )
        self._hirc = [x for i, x in enumerate(self._hirc) if i not in indices]
        self._regenerate_index_table()

        logger.info(f"Found and deleted {len(indices)} orphans")

    def remove_unused_wems(self) -> None:
        used = set(self.wems())
        removed = []
        for file in self.bnk_dir.glob("*.wem"):
            wem = int(file.stem)
            if wem not in used:
                removed.append(wem)
                file.unlink()

        logger.info(f"Removed {len(removed)} unused wems")

    def get_full_tree(self, valid_only: bool = True) -> nx.DiGraph:
        g = nx.DiGraph()

        for node in self._hirc:
            g.add_node(node.id, type=node.type)
            references = node.get_references()
            for _, ref in references:
                if not valid_only or ref in self:
                    g.add_edge(node.id, ref)

        return g

    def get_subtree(self, entrypoint: int | Node, children_only: bool = True) -> nx.DiGraph:
        """Collects all descendant nodes from the specified entrypoint in a graph."""
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
                g.add_node(node_id, type="(external)")
                g.add_edge(parent_id, node_id)
                continue

            node = self._hirc[idx]
            node_type = node.type
            g.add_node(node_id, type=node_type)

            if parent_id is not None:
                g.add_edge(parent_id, node_id)

            if node_type == "Sound":
                # We found an actual sound
                wem = node["bank_source_data/media_information/source_id"]
                g.nodes[node_id]["wems"] = [wem]
            elif node_type == "MusicTrack":
                wems = [src["media_information"]["source_id"] for src in node["sources"]]
                g.nodes[node_id]["wems"] = wems

            if children_only:
                if node.type in ("Event", "Action"):
                    todo.extend((ref, node_id) for _, ref in node.get_references())
                elif hasattr(node, "children"):
                    todo.extend((cid, node_id) for cid in node.children)
            else:
                todo.extend((ref, node_id) for _, ref in node.get_references())

        return g

    def get_parent_chain(self, entrypoint: Node) -> list[int]:
        """Go up in the HIRC from the specified entrypoint and collect all node IDs along the way until we reach the top."""
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
                    debug_obj: Node = self[pid]
                    debug_parent = debug_obj.parent
                    print(f"{pid} -> {debug_parent}")

                print(f"{debug_parent} -> {parent_id}")

                raise ValueError(
                    f"Parent chain for node {entrypoint} contains a loop at node {parent_id}"
                )

            # Children before parents
            upchain.append(parent_id)
            parent_id = self[parent_id].parent

        return upchain

    def query(self, query: str) -> Generator[Node, None, None]:
        yield from query_nodes(self._hirc, query)

    def query_one(self, query: str, default: Any = None) -> Node:
        return next(self.query(query), default)

    def find_events(self, event_type: str = "Play") -> Generator[Node, None, None]:
        events = list(self.query("type=Event"))
        for evt in events:
            for aid in evt["actions"]:
                action = self[aid]
                if not event_type or event_type == action.type:
                    yield evt
                    break

    def find_event_subgraphs_for(
        self, node: int | Node
    ) -> Generator[tuple[Node, nx.DiGraph], None, None]:
        if isinstance(node, Node):
            node = node.id

        # TODO cache nodes by type
        # TODO cache full graph
        events = list(self.query("type=Event"))

        g = self.get_full_tree()
        for evt in events:
            desc = nx.descendants(g, evt.id)
            if node in desc:
                yield evt, g.subgraph({evt.id} | desc)

    def find_related_objects(self, object_ids: list[int]) -> set[int]:
        """Recursively collect any values of attributes that look like they could be a reference to another object, e.g. a bus."""
        extras = []
        object_ids = set(object_ids)  # for efficiency

        # TODO instead of just taking everything that even remotely looks like an object we really should decide based on node type and attribute name, but.... eh
        def delve(item: Any, field: str, new_ids: set):
            if field in ["source_id", "direct_parent_id", "children"]:
                return

            if isinstance(item, list):
                for i, subnode in enumerate(item):
                    delve(subnode, f"{field}[{i}]", new_ids)

            elif isinstance(item, dict):
                for key, val in item.items():
                    delve(val, key, new_ids)

            elif isinstance(item, int):
                if item in self._id2index and item not in object_ids:
                    new_ids.add(item)

        for oid in object_ids:
            todo = deque([oid])

            while todo:
                node_id = todo.pop()
                node = self._hirc[self._id2index[node_id]]

                new_ids = set()
                delve(node.body, "body", new_ids)

                for id in new_ids.difference(extras):
                    todo.append(id)
                    # Will contain the highest parents in the beginning (to the left) and deeper
                    # children towards the end (right)
                    extras.append(id)

        return extras

    def solve(self) -> None:
        from yonder.node_types import Event

        g = self.get_full_tree()
        new_hirc = []

        if not nx.is_directed_acyclic_graph(g):
            logger.warning("HIRC is not acyclic")

        # These will be appended at the very end
        events: list[Event] = []

        # Reverse g so we get the children before their parents. This means that any objects
        # with no references to other nodes (like Attenuations) will come at the very beginning.
        # Since references must appear before the nodes referencing them this is exactly what
        # we need.
        for generation in nx.topological_generations(g.reverse()):
            nodes: list[Node] = []

            for nid in generation:
                node = self[nid]
                if type(node) is Node:
                    logger.debug(f"Uncast node {node}")

                if node.type == "Event":
                    events.append(node)
                elif node.type == "Action":
                    # Will be placed later
                    pass
                else:
                    nodes.append(node)

            # Sort by type first, then ID
            nodes.sort(key=lambda n: f"{n.type} {n.id:010d}")
            new_hirc.extend(n for n in nodes)

        # Actions are usually placed immediately before their events
        events.sort(key=lambda n: n.id)
        placed_actions = set()

        for evt in events:
            for aid in sorted(evt.actions):
                if aid in placed_actions:
                    continue

                action = self.get(aid)
                if action:
                    new_hirc.append(action)
                    placed_actions.add(aid)

            new_hirc.append(evt)

        self._hirc = new_hirc

        logger.info(f"Solved structure for {len(g)} nodes ({len(events)} events)")
        self._regenerate_index_table()

    def verify(self) -> int:
        from yonder.node_types.mixins import ContainerMixin

        severity = 0
        discovered_ids = set([0])

        logger.info(f"Verifying {self}...")

        for node in self._hirc:
            node = node.cast()
            node_id = node.id

            if node_id <= 0:
                logger.error(f"{node}: invalid node ID {node_id}")
            elif node_id in discovered_ids:
                logger.error(f"{node}: ID {node_id} has been defined before")
                severity = max(severity, 2)
                continue

            discovered_ids.add(node_id)

            parent_id = node.parent
            if parent_id is not None:
                if parent_id <= 0:
                    logger.warning(f"{node}: node has no parent")
                    severity = max(severity, 1)
                elif parent_id in discovered_ids:
                    logger.error(f"{node}: defined after its parent {parent_id}")
                    severity = max(severity, 2)
                elif parent_id in self:
                    parent = self[parent_id]
                    if hasattr(parent, "children"):
                        if node_id not in parent.children:
                            logger.error(
                                f"{node}: parent {parent_id} does not include node in its children"
                            )
                            severity = max(severity, 2)
                else:
                    logger.error(f"{node}: parent {parent_id} does not exist")
                    severity = max(severity, 2)

            for _, ref in node.get_references():
                if ref in self and ref not in discovered_ids:
                    logger.error(f"{node}: defined before referenced node {ref}")
                    severity = max(severity, 2)

            if isinstance(node, ContainerMixin):
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

    def verify_raw(self) -> None:
        # Experimental, treats everything that looks remotely like an ID as a reference,
        # only checks order
        discovered_ids = set([0])
        for node in self._hirc:
            references = set()

            def delve(d: dict) -> None:
                for k, v in d.items():
                    if isinstance(v, dict):
                        delve(v)
                    elif isinstance(v, list):
                        sub = {i: s for i, s in enumerate(v)}
                        delve(sub)
                    elif k in (
                        "Hash",
                        "String",
                        "direct_parent_id",
                        "source_id",
                        "in_memory_media_size",
                        "bank_id",
                    ):
                        continue
                    elif isinstance(v, int) and 10**6 <= v <= 10**10:
                        references.add(v)

            delve(node.body)
            for ref in references:
                if ref in self and ref not in discovered_ids:
                    logger.error(f"{node}: defined before its reference {ref}")

    def __iter__(self) -> Iterator[Node]:
        yield from self._hirc

    def __contains__(self, key: Any) -> Node:
        if isinstance(key, Node):
            key = key.id
        elif isinstance(key, str):
            key = calc_hash(key)

        return key in self._id2index

    def __getitem__(self, key: int | str) -> Node:
        if isinstance(key, str):
            if key.startswith("#"):
                key = int(key[1:])
            else:
                key = calc_hash(key)

        idx = self._id2index[key]
        return self._hirc[idx]

    def __delitem__(self, key: int | str | Node) -> None:
        if isinstance(key, Node):
            key = key.id
        elif isinstance(key, str):
            if key.startswith("#"):
                key = int(key[1:])
            else:
                key = calc_hash(key)

        idx = self._id2index.pop(key)
        del self._hirc[idx]

        self._regenerate_index_table()

    def __str__(self):
        return f"Soundbank (id={self.id}, bnk={self.name})"
