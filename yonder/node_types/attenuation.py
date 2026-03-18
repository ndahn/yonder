from yonder.node import Node
from yonder.enums import ScalingType, CurveType
from yonder.util import logger
from .mixins import RtpcMixin


class Attenuation(RtpcMixin, Node):
    """Attenuation object defining distance-based audio falloff curves.

    Controls how sound volume, low-pass filter, high-pass filter, and spread change over distance. Also manages cone-based directional attenuation for focused sound sources.
    """
    base_params_path = ""

    curve_parameters: list[str] = [
        "Volume1",
        "LPF",
        "Volume2",
        "HPF",
        "Spread",
        "Focus",
        "(unused)",
    ]


    @classmethod
    def new(cls, nid: int) -> "Attenuation":
        """Create a new Attenuation node.

        Parameters
        ----------
        nid : int
            Node ID (hash).

        Returns
        -------
        Attenuation
            New Attenuation instance with default volume curve.
        """
        temp = cls.load_template(cls.__name__)
        attenuation = cls(temp)
        attenuation.id = nid
        logger.info(f"Created new node {attenuation}")
        return attenuation

    @property
    def is_cone_enabled(self) -> bool:
        """Controls whether directional attenuation based on sound source orientation is applied.

        Returns
        -------
        bool
            True if cone attenuation is enabled.
        """
        return bool(self["is_cone_enabled"])

    @is_cone_enabled.setter
    def is_cone_enabled(self, value: bool) -> None:
        self["is_cone_enabled"] = int(value)

    @property
    def cone_inside_degrees(self) -> float:
        """Cone inside angle in degrees.

        Returns
        -------
        float
            Inside cone angle in degrees.
        """
        return self["cone_params/inside_degrees"]

    @cone_inside_degrees.setter
    def cone_inside_degrees(self, value: float) -> None:
        self["cone_params/inside_degrees"] = value

    @property
    def cone_outside_degrees(self) -> float:
        """Cone outside angle in degrees.

        Returns
        -------
        float
            Outside cone angle in degrees.
        """
        return self["cone_params/outside_degrees"]

    @cone_outside_degrees.setter
    def cone_outside_degrees(self, value: float) -> None:
        self["cone_params/outside_degrees"] = value

    @property
    def cone_outside_volume(self) -> float:
        """Volume outside the cone.

        Returns
        -------
        float
            Volume attenuation outside cone.
        """
        return self["cone_params/outside_volume"]

    @cone_outside_volume.setter
    def cone_outside_volume(self, value: float) -> None:
        self["cone_params/outside_volume"] = value

    @property
    def curves(self) -> list[dict]:
        """Distance-based curves defining how audio properties change over space.

        Returns
        -------
        list[dict]
            List of curve dictionaries with scaling, points, and interpolation.
        """
        return self["curves"]

    @property
    def curves_to_use(self) -> list[int]:
        """Get or set which curves are active for each parameter type.
        
        This is a mapping array where each index corresponds to a parameter:
        - Index 0: Volume curve 1
        - Index 1: LPF (Low-Pass Filter)
        - Index 2: Volume curve 2
        - Index 3: HPF (High-Pass Filter)  
        - Index 4: Spread
        - Index 5: Focus
        - Index 6: (unused, typically -1)
        
        The value at each index is the curve index to use, or -1 if unused.
        
        Returns
        -------
        list[int]
            Array mapping parameter slots to curve indices (-1 = unused).
        """
        return self["curves_to_use"]
    
    def set_curve_for_parameter(self, param_index: int, curve_index: int) -> None:
        """Assign a curve to a specific parameter type.
        
        Parameters
        ----------
        param_index : int
            Parameter index (0=Volume1, 1=LPF, 2=Volume2, 3=HPF, 4=Spread, 5=Focus).
        curve_index : int
            Curve index to use, or -1 to disable.
        """
        curves_to_use = self["curves_to_use"]
        if param_index < 0 or param_index >= len(curves_to_use):
            raise IndexError(f"Parameter index {param_index} out of range")
        
        curves_to_use[param_index] = curve_index
 
    def add_curve(self, curve_scaling: ScalingType = "DB") -> dict:
        """Creates a new distance-based curve for controlling audio properties.

        Parameters
        ----------
        curve_scaling : CurveType, default="DB"
            Scaling type ('DB', 'None', 'Linear').

        Returns
        -------
        dict
            The newly created curve dictionary.
        """
        curve = {"curve_scaling": curve_scaling, "point_count": 0, "points": []}
        self["curves"].append(curve)
        self["curve_count"] = len(self["curves"])
        return curve

    def add_curve_point(
        self,
        curve_index: int,
        from_distance: float,
        to_value: float,
        interpolation: CurveType = "Linear",
    ) -> None:
        """Defines how an audio property changes at a specific distance.

        Parameters
        ----------
        curve_index : int
            Index of the curve to modify.
        from_distance : float
            Distance value (x-axis).
        to_value : float
            Output value (y-axis).
        interpolation : CurveType, default="Linear"
            Interpolation type.
        """
        if curve_index < 0 or curve_index >= self.curve_count:
            raise IndexError(f"Curve index {curve_index} out of range")

        point = {"from": from_distance, "to": to_value, "interpolation": interpolation}
        curve = self["curves"][curve_index]
        curve["points"].append(point)
        curve["point_count"] = len(curve["points"])

    def clear_curves(self) -> None:
        """Removes all distance-based curves from this attenuation."""
        self["curves"] = []
        self["curve_count"] = 0
