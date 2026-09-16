from random import random
from yonder.types.base_types import PropBundle, PropRangedModifier
from yonder.enums import PropID


# NOTE: mixed class must expose a "properties" member
class PropertyMixin:
    # Dummies, just for the type checker
    properties: list[PropBundle]
    # Busses don't have this one
    property_ranges: list[PropRangedModifier]

    def get_property(
        self, property: PropID, default: float = None, apply_randomization: bool = False
    ) -> float:
        """Get a property value by name.

        Parameters
        ----------
        property : PropID
            Property name (e.g., 'Volume', 'Pitch', 'LPF', 'HPF').
        default : float, optional
            Default value if property not found.
        apply_randomization : float, optional
            If True and this object supports and has a property range for the specified property, a random offset from the property range will be added to the returned value.

        Returns
        -------
        float
            Property value, or default if not found.
        """
        for bundle in self.properties:
            if bundle.prop_id == property:
                val = bundle.value

                if apply_randomization:
                    rmin, rmax = self.get_property_range(property)
                    val += rmin + random() * (rmax - rmin)

                return val

        return default

    def set_property(self, property: PropID, value: float) -> None:
        """Set a property value by name.

        If the property already exists, updates it. Otherwise, adds it.

        Parameters
        ----------
        property : PropID
            Property to set.
        value : float
            Property value to set.
        """
        for bundle in self.properties:
            if bundle.prop_id == property:
                bundle.value = value
                return

        self.properties.append(PropBundle(property, value))

    def remove_property(self, property: PropID) -> bool:
        """Remove a property by name.

        Parameters
        ----------
        property : PropID
            Property name to remove.

        Returns
        -------
        bool
            True if property was removed, False if not found.
        """
        for i, bundle in enumerate(self.properties):
            if bundle.prop_id == property:
                self.properties.pop(i)
                return True

        return False

    def clear_properties(self) -> None:
        """Remove all initial property values."""
        self.properties.clear()

    def can_randomize_properties(self) -> bool:
        return hasattr(self, "property_ranges")

    def get_property_range(self, prop: PropID) -> tuple[float, float]:
        if not self.can_randomize_properties():
            return (0, 0)

        for pr in self.property_ranges:
            if PropID(pr.prop_type) == prop:
                # Strangely enough this is allowed
                rmin = 0.0 if pr.min is None else pr.min
                rmax = 0.0 if pr.max is None else pr.max
                rmin = min(rmin, rmax)
                return (rmin, rmax)

        return (0, 0)

    def set_property_range(
        self, prop: PropID, rand_min: float = None, rand_max: float = None
    ) -> None:
        if not self.can_randomize_properties():
            raise RuntimeError(f"{self} does not supported property randomization")

        if rand_min is None and rand_max is None:
            for idx, pr in enumerate(self.property_ranges):
                if PropID(pr.prop_type) == prop:
                    del self.property_ranges[idx]
                    return

        # NOTE doesn't need a corresponding value in prop_initial_values
        for idx, pr in enumerate(self.property_ranges):
            if PropID(pr.prop_type) == prop:
                # Actually *can* be set to None
                pr.min = rand_min
                pr.max = rand_max
                break
        else:
            self.property_ranges.append(PropRangedModifier(prop, rand_min, rand_max))

    def clear_property_ranges(self) -> None:
        if self.can_randomize_properties():
            self.property_ranges.clear()
