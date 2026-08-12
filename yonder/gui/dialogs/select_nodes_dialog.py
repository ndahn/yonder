from typing import Any, Callable, Iterable
import networkx as nx
from dearpygui import dearpygui as dpg

from yonder import HIRCNode, lookup_name
from yonder.types import ActorMixer
from yonder.game import get_selected_game
from yonder.game.data import AmxData
from yonder.gui.localization import µ
from yonder.gui.widgets import (
    DpgItem,
    add_table_tree_node,
    push_table_tree_level,
    pop_table_tree_level,
    get_foldable_row_descriptor,
)
from yonder.gui.icons import Icons


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
            get_node_label = lambda n: n.get_name(f"#{n.id}")

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

    def regenerate(self) -> None:
        self._row_tags.clear()
        self._selected_keys.clear()
        dpg.delete_item(self._t("table"), children_only=True, slot=1)

        for label, node in self._items.items():
            with dpg.table_row(parent=self._t("table")) as row:
                self._row_tags[row] = label
                dpg.add_selectable(
                    label=label,
                    span_columns=True,
                    callback=self._on_row_clicked,
                    user_data=row,
                )

            if self._get_node_details:
                details = self._get_node_details(node)
                if details:
                    with dpg.tooltip(dpg.last_item()):
                        for line in details:
                            if line.startswith("# "):
                                dpg.add_separator(label=line[2:])
                            else:
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
        self.regenerate()

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

            with dpg.child_window(
                autosize_x=True,
                auto_resize_y=True,
                border=False,
            ):
                with dpg.table(
                    tag=self._t("table"),
                    header_row=False,
                    scrollY=True,
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


class select_actormixer(select_nodes_dialog):
    def __init__(
        self,
        get_items: Callable[[str], Iterable[ActorMixer]],
        on_nodes_selected: Callable[[str, list[ActorMixer] | list[str], Any], None],
        *,
        multiple: bool = False,
        return_labels: bool = False,
        max_items: int = 200,
        title: str = "Select ActorMixer",
        tag: str = 0,
        user_data: Any = None,
    ) -> str:
        super().__init__(
            get_items,
            on_nodes_selected,
            get_node_details=None,
            get_node_label=None,
            multiple=multiple,
            return_labels=return_labels,
            max_items=max_items,
            title=title,
            tag=tag,
            user_data=user_data,
        )

    def _build(self, title: str) -> None:
        super()._build(title)
        dpg.add_table_column(
            label="Hints",
            width=80,
            width_fixed=True,
            no_resize=True,
            parent=self._t("table")
        )

    def regenerate(self) -> None:
        table_tag = self._t("table")

        self._row_tags.clear()
        self._selected_keys.clear()
        dpg.delete_item(table_tag, children_only=True, slot=1)

        summary = get_selected_game().amx_summary
        tree = summary.tree

        bank_map: dict[str, list[AmxData]] = {}
        for amx in summary.actormixers.values():
            if amx.bank:
                bank_map.setdefault(amx.bank, []).append(amx)

        def name(key: int) -> str:
            return lookup_name(key, f"#{key}")

        def make_row(label: str, amx_id: int, leaf: bool) -> None:
            callback = self._on_row_clicked if amx_id >= 0 else None

            row = add_table_tree_node(
                label,
                table=table_tag,
                leaf=leaf,
                span_columns=True,
                on_click_callback=callback,
                user_data=amx_id,
            )

            with dpg.group(horizontal=True, horizontal_spacing=0, parent=row.row):
                info = summary.actormixers.get(amx_id)

                if info:
                    if info.bus:
                        dpg.add_image(Icons.bus16)
                    else:
                        dpg.add_spacer(width=16)

                    if info.has_aux():
                        dpg.add_image(Icons.aux16)
                    else:
                        dpg.add_spacer(width=16)

                    if info.properties:
                        dpg.add_image(Icons.properties16)
                    else:
                        dpg.add_spacer(width=16)

                    if info.rtpcs:
                        dpg.add_image(Icons.rtpc16)
                    else:
                        dpg.add_spacer(width=16)

                    if info.states:
                        dpg.add_image(Icons.states16)
                    else:
                        dpg.add_spacer(width=16)

                dpg.add_spacer(width=3)

            if amx_id > 0:
                self._row_tags[amx_id] = label
                details = self._get_amx_details(amx_id)
                if details:
                    with dpg.tooltip(row.selectable):
                        for line in details:
                            if line.startswith("# "):
                                dpg.add_separator(label=line[2:])
                            else:
                                dpg.add_text(line)

        def descend_amx(amx_id: int, graph: nx.DiGraph) -> None:
            is_leaf = not bool(list(graph.successors(amx_id)))
            make_row(name(amx_id), amx_id, is_leaf)
            push_table_tree_level(table_tag)

            for child_id in graph.successors(amx_id):
                descend_amx(child_id, graph)

            pop_table_tree_level(table_tag)

        def place_bank_amx(bank: str, bank_amx: list[AmxData]) -> None:
            make_row(bank, 0, False)
            bank_graph = tree.subgraph([a.nid for a in bank_amx])
            roots = sorted(n for n in bank_graph if bank_graph.in_degree(n) == 0)

            push_table_tree_level(table_tag)

            for root_id in roots:
                descend_amx(root_id, bank_graph)

            pop_table_tree_level(table_tag)

        # TODO
        # Place the current bank first, then main, then the rest
        # current_bank_amx = bank_map.pop(self.bnk.name)
        # if current_bank_amx:
        #    place_bank_amx(self.bnk.name, current_bank_amx)

        for category, pattern in [
            (µ("Main"), "cs_main"),
            (µ("Hero"), "hero"),
            (µ("Character"), "cs_c"),
            (µ("Dialog"), "vc"),
            (µ("Map"), "cs_m"),
            (µ("Asset"), "aeg"),
            (µ("Cutscene"), ("cs_s", "s")),
            (µ("Other"), ""),
        ]:
            banks = sorted(b for b in bank_map if b.lower().startswith(pattern))
            if not banks:
                continue

            make_row(category, 0, False)
            push_table_tree_level(table_tag)

            for bnk in banks:
                place_bank_amx(bnk, bank_map[bnk])

            pop_table_tree_level(table_tag)
            bank_map = {k: v for k, v in bank_map.items() if k not in banks}

    def _get_amx_details(self, amx_id: int) -> list[str]:
        game_data = get_selected_game()

        # TODO need to expand the summary with the current bank's info
        root, info = game_data.amx_summary.get_effective_values(amx_id)

        if root <= 0:
            return ["<no data>"]

        def name(key: int) -> str:
            return lookup_name(key, f"#{key}")

        lines = []

        # TODO show bank the AMX is defined in, group amx by bank

        root_bus = game_data.amx_summary.actormixers[root].bus
        if root_bus != info.bus:
            lines.append(f"Bus: {name(info.bus)} ({name(root_bus)})")
        else:
            lines.append(f"Bus: {name(info.bus)}")

        if info.has_aux():
            for aux in info.aux1, info.aux2, info.aux3, info.aux4:
                if aux > 0:
                    lines.append(f"-> {name(aux)}")

        if info.properties:
            lines.append("# Properties")
            lines.extend([f"{p.name} = {v}" for p, v in info.properties.items()])

        if info.rtpcs:
            lines.append("# RTPCs")
            for rtpc, val in info.rtpcs.items():
                param = game_data.rtpc_params(val[1])
                lines.append(f"{name(rtpc)} -> {param.name}")

        if info.states:
            lines.append("# States")
            for group, states in info.states.items():
                lines.append(name(group))
                props = sorted({p for s in states.values() for p in s})
                for p in props:
                    lines.append(f"  {p.name}")

        return lines

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
            for row in dpg.get_item_children(self._t("table"), slot=1):
                descriptor = get_foldable_row_descriptor(row)
                dpg.set_value(descriptor.selectable, False)

            self._selected_keys.clear()
            self._selected_keys.add(key)
            dpg.set_value(sender, True)
