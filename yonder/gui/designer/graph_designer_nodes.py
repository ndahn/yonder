from __future__ import annotations
from typing import Any, Callable, ClassVar
from functools import cache
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.hash import Hash
from yonder.types import (
    HIRCNode,
    Action,
    Event,
)
from yonder.enums import PropID
from yonder.types.mixins import PropertyMixin
from yonder.gui.localization import µ
from yonder.gui import style
from yonder.gui.widgets import add_properties_table


# Node type -> designer node implementing it, filled by __init_subclass__
_designer_nodes: dict[type[HIRCNode], type[GraphDesignerNode]] = {}


def get_designer_node(node_type: type[HIRCNode]) -> type[GraphDesignerNode]:
    """Return the designer node registered for a HIRC node type, if any."""
    return _designer_nodes.get(node_type)


def get_designer_nodes() -> dict[type[HIRCNode], type[GraphDesignerNode]]:
    """Return all registered designer nodes, keyed by the HIRC type they create."""
    return dict(_designer_nodes)


def can_reference(source: type[HIRCNode], target: type[HIRCNode]) -> bool:
    """Whether a node of type `source` may hold a reference to a node of type `target`.

    This is a coarse, purely type based check used as the default for
    `GraphDesignerNode.link_valid`. Deriving classes should narrow it down
    further, e.g. a MusicSegment should only ever adopt MusicTracks.
    """
    if source is None or target is None:
        return False

    if target is Event:
        # Events are always entry points
        return False

    if source is Event:
        # Events automatically include the play/stop actions and could have additional actions
        return target is Action or hasattr(target, "parent")

    if target is Action:
        return False

    if source is Action:
        # Actions can target pretty much anything playable
        return True

    # Everything else has to be able to adopt the target as a child
    return hasattr(source, "attach")


@cache
def _node_theme(color: style.RGBA) -> str:
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(
                dpg.mvNodeCol_TitleBar,
                color.mix(style.black, 0.35),
                category=dpg.mvThemeCat_Nodes,
            )
            dpg.add_theme_color(
                dpg.mvNodeCol_TitleBarHovered, color, category=dpg.mvThemeCat_Nodes
            )
            dpg.add_theme_color(
                dpg.mvNodeCol_TitleBarSelected, color, category=dpg.mvThemeCat_Nodes
            )
            dpg.add_theme_color(
                dpg.mvNodeCol_NodeOutline,
                color.but(a=180),
                category=dpg.mvThemeCat_Nodes,
            )

    return theme


class GraphDesignerNode:
    """Base class for the nodes shown in the graph designer.

    One designer node stands for one HIRC node that is about to be created.
    It owns the dpg node widget, the terminals links can be attached to, and
    knows how to turn itself into an actual `HIRCNode` once the user is happy
    with the graph.

    Deriving classes are registered automatically by their `node_type` and
    should fill in the class variables plus whatever of the hooks below they
    need:

    - `build_body` to add widgets to the node
    - `link_valid` to decide which links are acceptable
    - `on_connections_changed` to add/remove terminals on the fly
    - `make_node` to create the HIRC node (and apply the widget values)
    - `connect` if the default "parent attaches child" is not what the link means
    - `validate` to refuse building until the node is configured properly

    Terminals are identified by a label that is unique per node and direction.
    Their dpg tags are derived from the node id, so they survive as long as
    the terminal exists, which is what links are bound to.

    Parameters
    ----------
    nid : int or str
        ID of the HIRC node that will be created. Generated if 0.
    """

    # Set by deriving classes
    node_type: ClassVar[type[HIRCNode]] = None
    label: ClassVar[str] = None
    inputs: ClassVar[tuple[str, ...]] = ()
    outputs: ClassVar[tuple[str, ...]] = ()
    show_name_field: ClassVar[bool] = False
    body_width: ClassVar[int] = 140

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls.node_type is not None:
            _designer_nodes[cls.node_type] = cls

    def __init__(self, nid: str | int = 0):
        self.nid = int(nid) if nid else dpg.generate_uuid()
        self.name: str = ""
        self.properties: dict[PropID, float] = {}
        self._editor: str | int = None
        self._inputs: list[str] = []
        self._outputs: list[str] = []
        self._widget_tags: list[str] = []

    # === Identity ======================================================

    @property
    def node_tag(self) -> str:
        return f"{self.nid}#NODE"

    @property
    def title(self) -> str:
        if self.label:
            return self.label

        if self.node_type:
            return self.node_type.__name__

        return type(self).__name__

    @property
    def color(self) -> style.RGBA:
        return style.type_colors.get(
            self.node_type.__name__ if self.node_type else None, style.light_grey
        )

    def node_id(self) -> Hash:
        """Name or ID the HIRC node will be created with."""
        return self.name or self.nid

    # === Terminals =====================================================

    def _make_tag(self, is_input: bool, label: str, suffix: str = None) -> str:
        return f"{self.nid}#{'IN' if is_input else 'OUT'}#{label}#{suffix or ''}"

    def _wtag(self, name: str) -> str:
        """Tag for a widget inside this node. Never parses as a terminal."""
        tag = f"{self.nid}#W#{name}"
        if tag not in self._widget_tags:
            self._widget_tags.append(tag)

        return tag

    def _split_tag(self, dpg_item_id: str | int) -> tuple[str, str]:
        """Return (direction, label) if the item is one of our terminals."""
        if not isinstance(dpg_item_id, str):
            dpg_item_id = dpg.get_item_alias(dpg_item_id)

        try:
            tag, in_out, label, *_ = dpg_item_id.split("#")
            if int(tag) != self.nid:
                return (None, None)
        except (AttributeError, ValueError):
            return (None, None)

        if in_out not in ("IN", "OUT"):
            return (None, None)

        return (in_out, label)

    def get_input_label(self, dpg_item_id: str | int) -> str:
        in_out, label = self._split_tag(dpg_item_id)
        return label if in_out == "IN" else None

    def get_input_terminal(self, label: str) -> str:
        return self._make_tag(True, label)

    def get_output_label(self, dpg_item_id: str | int) -> str:
        in_out, label = self._split_tag(dpg_item_id)
        return label if in_out == "OUT" else None

    def get_output_terminal(self, label: str) -> str:
        return self._make_tag(False, label)

    def get_terminals(self, is_input: bool) -> list[str]:
        """Labels of this node's current terminals, in the order they appear."""
        return list(self._inputs if is_input else self._outputs)

    def terminal_index(self, label: str, is_input: bool) -> int:
        """Position of a terminal within the node, or -1. Defines child order."""
        terminals = self._inputs if is_input else self._outputs
        return terminals.index(label) if label in terminals else -1

    def add_terminal(
        self,
        label: str,
        is_input: bool,
        *,
        before: str = None,
        widget: Callable[[str, bool], None] = None,
    ) -> str:
        """Add a terminal to the live dpg node and return its tag.

        Parameters
        ----------
        label : str
            Terminal label, unique per node and direction.
        is_input : bool
            Whether this is an input (left side) or output (right side).
        before : str, optional
            Label of the terminal to insert this one in front of.
        widget : callable, optional
            Called to fill the terminal, defaults to the (localized) label.
        """
        tag = self._make_tag(is_input, label)
        terminals = self._inputs if is_input else self._outputs
        if label in terminals:
            return tag

        kwargs = {}
        if before in terminals:
            kwargs["before"] = self._make_tag(is_input, before)
            terminals.insert(terminals.index(before), label)
        else:
            terminals.append(label)

        attribute_type = dpg.mvNode_Attr_Input if is_input else dpg.mvNode_Attr_Output
        with dpg.node_attribute(
            attribute_type=attribute_type,
            parent=self.node_tag,
            tag=tag,
            **kwargs,
        ):
            if widget:
                widget(label, is_input)
            else:
                dpg.add_text(µ(label))

        return tag

    def remove_terminal(self, label: str, is_input: bool) -> None:
        """Remove a terminal. Any link attached to it must be gone already."""
        terminals = self._inputs if is_input else self._outputs
        if label not in terminals:
            return

        terminals.remove(label)
        self._destroy_item(self._make_tag(is_input, label))

    # === Build =========================================================

    def build(self, parent: str | int, pos: tuple[float, float] = None) -> None:
        """Create the dpg node inside the given node editor."""
        self._editor = parent
        self._inputs.clear()
        self._outputs.clear()

        with dpg.node(
            label=self.title,
            pos=pos or [],
            tag=self.node_tag,
            parent=parent,
        ):
            with dpg.node_attribute(
                attribute_type=dpg.mvNode_Attr_Static, tag=self._wtag("body")
            ):
                if self.show_name_field:
                    dpg.add_input_text(
                        hint=µ("Name"),
                        default_value=self.name,
                        width=self.body_width,
                        callback=self._on_name_changed,
                        tag=self._wtag("name"),
                    )

                self.build_body()

                if issubclass(self.node_type, PropertyMixin):
                    with dpg.tree_node(label=µ("Properties"), span_text_width=True):
                        add_properties_table(
                            {},
                            self._on_update_properties,
                            label=None,
                            compact=True,
                            tag=self._wtag("properties"),
                        )

        for label in self.inputs:
            self.add_terminal(label, True)

        for label in self.outputs:
            self.add_terminal(label, False)

        dpg.bind_item_theme(self.node_tag, _node_theme(self.color))

    def destroy(self) -> None:
        for label in list(self._inputs):
            self.remove_terminal(label, True)

        for label in list(self._outputs):
            self.remove_terminal(label, False)

        for tag in self._widget_tags:
            self._destroy_item(tag)

        self._widget_tags.clear()
        self._destroy_item(self.node_tag)

    def _destroy_item(self, tag: str) -> None:
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        if dpg.does_alias_exist(tag):
            try:
                dpg.remove_alias(tag)
            except SystemError:
                pass

    # === DPG callbacks =================================================

    def _on_name_changed(self, sender: str, new_name: str, user_data: Any) -> None:
        self.name = new_name.strip()

    def _on_update_properties(
        self, sender: str, props: dict[PropID, float], user_data: Any
    ) -> None:
        self.properties = props

    # === Hooks =========================================================

    def build_body(self) -> None:
        """Add widgets to the node's static attribute. For deriving classes."""
        pass

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        """Whether this node accepts the given link.

        Called on both endpoints, both of which have to agree. Structural
        constraints (self links, cycles, terminals already in use) are handled
        by the designer and don't have to be checked here.
        """
        return can_reference(source.node_type, target.node_type)

    def on_connections_changed(self, inputs: set[str], outputs: set[str]) -> None:
        """Called whenever a link to this node was added or removed.

        Receives the labels of all currently connected terminals, which is
        the place to add or remove dynamic terminals (see `RSCNode`).
        """
        pass

    def validate(self, bnk: Soundbank) -> str:
        """Return a message describing why this node can't be built yet, if any."""
        if self.node_type is None:
            return µ("{node} cannot be created", "msg").format(node=self.title)

        if self.name and self.name in bnk:
            return µ("The soundbank already contains {name}", "msg").format(
                name=self.name
            )

        return None

    def make_node(self, bnk: Soundbank) -> HIRCNode:
        """Create the HIRC node this designer node stands for.

        Links are applied separately through `connect`, so children don't have
        to be known here.
        """
        return self.node_type.new(self.node_id())

    def connect(
        self,
        bnk: Soundbank,
        my_node: HIRCNode,
        output: str,
        other: GraphDesignerNode,
        other_node: HIRCNode,
        input: str,
    ) -> None:
        """Apply one of this node's outgoing links to the created HIRC nodes.

        Called once per link, on the source node, in terminal order.
        """
        attach = getattr(my_node, "attach", None)
        if callable(attach):
            attach(other_node)
        elif isinstance(my_node, Action):
            my_node.external_id = other_node.id
        elif hasattr(other_node, "parent"):
            other_node.parent = my_node.id
        else:
            raise TypeError(f"Don't know how to attach {other_node} to {my_node}")

    def __str__(self) -> str:
        return f"[{self.title}] {self.name or f'#{self.nid}'}"

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name or ''} #{self.nid}>"
