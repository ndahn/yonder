from typing import Any, ClassVar
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.enums import RandomSequenceMode
from yonder.types import HIRCNode, MusicRandomSequenceContainer, PlaylistTreeItem
from yonder.gui.localization import μ
from yonder.gui.designer.graph_designer_node import GraphDesignerNode, can_reference
from yonder.gui.widgets import add_music_playlist_editor


class MRSCNode(GraphDesignerNode):
    """A MusicRandomSequenceContainer, for playing a complex playlist of music pieces."""

    node_type: ClassVar[type[HIRCNode]] = MusicRandomSequenceContainer
    label: ClassVar[str] = "MusicRandomSequenceContainer"
    inputs: ClassVar[tuple[str, ...]] = ("Playback", "Event")
    outputs: ClassVar[tuple[str, ...]] = ("Item 0",)

    def __init__(self, bnk: Soundbank, nid: str | int = 0):
        super().__init__(bnk, nid)

        default_tree = PlaylistTreeItem.new()
        default_tree.children.append(
            PlaylistTreeItem.new(RandomSequenceMode.Inherit, parent=default_tree)
        )

        self.playlist: PlaylistTreeItem = default_tree
        self._playlist_editor: add_music_playlist_editor = None

    def build(self, parent: str | int, pos: tuple[float, float] = None) -> None:
        super().build(parent, pos)
        self._on_playlist_changed(self.node_tag, self.playlist, None)

    def build_body(self) -> None:
        with dpg.tree_node(label=µ("Playlist"), span_text_width=True):
            self._playlist_editor = add_music_playlist_editor(
                self.playlist, self._on_playlist_changed, compact=True
            )

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

    def validate(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> str:
        if self.playlist.item.ers_type_enum == RandomSequenceMode.Inherit:
            return µ("Playlist root cannot have mode 'Inherit'")

        if "Playback" not in input_map:
            return µ("Playback not connected")
        
        return super().validate(bnk, input_map, output_map)

    def make_node(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> MusicRandomSequenceContainer:
        parent = input_map.get("Playback", 0)

        # Resolve the leaf items against the segments connected to our terminals
        playlist = self.playlist.copy()
        for leaf in playlist.leaves():
            label = self._playlist_editor.get_playlist_item_label(leaf.item)
            leaf.item.segment_id = output_map.get(label, 0)

        return MusicRandomSequenceContainer.new(
            self.node_id(),
            playlist=playlist,
            props=self.properties,
            parent=parent,
        )

    # === DPG callbacks =================================================

    def _on_playlist_changed(
        self, sender: str, playlist: PlaylistTreeItem, user_data: Any
    ) -> None:
        self.playlist = playlist

        # One terminal per playlist leaf; dropped leaves take their link with them
        leafs = [
            self._playlist_editor.get_playlist_item_label(leaf.item)
            for leaf in playlist.leaves()
        ]
        self.sync_terminals(leafs, False)
