from typing import Any, ClassVar
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.types import HIRCNode, MusicRandomSequenceContainer
from yonder.gui.localization import μ
from yonder.gui.designer.graph_designer_nodes import GraphDesignerNode, can_reference
from yonder.gui.widgets.music_playlist_editor import add_music_playlist_editor, PlaylistTreeItem


class MRSCNode(GraphDesignerNode):
    """A MusicRandomSequenceContainer, for playing a complex playlist of music pieces."""

    node_type: ClassVar[type[HIRCNode]] = MusicRandomSequenceContainer
    label: ClassVar[str] = "MusicRandomSequenceContainer"
    inputs: ClassVar[tuple[str, ...]] = ("Playback", "Event")
    outputs: ClassVar[tuple[str, ...]] = ("Item0",)

    def __init__(
        self,
        nid: str | int = 0
    ):
        super().__init__(nid)

        self.playlist: PlaylistTreeItem = PlaylistTreeItem.new()

    def build_body(self) -> None:
        with dpg.tree_node(label=µ("Playlist"), span_text_width=True):
            add_music_playlist_editor(self.playlist, None, compact=True)

    def on_connections_changed(self, inputs: set[str], outputs: set[str]) -> None:
        # Always keep exactly one free item slot at the bottom
        items = [o for o in self.get_terminals(False) if o.startswith("Item")]
        last_used = max(
            (i for i, label in enumerate(items) if label in outputs), default=-1
        )
        wanted = last_used + 2

        for label in items[wanted:]:
            self.remove_terminal(label, False)

        for i in range(len(items), wanted):
            self.add_terminal(f"Item{i}", False)

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        if source is self:
            return output.startswith("Item") and input == "Playback"

        # Either a parent container plays us, or an action targets us
        return can_reference(source.node_type, target.node_type)

    def make_node(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> MusicRandomSequenceContainer:
        parent = input_map.get("Playback", 0)
        
        # TODO build playlist

        return MusicRandomSequenceContainer.new(
            self.node_id(),
            props=self.properties,
            parent=parent,
        )

    # === DPG callbacks =================================================
