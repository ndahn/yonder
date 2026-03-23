from yonder.node import Node
from yonder.util import logger, PathDict
from yonder.enums import CurveType, SyncType
from .wwise_node import WwiseNode
from .mixins import ContainerMixin


class MusicRandomSequenceContainer(ContainerMixin, WwiseNode):
    """Interactive music playlist that randomly or sequentially plays music segments.

    Includes transition rules for smooth musical transitions and weighted selection for segments.
    """
    base_params_path = "music_trans_node_params/music_node_params/node_base_params"
    children_path = "music_trans_node_params/music_node_params/children"
    

    @classmethod
    def new(
        cls,
        nid: int,
        parent: int | Node = None,
    ) -> "MusicRandomSequenceContainer":
        """Create a new MusicRandomSequenceContainer node.

        Parameters
        ----------
        nid : int
            Node ID (hash).
        parent : int | Node, default=None
            Parent node.

        Returns
        -------
        MusicRandomSequenceContainer
            New MusicRandomSequenceContainer instance.
        """
        temp = cls.load_template(cls.__name__)

        container = cls(temp)
        container.id = nid
        if parent is not None:
            container.parent = parent

        logger.info(f"Created new node {container}")
        return container

    @property
    def music_params(self) -> PathDict:
        return PathDict(self["music_trans_node_params/music_node_params"])

    @property
    def playlist_items(self) -> list[dict]:
        """Segments in the playlist with their weights and loop settings.

        Returns
        -------
        list[dict]
            List of playlist item dictionaries with segment_id, weight, and loop settings.
        """
        return self["playlist_items"]

    @property
    def transition_rules(self) -> list[dict]:
        """Rules defining musical transitions between segments.

        Returns
        -------
        list[dict]
            List of transition rule dictionaries.
        """
        return self["music_trans_node_params/transition_rules"]

    def _update_children_list(self) -> None:
        children_set = set()

        for playlist_item in self.playlist_items:
            children_set.add(playlist_item.get("segment_id", 0))

        # Update the children list
        children = self.music_params["children/items"]
        children.clear()
        children.extend(sorted(c for c in children_set if c > 0))
        self.music_params["children/count"] = len(children)

    def add_playlist_item(
        self,
        playlist_item_id: int,
        segment_id: int | Node,
        weight: int = 50000,
        use_weight: bool = False,
        shuffle: bool = False,
        avoid_repeat: int = 0,
        loop_base: bool = False,
        ers_type: int = 4294967295,
        parent: int = 0,
    ) -> int:
        """Associates a segment with this playlist for random/sequential playback. A playlist is actually a flattened tree structure where children inherit settings from their parents. Use the parent parameter to associate child items to their parents.

        Parameters
        ----------
        playlist_item_id : int
            Unique playlist item ID.
        segment_id : int | Node
            Segment node ID.
        weight : int, default=50000
            Relative weight for random selection.
        use_weight : bool, default=False
            Whether to use weight when shuffling. Always True for the first playlist item.
        avoid_repeat : int, default=0
            Number of recent items to avoid repeating.
        ers_type : int, default=0
            Playlist playback type (0 - sequence, 1 - random, 2 - shuffle, 4294967295 - inherit).
        parent : int, default=0
            Which playlist item to associate the new item with (0 - root).
        """
        if isinstance(segment_id, Node):
            if segment_id.parent > 0 and segment_id.parent != self.id:
                logger.warning(f"Adding already adopted child {segment_id} to {self}")

            segment_id = segment_id.id

        if len(self.playlist_items) == 0:
            if parent > 0:
                raise ValueError("parent cannot be set for first playlist item")
            if ers_type == 4294967295:
                raise ValueError("ers_type cannot be 'inherit' for first playlist item")
            use_weight = True

        new_item = {
            "segment_id": segment_id,
            "playlist_item_id": playlist_item_id,
            "child_count": 0,
            "ers_type": ers_type,
            "loop_base": 1 if loop_base else 0,
            "loop_min": 0,
            "loop_max": 0,
            "weight": weight,
            "avoid_repeat_count": avoid_repeat,
            "use_weight": 1 if use_weight else 0,
            "shuffle": 1 if shuffle else 0,
        }

        if parent > 0:
            # Insert after parent
            for idx, item in enumerate(self.playlist_items):
                if item["playlist_item_id"] == parent:
                    insert_idx = idx + 1
                    parent_item = item
                    break
            else:
                raise ValueError(f"No playlist item with key {parent}")

            insert_idx += parent_item["child_count"]
            parent_item["child_count"] += 1
            self.playlist_items.insert(insert_idx, new_item)
        else:
            self["playlist_items"].append(new_item)

        self["playlist_item_count"] = len(self["playlist_items"])
        self._update_children_list()

        return playlist_item_id

    def remove_playlist_item(self, playlist_item_id: int | Node) -> bool:
        """Disassociates a playlist item from this container.

        Parameters
        ----------
        playlist_item_id : int
            Playlist item ID to remove.

        Returns
        -------
        bool
            True if item was removed, False if not found.
        """
        if isinstance(playlist_item_id, Node):
            playlist_item_id = playlist_item_id.id

        items = self["playlist_items"]
        for i, item in enumerate(items):
            if item["playlist_item_id"] == playlist_item_id:
                items.pop(i)
                self["playlist_item_count"] = len(items)
                self._update_children_list()
                return True

        return False

    def clear_playlist(self) -> None:
        """Disassociates all playlist items from this container."""
        self["playlist_items"] = []
        self["playlist_item_count"] = 0
        self._update_children_list()

    def add_transition_rule(
        self,
        source_ids: int | list[int] = -1,
        dest_ids: int | list[int] = -1,
        source_transition_time: int = 0,
        source_fade_offset: int = 0,
        source_fade_curve: CurveType = "Linear",
        source_play_post_exit: bool = False,
        sync_type: SyncType = "Immediate",
        dest_transition_time: int = 0,
        dest_fade_offset: int = 0,
        dest_fade_curve: CurveType = "Linear",
        dest_play_pre_entry: bool = False,
        transition_segment: int | Node = 0,
    ) -> None:
        """Add a transition rule between segments.

        Parameters
        ----------
        source_ids : int | list[int], default = -1
            Source segment IDs (-1 = any).
        dest_ids : int | list[int], default = -1
            Destination segment IDs (-1 = any).
        source_transition_time : int, default=0
            Source fade out time in ms.
        source_fade_offset : int, default=0
            Delay in ms before the source starts fading out.
        source_fade_curve : str, default="Linear"
            Source fade out curve type.
        sync_type : SyncType, default="Immediate"
            Marker sync type.
        dest_transition_time : int, default=0
            Destination fade out time in ms.
        dest_fade_offset : int, default=0
            Delay in ms before the destination starts fading in.
        dest_fade_curve : str, default="Linear"
            Destination fade in curve type.
        transition_segment: int | Node, default=0
            A MusicSegment to play during the transition.
        """
        if isinstance(source_ids, int):
            source_ids = [source_ids]

        if isinstance(dest_ids, int):
            dest_ids = [dest_ids]

        rule = {
            "source_transition_rule_count": len(source_ids),
            "source_ids": source_ids,
            "destination_transition_rule_count": len(dest_ids),
            "destination_ids": dest_ids,
            "source_transition_rule": {
                "transition_time": source_transition_time,
                "fade_curve": source_fade_curve,
                "fade_offet": source_fade_offset,
                "sync_type": sync_type,
                "clue_filter_hash": 0,
                "play_post_exit": 1 if source_play_post_exit else 0,
            },
            "destination_transition_rule": {
                "transition_time": dest_transition_time,
                "fade_curve": dest_fade_curve,
                "fade_offet": dest_fade_offset,
                "clue_filter_hash": 0,
                "jump_to_id": 0,
                "jump_to_type": 0,
                "entry_type": 0,
                "play_pre_entry": 1 if dest_play_pre_entry else 0,
                "destination_match_source_cue_name": 0,
            },
            "alloc_trans_object_flag": 0,
            "transition_object": {
                "segment_id": transition_segment,
                "fade_out": {"transition_time": 0, "curve": "Log3", "offset": 0},
                "fade_in": {"transition_time": 0, "curve": "Log3", "offset": 0},
                "play_pre_entry": 0,
                "play_post_exit": 0,
            },
        }
        self["music_trans_node_params/transition_rules"].append(rule)
        self["music_trans_node_params/transition_rule_count"] = len(
            self["music_trans_node_params/transition_rules"]
        )
