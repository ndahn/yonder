from yonder.types.base_types import PropBundle
from yonder.enums import PropID


# NOTE: mixed class must expose a "properties" member
class PropertyMixin:
    def get_property(self, property: PropID, default: float = None) -> float:
        """Get a property value by name.

        Parameters
        ----------
        property : PropID
            Property name (e.g., 'Volume', 'Pitch', 'LPF', 'HPF').
        default : float, optional
            Default value if property not found.

        Returns
        -------
        float
            Property value, or default if not found.
        """
        bundle: PropBundle
        for bundle in self.properties:
            if bundle.prop_id == property:
                return bundle.value
        
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
        bundle: PropBundle
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
        bundle: PropBundle
        for i, bundle in enumerate(self.properties):
            if bundle.prop_id == property:
                self.properties.pop(i)
                return True
        
        return False

    def clear_properties(self) -> None:
        """Remove all initial property values."""
        self.properties.clear()
