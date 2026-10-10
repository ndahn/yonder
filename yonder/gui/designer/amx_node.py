from typing import ClassVar, Any
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.util import logger
from yonder.gui.designer.graph_designer_node import GraphDesignerNode
from yonder.gui.localization import μ
from yonder.types import HIRCNode, Action, ActorMixer, AuxiliaryBus, Bus, Event
from yonder.gui.widgets import add_select_actormixer


class AMXNode(GraphDesignerNode):
    """A predefined ActorMixer that will mix different audio pieces."""

    node_type: ClassVar[type[HIRCNode]] = ActorMixer
    label: ClassVar[str] = "ActorMixer"
    show_name_field: ClassVar[bool] = False
    inputs: ClassVar[tuple[str, ...]] = ()
    outputs: ClassVar[tuple[str, ...]] = ("Child 0",)

    def __init__(
        self,
        bnk: Soundbank,
        nid: str | int = 0,
    ):
        super().__init__(bnk, nid)
        self._bnk = bnk
        self._amx_selector: add_select_actormixer = None

    def node_id(self) -> int:
        # We stand in for a mixer that already exists, so that is the ID our
        # children have to be parented to. Note that it may well live in
        # another bank, in which case we only have its ID.
        node = self._amx_selector.selected_node
        if not self.is_custom and node:
            return node.id if isinstance(node, HIRCNode) else node

        return super().node_id()

    def build_body(self) -> None:
        self._amx_selector = add_select_actormixer(
            self._bnk,
            textbox_width=self.body_width,
            tag=self._wtag("amx_selector"),
        )
        dpg.add_checkbox(label=µ("Custom"), callback=self._toggle_custom, tag=self._wtag("custom"))

    @property
    def is_custom(self) -> bool:
        return dpg.get_value(self._wtag("custom"))

    def _toggle_custom(self, sender: str, custom: bool, user_data: Any) -> None:
        if custom:
            dpg.hide_item(self._wtag("amx_selector"))
            dpg.show_item(self._wtag("name"))
            self.sync_terminals(["Parent", "Event"], True)
            self.sync_terminals(
                [c for c in self.get_terminals(False) if c.startswith("Child")]
                + ["Bus", "Aux 0"],
                False,
            )
            dpg.move_item_up(self.get_input_terminal("Parent"))
        else:
            dpg.show_item(self._wtag("amx_selector"))
            dpg.hide_item(self._wtag("name"))
            self.sync_terminals([], True)
            self.sync_terminals(
                [c for c in self.get_terminals(False) if c.startswith("Child")], False
            )

    def on_connections_changed(self, inputs: set[str], outputs: set[str]) -> None:
        # Always keep exactly one free child slot at the bottom. Children come
        # first, so new ones go in front of the routing terminals.
        self._grow_terminals("Child", outputs, before="Bus")

        if self.is_custom:
            # Up to 4 aux sends, which is all a mixer can hold
            self._grow_terminals("Aux", outputs, limit=4)

    def _grow_terminals(
        self,
        prefix: str,
        outputs: dict[str, GraphDesignerNode],
        *,
        limit: int = 0,
        before: str = None,
    ) -> None:
        items = [o for o in self.get_terminals(False) if o.startswith(prefix)]
        last_used = max(
            (i for i, label in enumerate(items) if label in outputs), default=-1
        )
        wanted = last_used + 2
        if limit:
            wanted = min(limit, wanted)

        for label in items[wanted:]:
            self.remove_terminal(label, False)

        for i in range(len(items), wanted):
            self.add_terminal(f"{prefix} {i}", False, before=before)

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        if source is self:
            if output.startswith("Child"):
                # Whatever we mix becomes our child
                return input in ("Playback", "Parent")

            if output == "Bus":
                # Where our mix goes, which can be any kind of bus
                return target.node_type in (Bus, AuxiliaryBus) and input.startswith(
                    "Input"
                )

            if output.startswith("Aux"):
                # Sends only ever go to an auxiliary bus
                return target.node_type is AuxiliaryBus and input.startswith("Input")

            return False

        if target is self:
            if input == "Parent":
                # Only another mixer can adopt us - an action connected here
                # would end up as our parent
                return output.startswith("Child")

            if input == "Event":
                return source.node_type in (Event, Action)

            return False

        return super().link_valid(source, output, target, input)

    def validate(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> str:
        if not self.is_custom and not self._amx_selector.selected_node:
            return µ("No ActorMixer selected")

        if not self._connected(output_map, "Child"):
            return µ("Child not connected")

        return super().validate(bnk, input_map, output_map)

    def make_node(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> ActorMixer:
        if not self.is_custom:
            # An existing mixer, nothing to create - our children are parented
            # to it through node_id(). It still has to adopt them, unless it
            # lives in another bank, where we can only set the child's side.
            amx: ActorMixer = bnk.get(self.node_id())
            if amx is None:
                logger.warning(
                    f"{self}: #{self.node_id()} is not part of this bank, only "
                    "the children will know about the link"
                )
            else:
                for child in self._connected(output_map, "Child"):
                    amx.attach(child)

            return None

        # TODO aux sends
        aux = self._connected(output_map, "Aux")

        ret = ActorMixer.new(
            self.node_id(),
            output_map.get("Bus", 0),
            parent=input_map.get("Parent", 0),
            props=self.properties,
        )

        for child in self._connected(output_map, "Child"):
            ret.attach(child)

        return ret

    # === Helpers =======================================================

    @staticmethod
    def _connected(output_map: dict[str, int], prefix: str) -> list[int]:
        """The IDs behind our `prefix 0`, `prefix 1`, ... terminals, in order."""
        return [
            output_map[label]
            for label in sorted(output_map)
            if label.startswith(prefix) and output_map[label]
        ]
