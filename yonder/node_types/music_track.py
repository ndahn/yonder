from typing import TYPE_CHECKING
from pathlib import Path

from yonder.node import Node
from yonder.enums import SourceType
from yonder.util import logger
from yonder.wem import get_wem_metadata
from .wwise_node import WwiseNode

if TYPE_CHECKING:
    from yonder.soundbank import Soundbank


class MusicTrack(WwiseNode):
    """An individual audio track within a music segment.

    Contains the actual audio sources and defines when/how they play within the segment timeline.
    """

    @classmethod
    def new(
        cls,
        nid: int,
        parent: int | Node = None,
    ) -> "MusicTrack":
        """Create a new MusicTrack node.

        Parameters
        ----------
        nid : int
            Node ID (hash).
        parent : int | Node, default=None
            Parent node.

        Returns
        -------
        MusicTrack
            New MusicTrack instance.
        """
        temp = cls.load_template(cls.__name__)

        track = cls(temp)
        track.id = nid
        if parent is not None:
            track.parent = parent

        logger.info(f"Created new node {track}")
        return track

    @classmethod
    def new_from_wem(
        cls,
        nid: int,
        wem: Path,
        source_type: SourceType = "Streaming",
        begin_trim: float = 0.0,
        end_trim: float = 0.0,
        parent: int | Node = None,
    ) -> "MusicTrack":
        track = cls.new(nid, parent=parent)
        track.add_source_full_from_file(wem, source_type, begin_trim, end_trim)
        return track

    @property
    def track_type(self) -> int:
        """Track type.

        Returns
        -------
        int
            Track type identifier.
        """
        return self["track_type"]

    @track_type.setter
    def track_type(self, value: int) -> None:
        self["track_type"] = value

    @property
    def look_ahead_time(self) -> int:
        """Look-ahead time in milliseconds.

        Returns
        -------
        int
            Look-ahead time in ms.
        """
        return self["look_ahead_time"]

    @look_ahead_time.setter
    def look_ahead_time(self, value: int) -> None:
        self["look_ahead_time"] = value

    @property
    def subtrack_count(self) -> int:
        """Number of subtracks.

        Returns
        -------
        int
            Number of subtracks.
        """
        return self["subtrack_count"]

    @subtrack_count.setter
    def subtrack_count(self, value: int) -> None:
        self["subtrack_count"] = value

    @property
    def sources(self) -> list[dict]:
        """Audio files used by this track.

        Returns
        -------
        list[dict]
            List of source dictionaries with plugin, source_type, and media_information.
        """
        return self["sources"]

    def get_source_path(self, bnk: "Soundbank", source_index: int) -> Path:
        src = self.sources[source_index]["media_information"]["source_id"]
        if src <= 0:
            return None

        return bnk.bnk_dir / f"{src}.wem"

    @property
    def playlist(self) -> list[dict]:
        """Timing and playback configuration for sources on the timeline.

        Returns
        -------
        list[dict]
            List of playlist item dictionaries.
        """
        return self["playlist"]

    def add_source_from_file_full(self, wem: Path, source_type: SourceType, begin_trim: float = 0.0, end_trim: float = 0.0) -> None:
        wem_id = int(wem.stem)
        meta = get_wem_metadata(wem)
        size = meta["in_memory_size"]

        self.add_source(wem_id, size, source_type)
        self.add_playlist_item(
            wem_id,
            meta["duration"] * 1000,  # ms
            begin_trim=begin_trim,
            end_trim=end_trim,
        )

    def add_source(
        self,
        source_id: int,
        media_size: int,
        source_type: SourceType = "Embedded",
        plugin: str = "VORBIS",
    ) -> None:
        """Associates an audio file with this track.

        Parameters
        ----------
        source_id : int
            Media source ID.
        media_size : int
            In-memory media size in bytes.
        source_type : SourceType
            Source type.
        plugin : str
            Codec plugin.
        """
        source = {
            "plugin": plugin,
            "source_type": source_type,
            "media_information": {
                "source_id": source_id,
                "in_memory_media_size": media_size,
                "source_flags": 0,
            },
            "params_size": 0,
            "params": "",
        }
        self["sources"].append(source)
        self["source_count"] = len(self["sources"])

    def add_playlist_item(
        self,
        source_id: int,
        duration: float,
        begin_trim: float = 0.0,
        end_trim: float = 0.0,
    ) -> None:
        """Schedules a source to play at a specific time on the track timeline.

        Parameters
        ----------
        source_id : int
            Source ID to play.
        duration : float
            Duration in milliseconds.
        begin_trim : float, default=0.0
            Trim offset from beginning in ms.
        end_trim : float, default=0.0
            Trim offset from end in ms.
        """
        item = {
            "track_id": 0,
            "source_id": source_id,
            "event_id": 0,
            # According to bgm tutorial
            # https://docs.google.com/document/d/1Dx8U9q6iEofPtKtZ0JI1kOedJYs9ifhlO7H5Knil5sg/edit?tab=t.0
            "play_at": -begin_trim,
            "begin_trim_offset": begin_trim,
            "end_trim_offset": end_trim,
            "source_duration": duration,
        }
        self["playlist"].append(item)
        self["playlist_item_count"] = len(self["playlist"])

    # TODO clip items
    # {
    #     "clip_index": 0,
    #     "auto_type": "FadeIn",
    #     "graph_point_count": 2,
    #     "graph_points": [
    #         {
    #         "from": 0.0,
    #         "to": 0.0,
    #         "interpolation": "Sine"
    #         },
    #         {
    #         "from": 0.20927228,
    #         "to": 1.0,
    #         "interpolation": "Constant"
    #         }
    #     ]
    #     }

    def clear_sources(self) -> None:
        """Disassociates all audio sources from this track."""
        self["sources"] = []
        self["source_count"] = 0

    def clear_playlist(self) -> None:
        """Clears the track timeline, removing all scheduled playback items."""
        self["playlist"] = []
        self["playlist_item_count"] = 0

    def get_references(self) -> list[tuple[str, int]]:
        refs = super().get_references()

        # Refers to the wem filename, but it seems like there can ALSO be
        # CustomEffects with a matching ID that would apply to it
        for i, source in enumerate(self.sources):
            refs.append(
                (
                    f"sources:{i}/media_information/source_id",
                    source["media_information"]["source_id"],
                )
            )
            
        return refs
