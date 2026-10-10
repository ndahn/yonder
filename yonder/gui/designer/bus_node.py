from typing import ClassVar, Any
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.hash import calc_hash
from yonder.types import HIRCNode, AuxiliaryBus, Bus
from yonder.gui.designer.graph_designer_node import GraphDesignerNode, can_reference
from yonder.gui.localization import μ


class BusNode(GraphDesignerNode):
    """A Bus mixes different sources and can apply effects.

    Busses and auxiliary busses hold the exact same data and only differ in
    their HIRC type and in how they are fed: a bus receives whatever is routed
    to it (the `Input` terminals, which is the bus the source names as its
    output bus), an auxiliary bus additionally receives the aux sends of other
    nodes. `Bus` is where our own mix ends up, `Aux` is a send of our own.

    Which of the two is created is decided by the "is aux" checkbox, so
    `node_type` is per instance here rather than per class.
    """

    node_type: ClassVar[type[HIRCNode]] = Bus
    label: ClassVar[str] = "Bus"
    show_name_field: ClassVar[bool] = True
    inputs: ClassVar[tuple[str, ...]] = ("Input 0",)
    outputs: ClassVar[tuple[str, ...]] = ("Aux", "Bus")

    def __init__(self, bnk: Soundbank, nid: str | int = 0, *, is_aux: bool = True):
        super().__init__(bnk, nid)
        self._bnk = bnk
        self.is_aux = is_aux

        # Shadows the class variables, see the class docstring
        self.node_type = AuxiliaryBus if is_aux else Bus
        self.label = self.node_type.__name__

    def build_body(self) -> None:
        # TODO ducking, effects
        dpg.add_checkbox(
            label=µ("is aux"),
            default_value=self.is_aux,
            callback=self._on_aux_changed,
            tag=self._wtag("is_aux"),
        )

    def on_connections_changed(
        self,
        inputs: dict[str, GraphDesignerNode],
        outputs: dict[str, GraphDesignerNode],
    ) -> None:
        # Always keep exactly one free input slot at the bottom
        items = [i for i in self.get_terminals(True) if i.startswith("Input")]
        last_used = max(
            (i for i, label in enumerate(items) if label in inputs), default=-1
        )
        wanted = last_used + 2

        for label in items[wanted:]:
            self.remove_terminal(label, True)

        for i in range(len(items), wanted):
            self.add_terminal(f"Input {i}", True)

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        if source is self:
            if output == "Bus":
                # Our mix goes to any kind of bus
                wanted = (Bus, AuxiliaryBus)
            elif output == "Aux":
                # A send only ever goes to an auxiliary bus
                wanted = (AuxiliaryBus,)
            else:
                return False

            if isinstance(target, BusNode):
                return target.node_type in wanted and input.startswith("Input")

            # Could still be a reference to a bus that already exists, in which
            # case the reference node checks what it actually points to
            return input == "Parent" and can_reference(
                self.node_type, target.node_type
            )

        if target is self:
            if not input.startswith("Input"):
                return False

            if output.startswith("Aux"):
                # Sends can only arrive here if we are an auxiliary bus
                return self.node_type is AuxiliaryBus

            # Either someone routes their mix to us, or an action targets us
            return output in ("Bus", "Target")

        return super().link_valid(source, output, target, input)

    def validate(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> str:
        if not self.name:
            # Busses are referenced by name from all over the place, an ID only
            # bus is next to useless
            return µ("Name not set")

        return super().validate(bnk, input_map, output_map)

    def make_node(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> Bus | AuxiliaryBus:
        # TODO ducking
        bus: Bus = self.node_type.new(
            self.node_id(),
            override_bus_id=output_map.get("Bus", 0),
            props=self.properties,
        )

        aux = output_map.get("Aux")
        if aux:
            # Busses can have up to 4 user aux sends, we only offer one for now.
            # NOTE the flags are what Wwise sets when a send is added by hand,
            # i.e. use our own sends instead of inheriting any.
            aux_params = bus.initial_values.bus_initial_params.aux_params
            aux_params.aux1 = calc_hash(aux)
            aux_params.has_aux = True
            aux_params.override_user_aux_sends = True

        return bus

    # === DPG callbacks =================================================

    def _on_aux_changed(self, sender: str, is_aux: bool, user_data: Any) -> None:
        self.is_aux = is_aux
        self.node_type = AuxiliaryBus if is_aux else Bus
        self.label = self.node_type.__name__
        dpg.configure_item(self.node_tag, label=self.title)
