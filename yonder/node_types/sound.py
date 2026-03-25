from typing import TYPE_CHECKING
from pathlib import Path

from yonder.node import Node
from yonder.enums import SourceType, PluginType
from yonder.util import logger
from .wwise_node import WwiseNode

if TYPE_CHECKING:
    from yonder.soundbank import Soundbank


class Sound(WwiseNode):
    """The fundamental playable audio object.

    Contains a single audio file (embedded or streamed) with codec settings and 3D positioning parameters.
    """

    @classmethod
    def new(
        cls,
        nid: int,
        source_id: int,
        source_type: SourceType = "Embedded",
        plugin: str = "VORBIS",
        parent: int | Node = None,
    ) -> "Sound":
        """Create a new Sound node.

        Parameters
        ----------
        nid : int
            Node ID (hash).
        source_id : int
            Media source ID.
        plugin : str, default="VORBIS"
            Codec plugin ('VORBIS', 'PCM', etc.).
        source_type : SourceType, default="Embedded"
            Source type ('Embedded' or 'Streamed').
        parent : int | Node, default=None
            Parent node.

        Returns
        -------
        Sound
            New Sound instance.
        """
        temp = cls.load_template(cls.__name__)

        sound = cls(temp)
        sound.id = nid
        sound.source_id = source_id
        sound.plugin = plugin
        sound.source_type = source_type
        if parent is not None:
            sound.parent = parent

        logger.info(f"Created new node {sound}")
        return sound

    @classmethod
    def new_from_wem(
        cls,
        nid: int,
        wem: Path,
        source_type: SourceType = "Embedded",
        plugin: str = "VORBIS",
        parent: int | Node = None,
    ) -> "Sound":
        wem_id = int(wem.stem)
        sound = cls.new(nid, wem_id, source_type, plugin=plugin, parent=parent)
        sound.media_size = len(wem.read_bytes())
        return sound

    @property
    def source_info(self) -> dict:
        return self["bank_source_data"]

    @property
    def source_id(self) -> int:
        """Media source ID.

        Returns
        -------
        int
            Source ID referencing the audio data.
        """
        return self["bank_source_data/media_information/source_id"]

    @source_id.setter
    def source_id(self, value: int) -> None:
        self["bank_source_data/media_information/source_id"] = value

    def get_source_path(self, bnk: "Soundbank") -> Path:
        src = self.source_id
        if src <= 0:
            return None

        if self.source_type == "Embedded":
            return bnk.bnk_dir / f"{src}.wem"

        return bnk.bnk_dir.parent / "wem" / f"{str(self.source_id)[:2]}" / f"{self.source_id}.wem"

    @property
    def plugin(self) -> PluginType:
        """Codec plugin type.

        Returns
        -------
        PluginType
            Plugin name (e.g., 'VORBIS', 'PCM').
        """
        return self["bank_source_data/plugin"]

    @plugin.setter
    def plugin(self, value: PluginType) -> None:
        self["bank_source_data/plugin"] = value

    @property
    def source_type(self) -> SourceType:
        """Source type.

        Returns
        -------
        SourceType
            Source type (e.g., 'Embedded', 'Streamed').
        """
        return self["bank_source_data/source_type"]

    @source_type.setter
    def source_type(self, value: SourceType) -> None:
        self["bank_source_data/source_type"] = value

    @property
    def media_size(self) -> int:
        """In-memory media size in bytes.

        Returns
        -------
        int
            Size of audio data in bytes.
        """
        return self["bank_source_data/media_information/in_memory_media_size"]

    @media_size.setter
    def media_size(self, value: int) -> None:
        self["bank_source_data/media_information/in_memory_media_size"] = value

    @property
    def enable_attenuation(self) -> bool:
        """Controls whether distance-based volume falloff is applied.

        Returns
        -------
        bool
            True if attenuation is enabled.
        """
        return self.base_params["positioning_params/enable_attenuation"]

    @enable_attenuation.setter
    def enable_attenuation(self, value: bool) -> None:
        self.base_params["positioning_params/enable_attenuation"] = value

    @property
    def three_dimensional_spatialization(self) -> str:
        """Controls how positional audio is rendered in 3D space.

        Returns
        -------
        str
            Spatialization mode (e.g., 'None', 'Position', 'PositionAndOrientation').
        """
        return self.base_params[
            "positioning_params/three_dimensional_spatialization_mode"
        ]

    @three_dimensional_spatialization.setter
    def three_dimensional_spatialization(self, value: str) -> None:
        self.base_params["positioning_params/three_dimensional_spatialization_mode"] = (
            value
        )

    def get_references(self) -> list[tuple[str, int]]:
        refs = super().get_references()

        # Refers to the wem filename, but it seems like there can ALSO be 
        # CustomEffects with a matching ID that would apply to it
        refs.append(("bank_source_data/media_information/source_id", self.source_id))
        return refs
