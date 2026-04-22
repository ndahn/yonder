from typing import Generator, Callable, Any
from contextlib import contextmanager
from dataclasses import dataclass
import dearpygui.dearpygui as dpg


INDENT_STEP = 14  # actually depends on font size


@dataclass
class RowDescriptor:
    level: int
    row: str = None
    table: str = None
    selectable: str = None
    button: str = None
    is_lazy: bool = False
    on_fold_cb: Callable[[str, bool, Any], None] = None
    on_click_cb: Callable[[str, bool, Any], None] = None
    user_data: Any = None


def get_foldable_row_descriptor(row: str) -> RowDescriptor:
    if not dpg.does_item_exist(row):
        return None
    data = dpg.get_item_user_data(row)
    return data if isinstance(data, RowDescriptor) else None


def is_foldable_row(row: str) -> bool:
    return get_foldable_row_descriptor(row) is not None


def is_foldable_row_leaf(row: str) -> bool:
    desc = get_foldable_row_descriptor(row)
    return desc is not None and desc.button is None


def is_lazy_foldable(row: str) -> bool:
    desc = get_foldable_row_descriptor(row)
    return desc is not None and desc.is_lazy


def is_foldable_row_expanded(row: str) -> bool:
    desc = get_foldable_row_descriptor(row)
    return (
        desc is not None
        and desc.button is not None
        and dpg.get_item_label(desc.button) == "-"
    )


def get_row_level(row: str, default: int = 0) -> int:
    desc = get_foldable_row_descriptor(row)
    return desc.level if desc else default


def is_row_index_visible(table, row_level: int, row_idx: int = -1) -> bool:
    rows = dpg.get_item_children(table, slot=1)
    if row_idx >= 0:
        rows = rows[:row_idx]

    for parent in reversed(rows):
        desc = get_foldable_row_descriptor(parent)
        if not desc:
            return True

        if desc.level < row_level:
            return is_foldable_row_expanded(parent)

    return True


def is_row_visible(table: str, row: str | int) -> bool:
    if not is_foldable_row(row):
        return True

    desc = get_foldable_row_descriptor(row)
    rows = dpg.get_item_children(table, slot=1)
    row_idx = rows.index(row)
    return is_row_index_visible(table, desc.level, row_idx)


def get_foldable_child_rows(table: str, row: str) -> Generator[str, None, None]:
    if row in (None, "", 0):
        return

    if isinstance(row, str):
        row = dpg.get_alias_id(row)

    rows = dpg.get_item_children(table, slot=1)
    row_idx = rows.index(row)

    if row_idx >= 0:
        rows = rows[row_idx + 1 :]

    for child_row in rows:
        if not is_foldable_row(child_row):
            break

        yield child_row


def get_foldable_row_parent(table: str, row: str) -> int:
    if isinstance(row, str):
        row = dpg.get_alias_id(row)

    rows = dpg.get_item_children(table, slot=1)
    row_idx = rows.index(row)

    if row_idx > 0:
        rows = rows[:row_idx]

    for parent in reversed(list(rows)):
        if is_foldable_row(parent):
            return parent

    return None


def get_next_foldable_row_sibling(table: str, row: str) -> int:
    if isinstance(row, str):
        row = dpg.get_alias_id(row)

    row_level = get_row_level(row)
    rows = dpg.get_item_children(table, slot=1)
    row_idx = rows.index(row)

    if row_idx >= 0:
        rows = rows[row_idx + 1 :]

    for child_row in rows:
        if get_row_level(child_row) <= row_level:
            return child_row

    return 0


def get_row_indent(table: str, row: str) -> int:
    parent = get_foldable_row_parent(table, row)
    if not parent:
        return 0

    return get_row_level(parent) * INDENT_STEP


@contextmanager
def apply_row_indent(
    table: str,
    indent_level: int,
    parent_row: str,
    until: str = 0,
) -> Generator[str, None, None]:
    try:
        yield
    finally:
        children = get_foldable_child_rows(table, parent_row)

        if isinstance(until, str):
            until = dpg.get_alias_id(until)

        for child_row in children:
            if until != 0 and child_row == until:
                break

            desc = get_foldable_row_descriptor(child_row)
            if desc:
                child_level = desc.level + indent_level
                desc.level = child_level
            else:
                child_level = indent_level

            child_row_content = dpg.get_item_children(child_row, slot=1)
            if child_row_content:
                dpg.set_item_indent(child_row_content[0], child_level * INDENT_STEP)


def set_foldable_row_status(row: str, expanded: bool) -> None:
    if not is_foldable_row(row) or is_foldable_row_leaf(row):
        return

    if is_foldable_row_expanded(row) == expanded:
        return

    desc = get_foldable_row_descriptor(row)
    if not desc:
        return

    if desc.is_lazy:
        expanded = not expanded
        dpg.set_item_label(desc.button, "-" if expanded else "+")
        _on_lazy_node_clicked(row, expanded, desc)
    else:
        dpg.set_item_label(desc.button, "-" if not expanded else "+")
        _on_row_clicked(desc.button, expanded, desc)


@contextmanager
def table_tree_node(
    label: str,
    *,
    table: str = None,
    folded: bool = True,
    tag: str = 0,
    before: str = 0,
    on_click_callback: Callable[[str, bool, Any], None] = None,
    on_fold_callback: Callable[[str, bool, RowDescriptor], None] = None,
    user_data: Any = None,
) -> Generator[RowDescriptor, None, None]:
    if not table:
        table = dpg.top_container_stack()

    if tag in (0, "", None):
        tag = dpg.generate_uuid()

    cur_level = dpg.get_item_user_data(table) or 0
    button = f"{tag}_foldable_row_button"
    selectable = f"{tag}_foldable_row_selectable"
    show = is_row_index_visible(table, cur_level)

    descriptor = RowDescriptor(
        level=cur_level,
        row=tag,
        table=table,
        button=button,
        selectable=selectable,
        on_fold_cb=on_fold_callback,
        on_click_cb=on_click_callback,
        user_data=user_data,
    )

    with dpg.table_row(
        parent=table,
        tag=tag,
        before=before,
        user_data=descriptor,
        show=show,
    ):
        with dpg.group(horizontal=True, indent=cur_level * INDENT_STEP):
            dpg.add_button(
                label="+" if folded else "-",
                small=True,
                callback=_on_row_clicked,
                user_data=descriptor,
                tag=button,
            )
            dpg.add_selectable(
                label=label,
                callback=on_click_callback,
                tag=selectable,
                user_data=user_data,
            )
    try:
        dpg.set_item_user_data(table, cur_level + 1)
        yield descriptor
    finally:
        dpg.set_item_user_data(table, cur_level)
        set_foldable_row_status(tag, not folded)


@contextmanager
def table_tree_leaf(
    table: str = None,
    tag: str = 0,
    before: str = 0,
) -> Generator[RowDescriptor, None, None]:
    if not table:
        table = dpg.top_container_stack()

    if tag in (0, "", None):
        tag = dpg.generate_uuid()

    cur_level = dpg.get_item_user_data(table) or 0
    row = f"{tag}_foldable_row"
    show = is_row_index_visible(table, cur_level)

    descriptor = RowDescriptor(level=cur_level, row=row, table=table)

    try:
        with dpg.table_row(
            parent=table,
            tag=tag,
            before=before,
            user_data=descriptor,
            show=show,
        ):
            yield descriptor
    finally:
        children = dpg.get_item_children(row, slot=1)
        if children:
            dpg.set_item_indent(children[0], cur_level * INDENT_STEP)


def add_lazy_table_tree_node(
    label: str,
    content_callback: Callable[[str, str, Any], None],
    *,
    on_click_callback: Callable[[str, bool, Any], None] = None,
    table: str = None,
    tag: str = 0,
    before: str = 0,
    user_data: Any,
) -> RowDescriptor:
    if not table:
        table = dpg.top_container_stack()

    if tag in (0, "", None):
        tag = dpg.generate_uuid()

    cur_level = dpg.get_item_user_data(table) or 0
    button = f"{tag}_foldable_row_button"
    selectable = f"{tag}_foldable_row_selectable"
    show = is_row_index_visible(table, cur_level)

    descriptor = RowDescriptor(
        level=cur_level,
        row=tag,
        table=table,
        button=button,
        selectable=selectable,
        is_lazy=True,
        on_fold_cb=content_callback,
        user_data=user_data,
    )

    with dpg.table_row(
        parent=table,
        tag=tag,
        before=before,
        user_data=descriptor,
        show=show,
    ):
        with dpg.group(horizontal=True, indent=cur_level * INDENT_STEP):
            dpg.add_button(
                label="+",
                small=True,
                callback=_on_lazy_node_clicked,
                user_data=descriptor,
                tag=button,
            )
            dpg.add_selectable(
                label=label,
                callback=on_click_callback,
                tag=selectable,
                user_data=user_data,
            )

    return descriptor


def _on_row_clicked(sender: str, value: Any, desc: RowDescriptor):
    # Make sure it happens quickly and without flickering
    with dpg.mutex():
        row = desc.row
        table = desc.table
        is_leaf = desc.button is None
        is_expanded = not is_foldable_row_expanded(row)

        # Toggle the node's "expanded" status
        if not is_leaf:
            dpg.set_item_label(desc.button, "-" if is_expanded else "+")

        # Call user callback for regular nodes
        if desc.on_fold_cb:
            desc.on_fold_cb(row, is_leaf or is_expanded, desc.user_data)

        if is_leaf:
            return

        # All children *beyond* this level (but not on this level) will be hidden
        hide_level = 10000 if is_expanded else desc.level

        for child_row in get_foldable_child_rows(table, row):
            child_desc = get_foldable_row_descriptor(child_row)
            if not child_desc:
                # Not a foldable row, stop here
                break

            if child_desc.level <= desc.level:
                # This sibling is on the same or higher level, so no more children
                break

            if child_desc.level > hide_level:
                # Child is too far away, hide it
                dpg.hide_item(child_row)
            else:
                # Child is close to one of its siblings, show it
                dpg.show_item(child_row)
                hide_level = (
                    10000 if is_foldable_row_expanded(child_row) else child_desc.level
                )


def _on_lazy_node_clicked(sender: str, app_data: Any, desc: RowDescriptor):
    row = desc.row
    table = desc.table
    anchor = get_next_foldable_row_sibling(table, row)
    indent_level = desc.level + 1
    folded = not is_foldable_row_expanded(row)

    dpg.set_item_label(desc.button, "-" if folded else "+")

    if folded:
        with apply_row_indent(table, indent_level, row, until=anchor):
            desc.on_fold_cb(sender, anchor, desc.user_data)
    else:
        child_rows = list(get_foldable_child_rows(table, row))

        until = anchor
        if isinstance(until, str):
            until = dpg.get_alias_id(anchor)

        for child_row in child_rows:
            if until != 0 and child_row == until:
                break

            dpg.delete_item(child_row)
