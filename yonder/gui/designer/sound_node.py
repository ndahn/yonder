from typing import Any, ClassVar
from pathlib import Path
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.types import HIRCNode, Sound
from yonder.enums import SourceType
from yonder.gui.designer.graph_designer_nodes import GraphDesignerNode
from yonder.gui.localization import μ
from yonder.gui.widgets import add_generic_widget


class SoundNode(GraphDesignerNode):
    """A Sound that plays back a short audio sample."""

    node_type: ClassVar[type[HIRCNode]] = Sound
    label: ClassVar[str] = "Sound"
    inputs: ClassVar[tuple[str, ...]] = ("Playback", "Effect0")
    outputs: ClassVar[tuple[str, ...]] = ()

    def __init__(
        self,
        nid: str | int = 0,
        *,
        wem_path: Path = None,
        source_type: SourceType = SourceType.Embedded,
    ):
        super().__init__(nid)

        self.wem_path: Path = wem_path
        self.source_type = source_type

    def build_body(self) -> None:
        add_generic_widget(
            Path,
            None,
            self._on_wem_path_changed,
            default=self.wem_path,
            filetypes={
                µ("Audio Files (.wav, .wem)", "filetypes"): ["*.wav", "*.wem"],
                µ("Wave (.wav)", "filetypes"): "*.wav",
                µ("WEM (.wem)", "filetypes"): "*.wem",
            },
            filename_only=True,
            width=self.body_width,
            tag=self._wtag("wem_path"),
        )
        dpg.add_combo(
            [s.name for s in SourceType],
            default_value=self.source_type.name,
            width=self.body_width,
            callback=self._on_source_type_changed,
            tag=self._wtag("source_type"),
        )

    def validate(self, bnk: Soundbank) -> bool:
        if not self.wem_path:
            return µ("No wem selected")

        return None

    def make_node(self, bnk: Soundbank) -> Sound:
        return Sound.new(self.nid, self.wem_path, self.source_type, props=self.properties)

    # === DPG callbacks =================================================

    def _on_wem_path_changed(self, sender: str, wem_path: Path, user_data: Any) -> None:
        self.wem_path = wem_path

    def _on_source_type_changed(self, sender: str, source_type: str, user_data: Any) -> None:
        self.source_type = SourceType[source_type]
