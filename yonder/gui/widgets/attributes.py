from typing import Any, Callable, get_args
from collections import deque
from pathlib import Path
from docstring_parser import parse as doc_parse
import shutil
from dearpygui import dearpygui as dpg

from yonder import Soundbank, Node
from yonder.hash import lookup_name
from yonder.node_types import (
    Action,
    ActorMixer,
    Attenuation,
    Bus,
    Event,
    LayerContainer,
    MusicRandomSequenceContainer,
    MusicSegment,
    MusicSwitchContainer,
    MusicTrack,
    RandomSequenceContainer,
    Sound,
    SwitchContainer,
    WwiseNode,
)
from yonder.util import logger
from yonder.datatypes import GraphPoint, GraphCurve
from yonder.enums import SourceType, ScalingType, ClipType
from yonder.wem import wav2wem, create_prefetch_snippet
from yonder.gui import style
from yonder.gui.config import get_config
from .paragraphs import add_paragraphs
from .generic_input_widget import add_generic_widget
from .loading_indicator import loading_indicator
from .properties_table import add_properties_table
from .wav_player import add_wav_player
from .transition_matrix import add_transition_matrix
from .editable_table import add_widget_table, add_curves_table
from .hash_widget import add_hash_widget


def create_attribute_widgets(
    bnk: Soundbank,
    node: Node,
    on_node_changed: Callable[[str, Node, Any], None],
    on_node_selected: Callable[[str, Node, Any], None],
    *,
    tag: str = 0,
    parent: str = 0,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    def update_node_hash(
        sender: str, new_name: tuple[int, str], user_data: Any
    ) -> None:
        nid, name = new_name

        if name:
            node.name = name
        else:
            node.id = nid

    def on_node_properties_changed(
        sender: str, new_props: dict[str, float], node: WwiseNode
    ) -> None:
        for key in list(node.properties.keys()):
            if key not in new_props:
                node.remove_property(key)

        for key, val in new_props.items():
            node.set_property(key, val)

        on_node_changed(tag, node, user_data)

    def set_property(sender: str, new_value: Any, prop: property):
        prop.fset(node, new_value)
        on_node_changed(tag, node, user_data)

    loading = loading_indicator("loading...")
    try:
        with dpg.group(tag=tag, parent=parent):
            # Heading
            dpg.add_text(node.type)
            if node.__class__.__doc__:
                with dpg.tooltip(dpg.last_item()):
                    add_paragraphs(node.__class__.__doc__)

            add_hash_widget(
                node.id,
                update_node_hash,
                allow_edit_hash=False,
                allow_edit_name=False,
                width=-300,
                tag=f"{tag}_hash",
            )

            dpg.add_spacer(height=3)
            dpg.add_separator()
            dpg.add_spacer(height=3)

            # Find all exposed python properties, including those from base classes
            properties: dict[str, property] = {}
            todo = deque([node.__class__])
            while todo:
                c = todo.popleft()
                for name, prop in c.__dict__.items():
                    if name in ("id", "name", "type", "parent"):
                        continue
                    if isinstance(prop, property):
                        properties.setdefault(name, prop)

                todo.extend(c.__bases__)

            # This may remove or add properties that are handled differently
            try:
                _create_type_specific_attributes(
                    bnk,
                    node,
                    properties,
                    on_node_changed,
                    on_node_selected,
                    base_tag=tag,
                    user_data=user_data,
                )
            except Exception as e:
                logger.error(f"Error creating node widgets: {e}", exc_info=e)
                dpg.add_text("Error creating node widgets, check logs", color=style.red)

            # TODO should be deliberate about each node
            for name, prop in properties.items():
                value_type = prop.fget.__annotations__["return"]
                value = prop.fget(node)
                readonly = prop.fset is None
                doc = doc_parse(prop.__doc__)

                try:
                    widget = add_generic_widget(
                        value_type,
                        name,
                        set_property,
                        default=value,
                        readonly=readonly,
                        user_data=prop,
                    )
                except Exception:
                    continue

                if widget and doc:
                    with dpg.tooltip(dpg.last_item()):
                        dpg.add_text(doc.short_description)

            if isinstance(node, WwiseNode):
                dpg.add_spacer(height=5)
                add_properties_table(
                    node.properties,
                    on_node_properties_changed,
                    user_data=node,
                )
    finally:
        dpg.delete_item(loading)

    return tag


def add_node_link(
    node: Node,
    on_node_selected: Callable[[str, Node, Any], None],
    *,
    tag: str = 0,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    dpg.add_button(
        label=str(node),
        small=True,
        callback=lambda s, a, u: on_node_selected(tag, u, user_data),
        user_data=node,
        tag=tag,
    )
    dpg.bind_item_theme(dpg.last_item(), style.themes.link_button)
    return tag


def get_sound_path(bnk: Soundbank, source: dict) -> Path:
    source_id = source["media_information"]["source_id"]
    source_type = source["source_type"]

    wem = bnk.bnk_dir / f"{source_id}.wem"
    if source_type != "PrefetchStreaming" and wem.is_file():
        return wem

    # Find the largest external wem (if any)
    ext_wem = max(
        get_config().find_external_sounds(source_id, bnk),
        key=lambda p: p.stat().st_size,
        default=None,
    )
    if ext_wem:
        return ext_wem

    # In case we have a prefetch snippet but no streaming sound
    if wem.is_file() and source_type == "PrefetchStreaming":
        logger.warning(
            f"Could not find streamed sound for {source_id}, playing prefetch snippet"
        )
        return wem

    return None


def copy_wems_dialog(bnk: Soundbank, wav: Path, wem: Path, source_type: SourceType):
    def copy_wems() -> None:
        if source_type == "Embedded":
            target = bnk.bnk_dir / wem.name
            if target.is_file():
                target.unlink()
            shutil.copy(wem, target)

        elif source_type in ("Streaming", "PrefetchStreaming"):
            target = bnk.bnk_dir.parent / wem / f"{wem.stem[:2]}" / wem.name
            if target.is_file():
                target.unlink()
            shutil.copy(wem, target)

            if source_type == "PrefetchStreaming":
                wwise = get_config().locate_wwise()
                snippet = create_prefetch_snippet(wav)
                wem_snippet = wav2wem(wwise, snippet, out_dir=bnk.bnk_dir)[0]
                logger.info(f"Placed prefetch snippet in {wem_snippet}")

        else:
            raise ValueError(f"Unknown source_type {source_type}")

        logger.info(f"Copied {wem.name} to {target}")
        dpg.delete_item(dialog)

    with dpg.window(
        label="Copy?",
        modal=True,
        no_saved_settings=True,
        autosize=True,
        on_close=lambda: dpg.delete_item(dialog),
    ) as dialog:
        dpg.add_text(f"Copy WEMs to soundbank {bnk.name}?")
        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Yes",
                callback=copy_wems,
            )
            dpg.add_button(
                label="No",
                callback=lambda: dpg.delete_item(dialog),
            )


def _create_type_specific_attributes(
    bnk: Soundbank,
    node: Node,
    properties: dict[str, property],
    on_node_changed: Callable[[str, Node, Any], None],
    on_node_selected: Callable[[str, Node, Any], None],
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> None:
    if isinstance(node, Action):
        pass
    elif isinstance(node, ActorMixer):
        pass
    elif isinstance(node, Attenuation):
        _create_attributes_attenuation(
            bnk,
            node,
            properties,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
    elif isinstance(node, Bus):
        pass
    elif isinstance(node, Event):
        pass
    elif isinstance(node, LayerContainer):
        pass
    elif isinstance(node, MusicRandomSequenceContainer):
        _create_attributes_music_random_sequence_container(
            bnk,
            node,
            properties,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
    elif isinstance(node, MusicSegment):
        _create_attributes_music_segment(
            bnk,
            node,
            properties,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
    elif isinstance(node, MusicSwitchContainer):
        _create_attributes_music_switch_container(
            bnk,
            node,
            properties,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
    elif isinstance(node, MusicTrack):
        _create_attributes_music_track(
            bnk,
            node,
            properties,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
    elif isinstance(node, RandomSequenceContainer):
        pass
    elif isinstance(node, Sound):
        _create_attributes_sound(
            bnk,
            node,
            properties,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
    elif isinstance(node, SwitchContainer):
        _create_attributes_switch_container(
            bnk,
            node,
            properties,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )


def _create_attributes_attenuation(
    bnk: Soundbank,
    node: Attenuation,
    properties: dict[str, property],
    on_node_changed: Callable[[str, Node, Any], None],
    on_node_selected: Callable[[str, Node, Any], None],
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> None:
    def on_curves_changed(
        sender: str, curves: list[GraphCurve], cb_user_data: Any
    ) -> None:
        if len(curves) < len(node.curves):
            logger.warning("Don't forget to update the parameter curve indices!")

        node.curves.clear()
        for curve in curves:
            node.add_curve(curve.curve_type, curve)

        if on_node_changed:
            on_node_changed(base_tag, node, user_data)

    def on_curve_param_changed(sender: str, curve_idx: int, param_idx: int) -> None:
        node.set_curve_for_parameter(param_idx, curve_idx)

        if on_node_changed:
            on_node_changed(base_tag, node, user_data)

    with dpg.group():
        dpg.add_text("Curves to use")
        for i, (param, curve) in enumerate(
            zip(node.curve_parameters, node.curves_to_use)
        ):
            with dpg.group(horizontal=True):
                dpg.add_input_int(
                    default_value=curve,
                    label=param,
                    min_value=-1,
                    min_clamped=True,
                    max_value=len(node.curves),
                    max_clamped=True,
                    callback=on_curve_param_changed,
                    user_data=i,
                    tag=f"{base_tag}_curve_param_{i}",
                )

        dpg.add_spacer(height=5)
        add_curves_table(
            [
                GraphCurve.from_wwise(curve["curve_scaling"], curve["points"])
                for curve in node.curves
            ],
            get_args(ScalingType),
            on_curves_changed,
            curve_type_label="Scaling Type",
        )


def _create_attributes_music_random_sequence_container(
    bnk: Soundbank,
    node: MusicRandomSequenceContainer,
    properties: dict[str, property],
    on_node_changed: Callable[[str, Node, Any], None],
    on_node_selected: Callable[[str, Node, Any], None],
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> None:
    with dpg.group():
        add_transition_matrix(bnk, node, None, user_data=user_data)

        dpg.add_spacer(height=3)
        dpg.add_separator()
        dpg.add_spacer(height=3)


def _create_attributes_music_switch_container(
    bnk: Soundbank,
    node: MusicSwitchContainer,
    properties: dict[str, property],
    on_node_changed: Callable[[str, Node, Any], None],
    on_node_selected: Callable[[str, Node, Any], None],
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> None:
    from yonder.gui.dialogs.create_state_path_dialog import create_state_path_dialog

    properties.pop("arguments")
    properties.pop("tree_depth")

    args = node.arguments
    names = {a: lookup_name(a, f"#{a}") for a in node.arguments}

    def on_state_path_created(
        sender: str, state_path: list[int], path_node_id: int
    ) -> None:
        node.add_branch(state_path, path_node_id)
        # Regenerate
        on_node_selected(base_tag, node, user_data)

    def open_context_menu(sender: str, app_data: Any, info: tuple[str, Any]) -> None:
        item, user_data = info
        # TODO allow to edit state values and leaf nodes

    def register_context_menu(tag: str, user_data: Any) -> None:
        registry = f"{tag}_handlers"

        if not dpg.does_item_exist(registry):
            dpg.add_item_handler_registry(tag=registry)

        dpg.add_item_clicked_handler(
            dpg.mvMouseButton_Right,
            callback=open_context_menu,
            user_data=(tag, user_data),
            parent=registry,
        )
        dpg.bind_item_handler_registry(tag, registry)

    def get_key(tree_node: dict) -> str:
        val = tree_node["key"]
        if val == 0:
            return "*"
        return lookup_name(val, f"#{val}")

    def delve(tree_node: dict, level: int) -> None:
        if level == len(args) - 1:
            # Leaf
            nid = tree_node["node_id"]
            leaf_node = bnk.get(nid)

            arg = args[level]
            arg_name = names[arg]
            val_name = get_key(tree_node)

            with dpg.tree_node(label=f"{arg_name} = {val_name}"):
                # TODO should be an input field
                if leaf_node:
                    add_node_link(leaf_node, on_node_selected, user_data=user_data)
                elif nid == 0:
                    dpg.add_text("<None>")
                else:
                    dpg.add_text(f"(ext) {nid}")
        else:
            # Branch
            arg = args[level]
            arg_name = names[arg]
            val_name = get_key(tree_node)

            # TODO add context menu
            with dpg.tree_node(label=f"{arg_name} = {val_name}"):
                for child in tree_node["children"]:
                    delve(child, level + 1)

    with dpg.group():
        with dpg.tree_node(label="Decision Tree", default_open=True):
            for child in node.decision_tree["children"]:
                delve(child, 0)

        dpg.add_spacer(height=3)
        dpg.add_button(
            label="Add State Path",
            callback=lambda: create_state_path_dialog(
                bnk, node, on_state_path_created, raw=True
            ),
        )

        dpg.add_spacer(height=3)
        add_transition_matrix(bnk, node, None)

        dpg.add_spacer(height=3)
        dpg.add_separator()
        dpg.add_spacer(height=3)


def _create_attributes_music_segment(
    bnk: Soundbank,
    node: MusicSegment,
    properties: dict[str, property],
    on_node_changed: Callable[[str, Node, Any], None],
    on_node_selected: Callable[[str, Node, Any], None],
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> None:
    from yonder.gui.dialogs.edit_markers_dialog import edit_markers_dialog

    def on_marker_renamed(
        sender: str, new_name: tuple[int, str], info: tuple[int, int]
    ) -> None:
        idx, _ = info
        mid, name = new_name
        pos = node.markers[idx]["position"]
        node.markers.pop(idx)
        node.set_marker(name or mid, pos)
        on_node_changed(base_tag, node, user_data)

    def on_marker_moved(sender: str, new_pos: float, info: tuple[int, int]) -> None:
        _, mid = info
        node.set_marker(mid, new_pos)
        on_node_changed(base_tag, node, user_data)

    def on_marker_added(
        sender: str, info: tuple[int, list[dict], list[dict]], cb_user_data: Any
    ) -> None:
        marker = info[1][0]
        node.set_marker(marker["id"], marker["position"])
        on_node_changed(base_tag, node, user_data)

    def on_marker_removed(
        sender: str, info: tuple[int, dict, list[dict]], cb_user_data: Any
    ) -> None:
        marker = info[1]
        node.remove_marker(marker["id"])
        on_node_changed(base_tag, node, user_data)

    def new_marker() -> dict:
        mid = node.set_marker(f"m{len(node.markers)}", 0.0)
        return [node.get_marker(mid)]

    def create_row(marker: dict, idx: int) -> None:
        with dpg.group(horizontal=True):
            add_hash_widget(
                marker["id"],
                on_marker_renamed,
                initial_string=marker["string"],
                width=200,
                hash_label=None,
                user_data=(idx, marker["id"]),
            )
            dpg.add_input_float(
                default_value=marker["position"],
                min_value=0.0,
                min_clamped=True,
                callback=on_marker_moved,
                user_data=(idx, marker["id"]),
                width=-1,
            )

    def edit_markers_on_track() -> None:
        track: MusicTrack = bnk[int(dpg.get_value(f"{base_tag}_child_tracks"))]
        if not track.sources:
            logger.warning(f"{track} has no sources")
            return

        if track.sources[0]["source_type"] == "Embedded":
            path = track.get_source_path(bnk, 0)
        else:
            path = get_sound_path(bnk, track.sources[0])

        edit_markers_dialog(
            path,
            node.get_marker(MusicSegment.loop_start_id, 1.0),
            node.get_marker(MusicSegment.loop_end_id, -1.0),
            on_loop_changed,
        )

    def on_loop_changed(
        sender: str, loop_info: tuple[float, float, bool], user_data: Any
    ) -> None:
        loop_start, loop_end, loop_enabled = loop_info
        node.set_marker(MusicSegment.loop_start_id, loop_start)
        node.set_marker(MusicSegment.loop_end_id, loop_end)
        # TODO not sure how to enable/disable looping
        logger.warning("Don't know yet how to enable/disable looping")

    tracks = [cid for cid in node.children if isinstance(bnk.get(cid), MusicTrack)]
    if tracks:
        with dpg.group(horizontal=True):
            dpg.add_combo(
                [str(t) for t in tracks],
                tag=f"{base_tag}_child_tracks",
            )
            dpg.add_button(
                label="Edit on Track",
                callback=edit_markers_on_track,
            )
    else:
        dpg.add_text("Segment has no tracks", color=style.yellow)

    add_widget_table(
        node.markers,
        new_marker,
        create_row,
        on_add=on_marker_added,
        on_remove=on_marker_removed,
        add_item_label="+ Add Marker",
        label="Markers",
    )


def _create_attributes_music_track(
    bnk: Soundbank,
    node: MusicTrack,
    properties: dict[str, property],
    on_node_changed: Callable[[str, Node, Any], None],
    on_node_selected: Callable[[str, Node, Any], None],
    *,
    parent: str = 0,
    user_data: Any = None,
    base_tag: str = 0,
) -> None:
    def on_source_changed(sender: str, filepath: Path, source_index: int) -> None:
        if filepath.name.endswith(".wav"):
            wwise = get_config().locate_wwise()
            wem_path = wav2wem(wwise, filepath)[0]
        else:
            wem_path = filepath

        copy_wems_dialog(bnk, wem_path, source["source_type"])

        source_details = node.sources[source_index]["media_information"]
        source_details["source_id"] = int(wem_path.stem)
        source_details["in_memory_media_size"] = wem_path.stat().st_size

        dpg.set_value(sender, wem_path.stem)
        on_node_changed(base_tag, node, user_data)

    def on_loop_changed(
        sender: str,
        loop_info: tuple[float, float, bool],
        cb_user_data: Any,
    ) -> None:
        # TODO not sure where to enable or disable looping
        loop_start, loop_end, loop_enabled = loop_info
        segment.set_marker(MusicSegment.loop_start_id, loop_start * 1000.0)
        segment.set_marker(MusicSegment.loop_end_id, loop_end * 1000.0)
        on_node_changed(base_tag, node, user_data)

    def set_trims(sender: str, trims: tuple[float, float], idx: int) -> None:
        node.set_trims(trims[0] * 1000, trims[1] * 1000, idx)
        on_node_changed(base_tag, node, user_data)

    def on_clips_changed(sender: str, curves: list[GraphCurve], user_data: Any) -> None:
        node.clear_clips()
        for curve in curves:
            node.add_clip(curve.curve_type, curve)

        on_node_changed(base_tag, node, user_data)

    segment: MusicSegment = bnk.get(node.parent)
    markers_enabled = bool(isinstance(segment, MusicSegment))

    if markers_enabled:
        loop_start = segment.get_marker(MusicSegment.loop_start_id)["position"] / 1000.0
        loop_end = segment.get_marker(MusicSegment.loop_end_id)["position"] / 1000.0
    else:
        loop_start = 1.0
        loop_end = -1.0

    if len(node.sources) > 1:
        dpg.add_text(
            "Track has multiple sources, might not be handled correctly",
            color=style.yellow,
        )

    # Not sure why music tracks can have several sources or what to do
    # with loop info if that happens, but so far I didn't se that
    with dpg.group():
        for i, source in enumerate(node.sources):
            if source["source_type"] == "Embedded":
                path = node.get_source_path(bnk, i)
            else:
                path = get_sound_path(bnk, source)

            trims = node.get_trims(i)
            add_wav_player(
                path,
                on_file_changed=on_source_changed,
                loop_markers_enabled=markers_enabled,
                edit_markers_inplace=False,
                on_loop_changed=on_loop_changed,
                loop_start=loop_start,
                loop_end=loop_end,
                trim_enabled=True,
                begin_trim=trims[0] / 1000.0,
                end_trim=trims[1] / 1000.0,
                on_trim_marker_changed=set_trims,
                user_data=i,
            )

        add_curves_table(
            [
                GraphCurve.from_wwise(clip["auto_type"], clip["graph_points"])
                for clip in node.clips
            ],
            get_args(ClipType),
            on_clips_changed,
            label="Clips",
            add_item_label="+ Add Clip",
        )

        dpg.add_spacer(height=3)
        dpg.add_separator()
        dpg.add_spacer(height=3)


def _create_attributes_sound(
    bnk: Soundbank,
    node: Sound,
    properties: dict[str, property],
    on_node_changed: Callable[[str, Node, Any], None],
    on_node_selected: Callable[[str, Node, Any], None],
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> None:
    properties.pop("media_size")
    properties.pop("source_id")

    def on_filepath_selected(sender: str, filepath: Path, sound: Sound) -> None:
        if filepath.name.endswith(".wav"):
            wwise = get_config().locate_wwise()
            wem_path = wav2wem(wwise, filepath)[0]
        else:
            wem_path = filepath

        copy_wems_dialog(bnk, wem_path, sound.source_type)

        sound.source_id = int(wem_path.stem)
        sound.media_size = wem_path.stat().st_size
        dpg.set_value(sender, wem_path.stem)
        on_node_changed(base_tag, sound, user_data)

    if node.source_type == "Embedded":
        path = node.get_source_path(bnk)
    else:
        path = get_sound_path(bnk, node.source_info)

    with dpg.group():
        add_wav_player(path, on_file_changed=on_filepath_selected)

        dpg.add_spacer(height=3)
        dpg.add_separator()
        dpg.add_spacer(height=3)


def _create_attributes_switch_container(
    bnk: Soundbank,
    node: SwitchContainer,
    properties: dict[str, property],
    on_node_changed: Callable[[str, Node, Any], None],
    on_node_selected: Callable[[str, Node, Any], None],
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> None:
    def on_show_empty_switches(sender: str, show: bool, node: SwitchContainer) -> None:
        for switch, nodes in node.switch_mappings.items():
            dpg.configure_item(
                f"{base_tag}_node_{node.id}_switch_{switch}",
                show=show or bool(nodes),
            )

    with dpg.group():
        dpg.add_checkbox(
            label="Show empty switches",
            callback=on_show_empty_switches,
            default_value=False,
            user_data=node,
        )

        with dpg.tree_node(label="Switches"):
            for switch, nodes in node.switch_mappings.items():
                label = f"{len(nodes)} - {lookup_name(switch, '?')} ({switch})"
                with dpg.tree_node(
                    label=label,
                    show=bool(nodes),
                    tag=f"{base_tag}_node_{node.id}_switch_{switch}",
                ):
                    for nid in nodes:
                        switch_node = bnk.get(nid)
                        if switch_node:
                            add_node_link(
                                switch_node, on_node_selected, user_data=user_data
                            )
                        else:
                            dpg.add_text(f"(ext) {nid}")

        dpg.add_spacer(height=3)
        dpg.add_separator()
        dpg.add_spacer(height=3)
