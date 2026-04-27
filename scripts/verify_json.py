import dataclasses
import logging
from typing import Any

from yonder import Soundbank


logger = logging.getLogger(__name__)


def _is_id_like(value: Any) -> bool:
    return isinstance(value, (int, float)) and value >= 10**9


def _scan_fields(
    node: Any,
    seen_ids: set,
    node_id: int | float,
) -> None:
    """Recursively scan dataclass fields for ID-like values and unsorted int/float lists."""
    if not dataclasses.is_dataclass(node) or isinstance(node, type):
        return

    for field in dataclasses.fields(node):
        value = getattr(node, field.name)
        _check_value(field.name, value, seen_ids, node_id)


def _check_value(
    field_name: str,
    value: Any,
    seen_ids: set,
    node_id: int | float,
) -> None:
    """Check a single value for ID references and unsorted arrays."""
    if _is_id_like(value):
        _validate_ref(field_name, value, seen_ids, node_id)

    elif isinstance(value, list) and field_name not in ("actions", "curves_to_use"):
        # Check if it's a list of ints/floats — validate sorting
        numeric = [v for v in value if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if len(numeric) == len(value) and len(value) > 1:
            if numeric != sorted(numeric):
                logger.error(
                    "Node %s: field '%s' contains unsorted numeric array: %s",
                    node_id, field_name, value,
                )
        else:
            # Mixed or non-numeric list — recurse into dataclass items
            for item in value:
                if dataclasses.is_dataclass(item) and not isinstance(item, type):
                    _scan_fields(item, seen_ids, node_id)
                elif _is_id_like(item):
                    _validate_ref(field_name, item, seen_ids, node_id)

    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        _scan_fields(value, seen_ids, node_id)


def _validate_ref(
    field_name: str,
    ref_value: int | float,
    seen_ids: set,
    node_id: int | float,
) -> None:
    """Apply forward/backward reference rules depending on field name."""

    # Exclude a bunch of fields that would log false positives
    if field_name in ("source_id", "override_bus_id", "bank_id", "Hash", "id", "ers_type", "key", "aux1", "aux2", "aux3", "aux4", "fx_id", "state_id", "group_id", "play_id", "playlist_item_id", "clue_filter_hash", "state_group_id", "event_id", "switch_state_id", "switch_group_id", "external_id"):
        return

    if field_name == "direct_parent_id":
        # Parent must come BEFORE this node — error if it already appeared
        if ref_value in seen_ids:
            logger.error(
                "Node %s: 'direct_parent_id' %s was already encountered (parent must precede child)",
                node_id, ref_value,
            )
    else:
        # All other ID references must point to already-seen objects
        if ref_value not in seen_ids:
            logger.error(
                "Node %s: field '%s' references unseen ID %s",
                node_id, field_name, ref_value,
            )


def verify_order(nodes: list[Any]) -> None:
    """
    Traverse a list of (possibly nested) dataclass nodes and log ordering errors:
      - duplicate IDs
      - direct_parent_id pointing to an already-seen node
      - any other ID-like reference to a not-yet-seen node
      - unsorted lists of id-like numbers
    """
    seen_ids: set = set()

    for node in nodes:
        node_id = node.id

        # Duplicate check before registering
        if node_id in seen_ids:
            logger.error("Duplicate node ID: %s", node_id)
        else:
            seen_ids.add(node_id)

        _scan_fields(node, seen_ids, node_id)


if __name__ == "__main__":
    bnk_path = "E:/Games/Elden Ring/Modding/Tools/yonder/test/mod/sd/cs_smain/soundbank.json"
    bnk = Soundbank.load(bnk_path)

    verify_order(bnk.hirc.objects)
