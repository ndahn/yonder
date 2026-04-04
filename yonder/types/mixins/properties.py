from yonder.types.rewwise_base_types import PropBundle
from yonder.types.rewwise_enums import PropID


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
        prop: PropBundle
        for prop in self.properties:
            if prop.prop_id == property:
                return prop.value
        
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
        prop: PropBundle
        for prop in self.properties:
            if prop.prop_id == property:
                prop[property] = value
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
        for i, prop_dict in enumerate(self.properties):
            if property in prop_dict:
                self.properties.pop(i)
                return True
        
        return False

    def clear_properties(self) -> None:
        """Remove all initial property values."""
        self.properties.clear()
