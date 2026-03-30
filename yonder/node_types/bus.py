from yonder.node import Node
from yonder.util import logger
from .mixins import RtpcMixin, StateChunkMixin


class Bus(RtpcMixin, StateChunkMixin, Node):
    """Audio bus for routing and mixing multiple sounds together.

    Buses serve as mixing points in the audio hierarchy, allowing shared processing (effects, ducking, HDR) and routing to output devices or parent buses. Supports voice ducking and real-time parameter control.
    """
    base_params_path = "initial_values"
    
    
    @classmethod
    def new(cls, nid: int, parent_bus_id: int | Node = 0) -> "Bus":
        """Create a new Bus node.

        Parameters
        ----------
        nid : int
            Node ID (hash).
        parent_bus_id : int | Node, default=0
            Parent bus ID (0 = master bus).

        Returns
        -------
        Bus
            New Bus instance.
        """
        temp = cls.load_template(cls.__name__)

        if isinstance(parent_bus_id, Node):
            parent_bus_id = parent_bus_id.id

        bus = cls(temp)
        bus.id = nid
        bus.override_bus_id = parent_bus_id
        logger.info(f"Created new node {bus}")
        return bus

    # Buses have a special set of prop_bundle different from WwiseNode
    @property
    def prop_bundle(self) -> list[dict]:
        """Bus property values.

        Returns
        -------
        list[dict]
            List of property dictionaries.
        """
        return self["initial_values/bus_initial_params/prop_bundle"]

    def get_property(self, prop_name: str, default: float = None) -> float:
        """Retrieves a specific bus property value.

        Parameters
        ----------
        prop_name : str
            Property name (e.g., 'CenterPCT', 'HDRBusThreshold').
        default : float, optional
            Default value if property not found.

        Returns
        -------
        float
            Property value, or default if not found.
        """
        for prop_dict in self.prop_bundle:
            if prop_name in prop_dict:
                return prop_dict[prop_name]
        return default

    def set_property(self, prop_name: str, value: float) -> None:
        """Configures a specific bus property value.

        If the property already exists, updates it. Otherwise, adds it.

        Parameters
        ----------
        prop_name : str
            Property name (e.g., 'CenterPCT', 'HDRBusThreshold').
        value : float
            Property value to set.
        """
        # Try to find and update existing property
        for prop_dict in self.prop_bundle:
            if prop_name in prop_dict:
                prop_dict[prop_name] = value
                return

        # Property doesn't exist, add it
        self.prop_bundle.append({prop_name: value})

    def remove_property(self, prop_name: str) -> bool:
        """Removes a specific property from the bus.

        Parameters
        ----------
        prop_name : str
            Property name to remove.

        Returns
        -------
        bool
            True if property was removed, False if not found.
        """
        prop_bundle = self.prop_bundle
        for i, prop_dict in enumerate(prop_bundle):
            if prop_name in prop_dict:
                prop_bundle.pop(i)
                return True
        return False

    def clear_properties(self) -> None:
        """Removes all property values from this bus."""
        self["initial_values/bus_initial_params/prop_bundle"] = []

    # Convenience properties for common bus parameters
    @property
    def center_pct(self) -> float:
        """Center percentage.

        CenterPCT controls speaker balance in surround sound setups, specifically how much audio goes to the center speaker vs. left/right speakers.

         - 100% - Full center speaker usage (dialogue typically uses this)
         - 50% - Balanced between center and L/R (default for many sounds)
         - 0% - No center speaker, audio spread to L/R only (music, ambience)

        This only matters for surround sound configurations; in stereo it has minimal/no effect.

        Returns
        -------
        float
            Center percentage (default 100.0 if not set).
        """
        return self.get_property("CenterPCT", 100.0)

    @center_pct.setter
    def center_pct(self, value: float) -> None:
        self.set_property("CenterPCT", value)

    @property
    def hdr_threshold(self) -> float:
        """HDR (High Dynamic Range Audio) bus threshold.

        Returns
        -------
        float
            HDR Loudness level (in dB) where compression starts.
        """
        return self.get_property("HDRBusThreshold", 0.0)

    @hdr_threshold.setter
    def hdr_threshold(self, value: float) -> None:
        self.set_property("HDRBusThreshold", value)

    @property
    def hdr_ratio(self) -> float:
        """HDR (High Dynamic Range Audio) bus ratio.

        Returns
        -------
        float
            How aggressively to compress (100 = 100:1 ratio, very aggressive).
        """
        return self.get_property("HDRBusRatio", 100.0)

    @hdr_ratio.setter
    def hdr_ratio(self, value: float) -> None:
        self.set_property("HDRBusRatio", value)

    @property
    def hdr_release_time(self) -> float:
        """HDR (High Dynamic Range Audio) bus release time.

        Returns
        -------
        float
            How quickly volume returns to normal after quieting down (ms).
        """
        return self.get_property("HDRBusReleaseTime", 0.0)

    @hdr_release_time.setter
    def hdr_release_time(self, value: float) -> None:
        self.set_property("HDRBusReleaseTime", value)

    @property
    def hdr_game_param_max(self) -> float:
        """HDR (High Dynamic Range Audio) game parameter maximum.

        Returns
        -------
        float
            Maximum value for game parameter control.
        """
        return self.get_property("HDRBusGameParamMax", 100.0)

    @hdr_game_param_max.setter
    def hdr_game_param_max(self, value: float) -> None:
        self.set_property("HDRBusGameParamMax", value)

    @property
    def override_bus_id(self) -> int:
        """Parent bus ID.

        Returns
        -------
        int
            Parent bus ID (0 = master bus).
        """
        return self["initial_values/override_bus_id"]

    @override_bus_id.setter
    def override_bus_id(self, value: int | Node) -> None:
        if isinstance(value, Node):
            value = value.id

        self["initial_values/override_bus_id"] = value

    @property
    def max_instances(self) -> int:
        """Maximum number of simultaneous instances.

        Returns
        -------
        int
            Maximum instance count (0 = unlimited).
        """
        return self["initial_values/bus_initial_params/max_instance_count"]

    @max_instances.setter
    def max_instances(self, value: int) -> None:
        self["initial_values/bus_initial_params/max_instance_count"] = value

    @property
    def channel_config(self) -> int:
        """Channel configuration.

        Returns
        -------
        int
            Channel configuration value.
        """
        return self["initial_values/bus_initial_params/channel_config"]

    @channel_config.setter
    def channel_config(self, value: int) -> None:
        self["initial_values/bus_initial_params/channel_config"] = value

    @property
    def recovery_time(self) -> int:
        """Ducking recovery time in milliseconds.

        Returns
        -------
        int
            Recovery time in ms after ducking ends.
        """
        return self["initial_values/recovery_time"]

    @recovery_time.setter
    def recovery_time(self, value: int) -> None:
        self["initial_values/recovery_time"] = value

    @property
    def max_duck_volume(self) -> float:
        """Maximum duck volume in dB.

        Returns
        -------
        float
            Maximum duck volume attenuation.
        """
        return self["initial_values/max_duck_volume"]

    @max_duck_volume.setter
    def max_duck_volume(self, value: float) -> None:
        self["initial_values/max_duck_volume"] = value

    @property
    def ducks(self) -> list[dict]:
        """Automatic volume reduction rules for other buses when this bus plays.

        Returns
        -------
        list[dict]
            List of duck dictionaries with target bus and fade times.
        """
        return self["initial_values/ducks"]

    def add_duck(
        self,
        target_bus_id: int | Node,
        duck_volume: float = -200.0,
        fade_out: int = 3000,
        fade_in: int = 500,
        fade_curve: str = "SCurve",
    ) -> None:
        """Configures automatic volume reduction of another bus when this bus plays.

        Parameters
        ----------
        target_bus_id : int | Node
            Bus ID to duck when this bus plays.
        duck_volume : float, default=-200.0
            Volume to duck to in dB.
        fade_out : int, default=3000
            Fade out time in milliseconds.
        fade_in : int, default=500
            Fade in time in milliseconds.
        fade_curve : str, default="SCurve"
            Fade curve type.
        """
        if isinstance(target_bus_id, Node):
            target_bus_id = target_bus_id.id

        duck = {
            "bus_id": target_bus_id,
            "duck_volume": duck_volume,
            "fade_out_time": fade_out,
            "fade_in_time": fade_in,
            "fade_curve": fade_curve,
            "target_prop": "BusVolume",
        }
        self["initial_values/ducks"].append(duck)
        self["initial_values/duck_count"] = len(self["initial_values/ducks"])

    def remove_duck(self, target_bus_id: int | Node) -> bool:
        """Removes ducking configuration for a specific target bus.

        Parameters
        ----------
        target_bus_id : int | Node
            Target bus ID to remove ducking for.

        Returns
        -------
        bool
            True if duck was removed, False if not found.
        """
        if isinstance(target_bus_id, Node):
            target_bus_id = target_bus_id.id

        ducks = self["initial_values/ducks"]
        for i, duck in enumerate(ducks):
            if duck["bus_id"] == target_bus_id:
                ducks.pop(i)
                self["initial_values/duck_count"] = len(ducks)
                return True
        return False

    def clear_ducks(self) -> None:
        """Removes all ducking configurations from this bus."""
        self["initial_values/ducks"] = []
        self["initial_values/duck_count"] = 0

    def get_aux_bus(self, index: int) -> int:
        """Retrieves an auxiliary send bus used for effects processing.

        Parameters
        ----------
        index : int
            Aux bus index (1-4).

        Returns
        -------
        int
            Aux bus ID.
        """
        if index < 1 or index > 4:
            raise ValueError("Aux index must be between 1 and 4")
        return self[f"initial_values/bus_initial_params/aux_params/aux{index}"]

    def set_aux_bus(self, index: int, bus_id: int | Node) -> None:
        """Configures an auxiliary send bus for effects processing.

        Parameters
        ----------
        index : int
            Aux bus index (1-4).
        bus_id : int | Node
            Aux bus ID to set.
        """
        if index < 1 or index > 4:
            raise ValueError("Aux index must be between 1 and 4")

        if isinstance(bus_id, Node):
            bus_id = bus_id.id

        self[f"initial_values/bus_initial_params/aux_params/aux{index}"] = bus_id

    def get_references(self) -> list[tuple[str, int]]:
        refs = super().get_references()

        paths = (
            "initial_values/override_bus_id",
            "initial_values/bus_initial_params/aux_params/aux1",
            "initial_values/bus_initial_params/aux_params/aux2",
            "initial_values/bus_initial_params/aux_params/aux3",
            "initial_values/bus_initial_params/aux_params/aux4",
        )        
        for p in paths:
            ref = self.get(p, 0)
            if ref > 0:
                refs.append((p, ref))


        return refs
