from typing import Any, Callable, Iterable, Type, TypeVar
from dearpygui import dearpygui as dpg
from yonder import Soundbank, HIRCNode


_T = TypeVar("_T", bound=Type[HIRCNode])


def select_nodes_dialog(
    get_items: Callable[[str], Iterable[HIRCNode]],
    on_nodes_selected: Callable[[str, list[HIRCNode] | list[str], Any], None],
    *,
    get_node_details: Callable[[HIRCNode], list[str]] = None,
    get_node_label: Callable[[HIRCNode], str] = None,
    multiple: bool = False,
    return_labels: bool = False,
    max_items: int = 200,
    title: str = "Select Node",
    tag: str = 0,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()
    elif dpg.does_item_exist(tag):
        dpg.delete_item(tag)

    items: dict[str, HIRCNode] = {}

    # Maps row_tag -> item key for lookup
    row_tags: dict[int, str] = {}
    selected_keys: set[str] = set()

    if not get_node_label:
        get_node_label = str

    def _set_row_highlight(row_tag: int, selected: bool) -> None:
        dpg.highlight_table_row(
            f"{tag}_table",
            list(row_tags.keys()).index(row_tag),
            (100, 149, 237, 80) if selected else (0, 0, 0, 0),
        )

    def _rebuild_table() -> None:
        row_tags.clear()
        selected_keys.clear()

        # Remove all existing rows
        for child in dpg.get_item_children(f"{tag}_table", slot=1) or []:
            dpg.delete_item(child)

        for key, node in items.items():
            with dpg.table_row(parent=f"{tag}_table") as row:
                row_tags[row] = key
                dpg.add_selectable(
                    label=key,
                    span_columns=True,
                    callback=_on_row_clicked,
                    user_data=row,
                )

            if get_node_details:
                details = get_node_details(node)
                if details:
                    with dpg.tooltip(dpg.last_item()):
                        for line in details:
                            dpg.add_text(line)

    def _on_row_clicked(sender: int, value: bool, row_tag: int) -> None:
        key = row_tags.get(row_tag)
        if key is None:
            return

        if multiple:
            if key in selected_keys:
                selected_keys.discard(key)
                dpg.set_value(sender, False)
            else:
                selected_keys.add(key)
                dpg.set_value(sender, True)
        else:
            # Deselect all others first
            for sibling in dpg.get_item_children(f"{tag}_table", slot=1):
                for sel in dpg.get_item_children(sibling, slot=1):
                    dpg.set_value(sel, False)

            selected_keys.clear()
            selected_keys.add(key)
            dpg.set_value(sender, True)

    def on_filter_changed(sender: int, filt: str, _user_data: Any) -> None:
        items.clear()
        items.update(
            {
                get_node_label(x): x
                for i, x in enumerate(get_items(filt))
                if i < max_items
            }
        )
        _rebuild_table()

    def on_okay() -> None:
        if not selected_keys:
            return

        if multiple:
            if return_labels:
                result = [k for k in selected_keys if k in items]
            else:
                result = [items[k] for k in selected_keys if k in items]
            on_nodes_selected(tag, result, user_data)
        else:
            key = next(iter(selected_keys), None)
            if return_labels:
                result = key
            else:
                result = items[key]
            on_nodes_selected(tag, result, user_data)

        dpg.delete_item(window)

    with dpg.window(
        label=title,
        width=350,
        height=450,
        autosize=True,
        no_saved_settings=True,
        tag=tag,
        on_close=lambda: dpg.delete_item(window),
    ) as window:
        dpg.add_input_text(
            callback=on_filter_changed,
            hint="Filter...",
            tag=f"{tag}_filter",
        )

        with dpg.table(
            tag=f"{tag}_table",
            header_row=False,
            scrollY=True,
            freeze_rows=1,
            height=300,
            policy=dpg.mvTable_SizingStretchProp,
        ):
            dpg.add_table_column(
                label="Node (id)",
                width_stretch=True,
            )

        if multiple:
            dpg.add_text(
                "Hold Ctrl or click multiple rows to select several nodes.",
                wrap=330,
                color=(180, 180, 180, 200),
            )

        dpg.add_separator()

        with dpg.group(horizontal=True):
            dpg.add_button(label="Okay", callback=on_okay, tag=f"{tag}_button_okay")
            dpg.add_button(
                label="Cancel",
                callback=lambda: dpg.delete_item(window),
            )

    on_filter_changed(f"{tag}_filter", "", None)
    return tag


def select_nodes_of_type(
    bnk: Soundbank,
    node_type: _T,
    on_node_selected: Callable[[str, list[_T] | list[str], Any], None],
    *,
    get_node_details: Callable[[HIRCNode], list[str]] = None,
    get_node_label: Callable[[HIRCNode], str] = str,
    multiple: bool = False,
    return_labels: bool = False,
    tag: str = 0,
    user_data: Any = None,
) -> str:
    candidates = list(bnk.query(f"type={node_type.__name__}"))

    def get_nodes(filt: str) -> list[_T]:
        if not filt:
            return candidates

        return [n for n in candidates if filt in str(n)]

    return select_nodes_dialog(
        get_nodes,
        on_node_selected,
        get_node_details=get_node_details,
        get_node_label=get_node_label,
        multiple=multiple,
        return_labels=return_labels,
        tag=tag,
        user_data=user_data,
    )
