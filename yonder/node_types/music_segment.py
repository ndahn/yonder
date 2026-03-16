from yonder.node import Node
from yonder.hash import calc_hash
from yonder.util import PathDict, logger
from .wwise_node import WwiseNode
from .mixins import ContainerMixin


class MusicSegment(ContainerMixin, WwiseNode):
    """A timed piece of interactive music with tempo, time signature, and markers.

    Contains music tracks and defines the musical structure for adaptive music systems.
    """
    base_params_path = "music_node_params/node_base_params"
    children_path = "music_node_params/children"

    # Marker IDs, we don't know the string values of these
    loop_start_id = 43573010
    loop_end_id = 1539036744
    

    @classmethod
    def new(
        cls,
        nid: int,
        duration: float = 0.0,
        parent: int | Node = None,
    ) -> "MusicSegment":
        """Create a new MusicSegment node.

        Parameters
        ----------
        nid : int
            Node ID (hash).
        duration : float, default=0.0
            Segment duration in milliseconds.
        parent : int | Node, default=None
            Parent node.

        Returns
        -------
        MusicSegment
            New MusicSegment instance.
        """
        temp = cls.load_template(cls.__name__)

        segment = cls(temp)
        segment.id = nid
        segment.duration = duration
        if parent is not None:
            segment.parent = parent

        logger.info(f"Created new node {segment}")
        return segment

    @property
    def music_params(self) -> PathDict:
        return PathDict(self["music_node_params"])

    @property
    def duration(self) -> float:
        """Segment duration in milliseconds.

        Returns
        -------
        float
            Duration in ms.
        """
        return self["duration"]

    @duration.setter
    def duration(self, value: float) -> None:
        self["duration"] = value

    @property
    def markers(self) -> list[dict]:
        """Timing markers for synchronization and transitions within the segment.

        Returns
        -------
        list[dict]
            List of marker dictionaries with id, position, and string.
        """
        return self["markers"]

    def set_marker(self, marker_id: str | int, position: float) -> int:
        """Places a timing marker at a specific position within the segment.

        Parameters
        ----------
        marker_id : str | int
            Unique marker ID.
        position : float
            Position in milliseconds.
        name : str, default=""
            Optional marker name.
        """
        marker = self.get_marker(marker_id)

        if marker:
            marker["position"] = position
        else:
            name = ""
            if isinstance(marker_id, str):
                name = marker_id
                marker_id = calc_hash(marker_id)
            else:
                name = self.lookup_name(marker_id, "")
            
            marker = {
                "id": marker_id,
                "position": position,
                "string_length": len(name) + 1 if name else 0,
                "string": name,
            }
            self["markers"].append(marker)
            self["marker_count"] = len(self["markers"])

        # Not sure if it's required, but just in case keep markers sorted by position
        self["markers"].sort(key=lambda m: m["position"])
        return marker_id

    def get_marker(self, marker_id: str | int, default: float = None) -> dict:
        if isinstance(marker_id, str):
            marker_id = calc_hash(marker_id)

        for m in self.markers:
            if m["id"] == marker_id:
                return m

        return default

    def remove_marker(self, marker_id: str | int) -> bool:
        """Removes a timing marker from the segment.

        Parameters
        ----------
        marker_id : str | int
            Marker ID to remove.

        Returns
        -------
        bool
            True if marker was removed, False if not found.
        """
        if isinstance(marker_id, str):
            marker_id = calc_hash(marker_id)

        markers = self["markers"]
        for i, marker in enumerate(markers):
            if marker["id"] == marker_id:
                markers.pop(i)
                self["marker_count"] = len(markers)
                return True
        return False

    def clear_markers(self) -> None:
        """Removes all timing markers from the segment."""
        self["markers"] = []
        self["marker_count"] = 0
