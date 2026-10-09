from typing import Any, ClassVar
from pathlib import Path
import wave
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.types import HIRCNode, MusicTrack
from yonder.enums import SourceType
from yonder.wem import get_wem_metadata
from yonder.gui.designer.graph_designer_node import GraphDesignerNode
from yonder.gui.localization import μ
from yonder.gui.widgets import add_generic_widget


class MTNode(GraphDesignerNode):
    """A MusicTrack that plays back a longer audio piece."""

    node_type: ClassVar[type[HIRCNode]] = MusicTrack
    label: ClassVar[str] = "MusicTrack"
    inputs: ClassVar[tuple[str, ...]] = ("Playback", "Effect0")
    outputs: ClassVar[tuple[str, ...]] = ()

    def __init__(
        self,
        bnk: Soundbank,
        nid: str | int = 0,
        *,
        wem_path: Path = None,
    ):
        super().__init__(bnk, nid)

        self.wem_path: Path = wem_path
        self._duration = 0.0

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
        # TODO trims

    @property
    def duration(self) -> float:
        return self._duration

    def validate(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> str:
        if "Playback" not in input_map:
            return µ("Playback not connected")
        
        return super().validate(bnk, input_map, output_map)

    def make_node(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> MusicTrack:
        # TODO effects
        parent = input_map.get("Playback", 0)
        return MusicTrack.new(
            self.nid,
            self.wem_path,
            source_type=SourceType.Embedded,
            props=self.properties,
            parent=parent,
        )

    # === DPG callbacks =================================================

    def _on_wem_path_changed(self, sender: str, wem_path: Path, user_data: Any) -> None:
        self.wem_path = wem_path

        if wem_path:
            if wem_path.suffix == ".wem":
                self._duration = get_wem_metadata(wem_path)["duration"]
            else:
                with wave.open(wem_path) as f:
                    self._duration = f.getnframes() / f.getframerate()
