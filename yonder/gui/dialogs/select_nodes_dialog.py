from typing import Any, Callable, Iterable, Type, TypeVar
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.gui.localization import µ
from yonder.gui.widgets import DpgItem


_T = TypeVar("_T", bound=Type[HIRCNode])


class select_nodes_dialog(DpgItem):
    def __init__(
        self,
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
        super().__init__(tag)

        if not get_node_label:
            get_node_label = str

        self._items: dict[str, HIRCNode] = {}
        self._get_items = get_items
        self._on_nodes_selected = on_nodes_selected
        self._get_node_details = get_node_details
        self._get_node_label = get_node_label
        self._multiple = multiple
        self._return_labels = return_labels
        self._max_items = max_items
        self._user_data = user_data

        # Maps row_tag -> item key for lookup
        self._row_tags: dict[int, str] = {}
        self._selected_keys: set[str] = set()

        self._build(title)

    def _set_row_highlight(self, row_tag: int, selected: bool) -> None:
        dpg.highlight_table_row(
            self._t("table"),
            list(self._row_tags.keys()).index(row_tag),
            (100, 149, 237, 80) if selected else (0, 0, 0, 0),
        )

    def _rebuild_table(self) -> None:
        self._row_tags.clear()
        self._selected_keys.clear()

        # Remove all existing rows
        for child in dpg.get_item_children(self._t("table"), slot=1) or []:
            dpg.delete_item(child)

        for key, node in self._items.items():
            with dpg.table_row(parent=self._t("table")) as row:
                self._row_tags[row] = key
                dpg.add_selectable(
                    label=key,
                    span_columns=True,
                    callback=self._on_row_clicked,
                    user_data=row,
                )

            if self._get_node_details:
                details = self._get_node_details(node)
                if details:
                    with dpg.tooltip(dpg.last_item()):
                        for line in details:
                            dpg.add_text(line)

    def _on_row_clicked(self, sender: int, value: bool, row_tag: int) -> None:
        key = self._row_tags.get(row_tag)
        if key is None:
            return

        if self._multiple:
            if key in self._selected_keys:
                self._selected_keys.discard(key)
                dpg.set_value(sender, False)
            else:
                self._selected_keys.add(key)
                dpg.set_value(sender, True)
        else:
            # Deselect all others first
            for sibling in dpg.get_item_children(self._t("table"), slot=1):
                for sel in dpg.get_item_children(sibling, slot=1):
                    dpg.set_value(sel, False)

            self._selected_keys.clear()
            self._selected_keys.add(key)
            dpg.set_value(sender, True)

    def _invert_selection(self) -> None:
        for row in dpg.get_item_children(self._t("table"), slot=1):
            key = self._row_tags.get(row)
            selectable = next(iter(dpg.get_item_children(row, slot=1)), None)
            if selectable:
                if key in self._selected_keys:
                    dpg.set_value(selectable, False)
                    self._selected_keys.remove(key)
                else:
                    dpg.set_value(selectable, True)
                    self._selected_keys.add(key)

    def _on_filter_changed(self, sender: int, filt: str, cb_user_data: Any) -> None:
        self._items.clear()
        self._items.update(
            {
                self._get_node_label(x): x
                for i, x in enumerate(self._get_items(filt))
                if i < self._max_items
            }
        )
        self._rebuild_table()

    def _on_okay(self) -> None:
        if not self._selected_keys:
            return

        if self._multiple:
            if self._return_labels:
                result = [k for k in self._selected_keys if k in self._items]
            else:
                result = [
                    self._items[k] for k in self._selected_keys if k in self._items
                ]
            self._on_nodes_selected(self.tag, result, self._user_data)
        else:
            key = next(iter(self._selected_keys), None)
            if self._return_labels:
                result = key
            else:
                result = self._items[key]
            self._on_nodes_selected(self.tag, result, self._user_data)

        dpg.delete_item(self.tag)

    def _build(self, title: str):
        with dpg.window(
            label=title,
            width=350,
            height=450,
            autosize=True,
            no_saved_settings=True,
            tag=self.tag,
            on_close=lambda: dpg.delete_item(window),
        ) as window:
            dpg.add_input_text(
                callback=self._on_filter_changed,
                hint="Filter...",
                tag=self._t("filter"),
            )

            with dpg.table(
                tag=self._t("table"),
                header_row=False,
                scrollY=True,
                freeze_rows=1,
                height=300,
                policy=dpg.mvTable_SizingStretchProp,
            ):
                dpg.add_table_column(
                    label=µ("Node (id)"),
                    width_stretch=True,
                )

            if self._multiple:
                dpg.add_text(
                    µ("Hold Ctrl or click multiple rows to select several nodes."),
                    wrap=330,
                    color=(180, 180, 180, 200),
                )

            dpg.add_separator()

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Okay", "button"),
                    callback=self._on_okay,
                    tag=self._t("button_okay"),
                )
                if self._multiple:
                    dpg.add_button(
                        label=µ("Invert", "button"),
                        callback=self._invert_selection,
                        tag=self._t("button_invert"),
                    )

        self._on_filter_changed(self._t("filter"), "", None)


class select_nodes_of_type(DpgItem):
    def __init__(
        self,
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
        super().__init__(tag)

        self._candidates = list(bnk.query(f"type={node_type.__name__}"))
        self._dialog = select_nodes_dialog(
            self._get_nodes,
            on_node_selected,
            get_node_details=get_node_details,
            get_node_label=get_node_label,
            multiple=multiple,
            return_labels=return_labels,
            tag=tag,
            user_data=user_data,
        )

    def _get_nodes(self, filt: str) -> list[_T]:
        if not filt:
            return self._candidates

        return [n for n in self._candidates if filt in str(n)]
