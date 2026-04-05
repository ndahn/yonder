from typing import TYPE_CHECKING

from yonder.util import logger

if TYPE_CHECKING:
    from yonder import HIRCNode
    from yonder.types.rewwise_base_types import Children


# NOTE mixed class must expose "parent", "children", and "id" members
class ContainerMixin:
    def add_child(self, child_id: "int | HIRCNode") -> None:
        """Associates a child node for random or sequential playback.

        Parameters
        ----------
        child_id : int | HIRCNode
            Child node ID or Node instance.
        """
        from yonder.types import HIRCNode

        if isinstance(child_id, HIRCNode):
            if child_id.parent > 0 and child_id.parent != self.id:
                logger.warning(f"Adding already adopted child {child_id} to {self}")
                # TODO update child parent?

            child_id = child_id.id

        children: Children = self.children.items
        if child_id not in self.children:
            children.append(child_id)
            children.sort()
            self.children.count += 1

    def remove_child(self, child_id: "int | HIRCNode") -> bool:
        """Disassociates a child node from this container.

        Parameters
        ----------
        child_id : int | Node
            Child node ID or Node instance to remove.

        Returns
        -------
        bool
            True if child was removed, False if not found.
        """
        from yonder.types import HIRCNode
        
        if isinstance(child_id, HIRCNode):
            child_id = child_id.id

        children: Children = self.children.items
        if child_id in children:
            children.remove(child_id)
            self.children.count -= 1
            return True

        return False

    def clear_children(self) -> None:
        """Disassociates all children from this container."""
        children: Children = self.children.items
        children.items.clear()
        children.count = 0
