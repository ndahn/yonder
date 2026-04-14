from typing import Any, Callable
from pathlib import Path
from docstring_parser import parse as doc_parse
import shutil
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.hash import lookup_name
from yonder.types import (
    Action,
    ActionType,
    ActorMixer,
    AudioDevice,
    AuxiliaryBus,
    Attenuation,
    Bus,
    DialogueEvent,
    Event,
    EffectCustom,
    EffectShareSet,
    LayerContainer,
    MusicRandomSequenceContainer,
    MusicSegment,
    MusicSwitchContainer,
    MusicTrack,
    RandomSequenceContainer,
    Section,
    Sound,
    State,
    SwitchContainer,
    TimeModulator,
)
from yonder.types.action import ActionParams
from yonder.util import logger, to_typed_dict
from yonder.types.base_types import (
    ConversionTable,
    ClipAutomation,
    BankSourceData,
    MusicTransitionRule,
    DecisionTreeNode,
    MusicMarkerWwise,
    RTPC,
)
from yonder.enums import (
    SourceType,
    CurveScaling,
    CurveParameters,
    ClipAutomationType,
    PropID,
    DecisionTreeMode,
    MarkerId,
    RandomMode,
    PlaybackMode,
)
from yonder.wem import wav2wem, create_prefetch_snippet
from yonder.gui import style
from yonder.gui.config import get_config
from yonder.gui.helpers import GraphCurve
from .paragraphs import add_paragraphs
from .generic_input_widget import add_generic_widget, is_simple_type
from .loading_indicator import loading_indicator
from .properties_table import add_properties_table
from .rtpc_table import add_rtpc_table
from .wav_player import add_wav_player
from .transition_matrix import add_transition_matrix
from .editable_table import add_widget_table, add_curves_table
from .hash_widget import add_hash_widget


def create_attribute_widgets(
    bnk: Soundbank,
    node: HIRCNode,
    on_node_changed: Callable[[str, HIRCNode, Any], None],
    on_node_selected: Callable[[str, int | HIRCNode, Any], None],
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

    loading = loading_indicator("loading...")
    try:
        with dpg.group(tag=tag, parent=parent):
            # Heading
            dpg.add_text(node.type_name)
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

            if hasattr(node, "parent"):
                with dpg.group(horizontal=True):
                    dpg.add_text("Parent: ")
                    parent_node = bnk.get(node.parent, node.parent)
                    add_node_link(repr(parent_node), parent_node, on_node_selected)

            dpg.add_spacer(height=3)
            dpg.add_separator()
            dpg.add_spacer(height=3)

            # This may remove or add properties that are handled differently
            try:
                _create_type_specific_attributes(
                    bnk,
                    node,
                    on_node_changed,
                    on_node_selected,
                    base_tag=tag,
                    user_data=user_data,
                )
            except Exception as e:
                logger.error(f"Error creating node widgets: {e}", exc_info=e)
                dpg.add_text("Error creating node widgets, check logs", color=style.red)

            dpg.add_spacer(height=5)

            if hasattr(node, "properties"):
                add_node_properties(
                    node, on_node_changed, base_tag=tag, user_data=user_data
                )

            if hasattr(node, "rtpcs"):
                add_node_rtpc(
                    bnk, node, on_node_changed, base_tag=tag, user_data=user_data
                )
    finally:
        dpg.delete_item(loading)

    return tag


def add_node_properties(
    node: HIRCNode,
    on_node_changed: Callable[[str, HIRCNode, Any], None],
    *,
    base_tag: str = None,
    user_data: Any = None,
) -> None:
    def on_node_properties_changed(
        sender: str, new_props: dict[PropID, float], node: HIRCNode
    ) -> None:
        for prop in list(node.properties):
            if prop.prop_id not in new_props:
                node.remove_property(prop.prop_id)

        for key, val in new_props.items():
            node.set_property(key, val)

        on_node_changed(base_tag, node, user_data)

    with dpg.tree_node(label="Properties", default_open=bool(node.properties)):
        add_properties_table(
            {p.prop_id: p.value for p in node.properties},
            on_node_properties_changed,
            label=None,
            user_data=node,
        )


def add_node_rtpc(
    bnk: Soundbank,
    node: HIRCNode,
    on_node_changed: Callable[[str, HIRCNode, Any], None],
    *,
    base_tag: str = None,
    user_data: Any = None,
) -> None:
    def on_rtpcs_changed(sender: str, rtpcs: list[RTPC], cb_user_data: Any) -> None:
        node.rtpcs[:] = rtpcs
        if on_node_changed:
            on_node_changed(base_tag, node, user_data)

    with dpg.tree_node(label="RTPC", default_open=bool(node.rtpcs)):
        add_rtpc_table(bnk, node.rtpcs, on_rtpcs_changed, label=None)


def add_node_link(
    label: str,
    target: int | HIRCNode,
    on_node_selected: Callable[[str, HIRCNode, Any], None],
    *,
    tag: str = 0,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    if isinstance(target, HIRCNode):
        target = target.id

    dpg.add_button(
        label=label,
        small=True,
        callback=lambda s, a, u: on_node_selected(tag, u, user_data),
        user_data=target,
        tag=tag,
    )
    dpg.bind_item_theme(dpg.last_item(), style.themes.link_button)
    return tag


def add_letmeknow() -> None:
    with dpg.child_window(auto_resize_x=True, auto_resize_y=True):
        dpg.add_text("Let me know what you want here!")
        dpg.add_text("Ping @managarm on ?ServerName?", color=style.orange)


def make_setter(
    node: HIRCNode,
    path: str,
    sender: str,
    on_node_changed: Callable[[str, HIRCNode, Any], None],
    user_data: Any,
    value_transformer: Callable[[Any], Any] = None,
):
    def cb(sender: str, new_value: Any, cb_user_data: Any) -> None:
        if value_transformer:
            new_value = value_transformer(new_value)

        node.set_value(path, new_value)

        if on_node_changed:
            on_node_changed(sender, node, user_data)

    return cb


def get_sound_path(bnk: Soundbank, source: BankSourceData) -> Path:
    source_id = source.media_information.source_id
    source_type = source.source_type

    wem = bnk.bnk_dir / f"{source_id}.wem"
    if source_type != SourceType.PrefetchStreaming and wem.is_file():
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
    if wem.is_file() and source_type == SourceType.PrefetchStreaming:
        logger.warning(
            f"Could not find streamed sound for {source_id}, playing prefetch snippet"
        )
        return wem

    return None


def copy_wems_dialog(bnk: Soundbank, wav: Path, wem: Path, source_type: SourceType):
    from yonder.gui.dialogs.choice_dialog import simple_choice_dialog

    def copy_wems() -> None:
        if source_type == SourceType.Embedded:
            target = bnk.bnk_dir / wem.name
            if target.is_file():
                target.unlink()
            shutil.copy(wem, target)

        elif source_type in (SourceType.Streaming, SourceType.PrefetchStreaming):
            target = bnk.bnk_dir.parent / wem / f"{wem.stem[:2]}" / wem.name
            if target.is_file():
                target.unlink()
            shutil.copy(wem, target)

            if source_type == SourceType.PrefetchStreaming:
                wwise = get_config().locate_wwise()
                snippet = create_prefetch_snippet(wav)
                wem_snippet = wav2wem(wwise, snippet, out_dir=bnk.bnk_dir)[0]
                logger.info(f"Placed prefetch snippet in {wem_snippet}")

        else:
            raise ValueError(f"Unknown source_type {source_type}")

        logger.info(f"Copied {wem.name} to {target}")

    simple_choice_dialog(
        f"Copy WEMs to soundbank {bnk.name}?",
        ["Yes", "No"],
        lambda s, a, u: copy_wems(),
        title="Copy?",
    )


def _create_type_specific_attributes(
    bnk: Soundbank,
    node: HIRCNode,
    on_node_changed: Callable[[str, HIRCNode, Any], None],
    on_node_selected: Callable[[str, HIRCNode, Any], None],
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> bool:
    if isinstance(node, Action):
        _create_attributes_action(
            bnk,
            node,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
        return True
    elif isinstance(node, ActorMixer):
        pass
    elif isinstance(node, Attenuation):
        _create_attributes_attenuation(
            bnk,
            node,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
        return True
    elif isinstance(node, Bus):
        # TODO
        add_letmeknow()
    elif isinstance(node, Event):
        _create_attributes_event(
            bnk,
            node,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
        return True
    elif isinstance(node, LayerContainer):
        # TODO
        add_letmeknow()
    elif isinstance(node, MusicRandomSequenceContainer):
        _create_attributes_musicrandomsequencecontainer(
            bnk,
            node,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
        return True
    elif isinstance(node, MusicSegment):
        _create_attributes_musicsegment(
            bnk,
            node,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
        return True
    elif isinstance(node, MusicSwitchContainer):
        _create_attributes_musicswitchcontainer(
            bnk,
            node,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
        return True
    elif isinstance(node, MusicTrack):
        _create_attributes_musictrack(
            bnk,
            node,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
        return True
    elif isinstance(node, RandomSequenceContainer):
        _create_attributes_randomsequencecontainer(
            bnk,
            node,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
        return True
    elif isinstance(node, Sound):
        _create_attributes_sound(
            bnk,
            node,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
        return True
    elif isinstance(node, SwitchContainer):
        _create_attributes_switchcontainer(
            bnk,
            node,
            on_node_changed,
            on_node_selected,
            base_tag=base_tag,
            user_data=user_data,
        )
        return True
    else:
        add_letmeknow()

    return False


def _create_attributes_action(
    bnk: Soundbank,
    node: Action,
    on_node_changed: Callable[[str, HIRCNode, Any], None],
    on_node_selected: Callable[[str, HIRCNode, Any], None],
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> None:
    def set_value(path: str, val: Any) -> None:
        parts = path.split("/")

        sub = node.params
        for p in parts[:-1]:
            if ":" in p:
                p, idx = p.split(":")
                sub = getattr(sub, p)[idx]
            else:
                sub = getattr(sub, p)

        key = parts[-1]
        if ":" in key:
            # Set list item
            p, idx = key.split(":")
            sub = getattr(sub, p)
            sub[idx] = val
        else:
            # Set regular member
            setattr(sub, key, val)

        if on_node_changed:
            on_node_changed(base_tag, node, user_data)

    def create_generic_widgets_recursive(
        d: dict[str, tuple[type, Any]], path: str = ""
    ) -> None:
        for key, (tp, val) in d.items():
            if isinstance(val, dict):
                val_path = f"{path}/{key}" if path else key
                create_generic_widgets_recursive(val, val_path)

            elif isinstance(val, list):
                if is_simple_type(tp):
                    add_generic_widget(
                        tp, key, lambda s, a, u: set_value(path, a), default=val
                    )
                else:
                    for idx, item in enumerate(val):
                        item_path = f"{path}/{key}:{idx}" if path else f"{key}:{idx}"
                        create_generic_widgets_recursive(item, item_path)

            else:
                add_generic_widget(
                    tp,
                    key,
                    lambda s, a, u: set_value(path, a),
                    default=val,
                    not_supported_ok=True,
                )

    params = node.params
    # PlayEvents will have a string here
    if isinstance(params, ActionParams):
        data = to_typed_dict(params, True)
        # No changing type, we'd have to exchange the params for that
        data.pop("action_type")
        create_generic_widgets_recursive(data)


def _create_attributes_attenuation(
    bnk: Soundbank,
    node: Attenuation,
    on_node_changed: Callable[[str, HIRCNode, Any], None],
    on_node_selected: Callable[[str, HIRCNode, Any], None],
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
            curve_type = CurveScaling[curve.curve_type]
            node.curves.append(ConversionTable(curve_type, points=curve.points))

        curve_items = ["-"] + [f"Curve #{i}" for i in range(len(curves))]
        for i in range(len(node.curves_to_use)):
            dpg.configure_item(f"{base_tag}_curve_param_{i}", items=curve_items)

        if on_node_changed:
            on_node_changed(base_tag, node, user_data)

    def on_curve_param_changed(sender: str, curve: str, param_idx: int) -> None:
        if curve == "-":
            curve_idx = -1
        else:
            curve_idx = int(curve.split("#")[-1])

        node.curves_to_use[param_idx] = curve_idx

        if on_node_changed:
            on_node_changed(base_tag, node, user_data)

    with dpg.group():
        with dpg.tree_node(label="Curves to use", default_open=True):
            for i, curve in enumerate(node.curves_to_use):
                param = CurveParameters(i).name
                default_value = f"Curve #{curve}" if curve >= 0 else "-"

                dpg.add_combo(
                    ["-"] + [f"Curve #{i}" for i in range(len(node.curves))],
                    default_value=default_value,
                    label=param,
                    callback=on_curve_param_changed,
                    user_data=i,
                    tag=f"{base_tag}_curve_param_{i}",
                )

            dpg.add_spacer(height=5)
            add_curves_table(
                [GraphCurve(c.curve_scaling.name, c.points) for c in node.curves],
                sorted([s.name for s in CurveScaling]),
                on_curves_changed,
                curve_type_label="Scaling Type",
            )

        with dpg.tree_node(label="Cone params"):
            dpg.add_checkbox(
                label="Cone enabled",
                default_value=(node.is_cone_enabled > 0),
                callback=make_setter(
                    node, "is_cone_enabled", base_tag, on_node_changed, user_data
                ),
                tag=f"{base_tag}_cone_enabled",
            )
            dpg.add_input_float(
                label="inside_degrees",
                default_value=node.cone_params.inside_degrees,
                min_value=0.0,
                min_clamped=True,
                max_value=90.0,
                max_clamped=True,
                callback=make_setter(
                    node, "inside_degrees", base_tag, on_node_changed, user_data
                ),
                tag=f"{base_tag}_inside_degrees",
            )
            dpg.add_input_float(
                label="outside_degrees",
                default_value=node.cone_params.outside_degrees,
                min_value=0.0,
                min_clamped=True,
                max_value=90.0,
                max_clamped=True,
                callback=make_setter(
                    node, "outside_degrees", base_tag, on_node_changed, user_data
                ),
                tag=f"{base_tag}_outside_degrees",
            )
            dpg.add_input_float(
                label="outside_volume",
                default_value=node.cone_params.outside_volume,
                # min_value=0.0,
                # min_clamped=True,
                # max_value=90.0,
                # max_clamped=True,
                callback=make_setter(
                    node, "outside_volume", base_tag, on_node_changed, user_data
                ),
                tag=f"{base_tag}_outside_volume",
            )
            dpg.add_input_float(
                label="low_pass",
                default_value=node.cone_params.low_pass,
                min_value=0.0,
                min_clamped=True,
                # max_value=90.0,
                # max_clamped=True,
                callback=make_setter(
                    node, "low_pass", base_tag, on_node_changed, user_data
                ),
                tag=f"{base_tag}_low_pass",
            )
            dpg.add_input_float(
                label="high_pass",
                default_value=node.cone_params.high_pass,
                min_value=0.0,
                min_clamped=True,
                # max_value=90.0,
                # max_clamped=True,
                callback=make_setter(
                    node, "high_pass", base_tag, on_node_changed, user_data
                ),
                tag=f"{base_tag}_high_pass",
            )


def _create_attributes_event(
    bnk: Soundbank,
    node: Event,
    on_node_changed: Callable[[str, HIRCNode, Any], None],
    on_node_selected: Callable[[str, HIRCNode, Any], None],
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> None:
    def on_actions_changed(
        sender: str, info: tuple[int, list, list], cb_user_data: Any
    ) -> None:
        node.actions[:] = info[2]
        if on_node_changed:
            on_node_changed(base_tag, node, user_data)

    def on_action_type_changed(
        sender: str, action_type_name: str, action_id: int
    ) -> None:
        action: Action = bnk[aid]
        action_type = ActionType[action_type_name]
        try:
            action.change_type(action_type)
        except ValueError:
            dpg.set_value(sender, action.action_type_enum.name)
            raise

        if on_node_changed:
            on_node_changed(base_tag, node, user_data)

    def add_action(done: Callable[[int], None]) -> None:
        # TODO new action dialog
        action: Action = Action.new_play_action(bnk.new_id(), 0, bnk.bank_id)
        bnk.add_nodes(action)
        node.actions.append(action.id)

        if on_node_changed:
            on_node_changed(base_tag, node, user_data)

        done(action.id)

    def get_row_for_action(aid: int, idx: int) -> None:
        with dpg.group(horizontal=True):
            dpg.add_text(str(aid))
            action = bnk.get(aid)
            if action:
                action: Action = bnk[aid]
                dpg.add_combo(
                    [at.name for at in ActionType],
                    default_value=action.action_type_enum.name,
                    width=150,
                    callback=on_action_type_changed,
                    user_data=aid,
                )
                dpg.add_text(">")
                target = bnk.get(action.external_id)
                if target:
                    add_node_link(repr(target), target.id, on_node_selected)
                else:
                    dpg.add_text(f"#{action.external_id} (not found)")

            else:
                dpg.add_text(f"#{aid} (not found)")

    add_widget_table(
        node.actions,
        get_row_for_action,
        new_item=add_action,
        on_add=on_actions_changed,
        on_remove=on_actions_changed,
        label="Actions",
        add_item_label="+ Add Action",
        tag=f"{base_tag}_actions",
    )


def _create_attributes_musicrandomsequencecontainer(
    bnk: Soundbank,
    node: MusicRandomSequenceContainer,
    on_node_changed: Callable[[str, HIRCNode, Any], None],
    on_node_selected: Callable[[str, HIRCNode, Any], None],
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> None:
    def on_transition_rule_changed(
        sender: str, rule: MusicTransitionRule, cb_user_data: Any
    ) -> None:
        if on_node_changed:
            on_node_changed(base_tag, node, user_data)

    with dpg.group():
        add_transition_matrix(
            bnk, node, on_transition_rule_changed, user_data=user_data
        )

        dpg.add_spacer(height=3)
        dpg.add_separator()
        dpg.add_spacer(height=3)


def _create_attributes_musicswitchcontainer(
    bnk: Soundbank,
    node: MusicSwitchContainer,
    on_node_changed: Callable[[str, HIRCNode, Any], None],
    on_node_selected: Callable[[str, HIRCNode, Any], None],
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> None:
    from yonder.gui.dialogs.edit_state_path_dialog import create_state_path_dialog

    names = {
        a.group_id: lookup_name(a.group_id, f"#{a.group_id}") for a in node.arguments
    }

    def on_state_path_created(
        sender: str, state_path: list[int], path_node_id: int
    ) -> None:
        node.add_branch(state_path, path_node_id)
        # Regenerate
        on_node_selected(base_tag, node, user_data)

    def on_tree_mode_changed(sender: str, mode: str, cb_user_data: Any) -> None:
        node.tree_mode = DecisionTreeMode[mode]
        on_node_changed(base_tag, node, user_data)

    def on_node_key_changed(
        sender: str, info: tuple[int, str], branch: tuple[DecisionTreeNode, int, str]
    ) -> None:
        tree_node = branch[0]
        tree_node.key = info[0]
        update_branch_label(sender, branch, None)

    def update_branch_label(
        sender: str, info: tuple[DecisionTreeNode, int, str], cb_user_data: Any
    ) -> None:
        tree_node, level, dpg_item = info

        arg = node.arguments[level]
        arg_name = names[arg.group_id]
        val_name = get_key(tree_node)

        label = f"{arg_name} = {val_name}"
        dpg.set_item_label(dpg_item, label)

    def bind_context_menu(
        item: str, tree_node: DecisionTreeNode, level: int
    ) -> None:
        arg = node.arguments[level]
        arg_name = names[arg.group_id]
        val_name = get_key(tree_node)

        with dpg.popup(item, mousebutton=dpg.mvMouseButton_Right, min_size=(100, 50)):
            dpg.add_text(arg_name)
            add_hash_widget(
                tree_node.key,
                on_node_key_changed,
                horizontal=False,
                initial_string=val_name,
                string_label="Value",
                width=100,
                user_data=(tree_node, level, item),
            )

    def get_key(tree_node: DecisionTreeNode) -> str:
        val = tree_node.key
        if val == 0:
            return "*"
        return lookup_name(val, f"#{val}")

    def delve(tree_node: DecisionTreeNode, level: int) -> None:
        if level == len(node.arguments) - 1:
            # Leaf
            nid = tree_node.node_id
            leaf_node = bnk.get(nid)

            with dpg.tree_node(span_full_width=True) as dpg_item:
                # TODO should be an input field
                if leaf_node:
                    add_node_link(
                        repr(leaf_node), leaf_node, on_node_selected, user_data=user_data
                    )
                else:
                    dpg.add_text(f"#{nid} (not found)")
        else:
            # Branch
            with dpg.tree_node(span_full_width=True) as dpg_item:
                for child in tree_node.children:
                    delve(child, level + 1)

        bind_context_menu(dpg_item, tree_node, level)
        update_branch_label(None, (tree_node, level, dpg_item), None)

    with dpg.group():
        dpg.add_combo(
            [m.name for m in DecisionTreeMode],
            default_value=node.tree_mode.name,
            callback=on_tree_mode_changed,
            tag=f"{base_tag}_tree_mode",
        )

        with dpg.tree_node(label="Decision Tree", default_open=True):
            for child in node.tree.children:
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


def _create_attributes_musicsegment(
    bnk: Soundbank,
    node: MusicSegment,
    on_node_changed: Callable[[str, HIRCNode, Any], None],
    on_node_selected: Callable[[str, HIRCNode, Any], None],
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
        pos = node.markers[idx].position
        node.markers.pop(idx)
        node.set_marker(name or mid, pos)
        on_node_changed(base_tag, node, user_data)

    def on_marker_moved(sender: str, new_pos: float, info: tuple[int, int]) -> None:
        _, mid = info
        node.set_marker(mid, new_pos)
        on_node_changed(base_tag, node, user_data)

    def on_marker_added(
        sender: str,
        info: tuple[int, MusicMarkerWwise, list[MusicMarkerWwise]],
        cb_user_data: Any,
    ) -> None:
        marker = info[1]
        node.set_marker(marker.id, marker.position)
        on_node_changed(base_tag, node, user_data)

    def on_marker_removed(
        sender: str,
        info: tuple[int, MusicMarkerWwise, list[MusicMarkerWwise]],
        cb_user_data: Any,
    ) -> None:
        marker = info[1]
        node.remove_marker(marker.id)
        on_node_changed(base_tag, node, user_data)

    def new_marker(done: Callable[[MusicMarkerWwise], None]) -> None:
        done(node.set_marker(f"m{len(node.markers)}", 0.0))

    def create_row(marker: MusicMarkerWwise, idx: int) -> None:
        with dpg.group(horizontal=True):
            add_hash_widget(
                marker.id,
                on_marker_renamed,
                initial_string=marker.string,
                width=200,
                hash_label=None,
                user_data=(idx, marker.id),
            )
            dpg.add_input_float(
                default_value=marker.position,
                min_value=0.0,
                min_clamped=True,
                callback=on_marker_moved,
                user_data=(idx, marker.id),
                width=-1,
            )

    def on_loop_changed(
        sender: str, loop_info: tuple[float, float, bool], user_data: Any
    ) -> None:
        loop_start, loop_end, loop_enabled = loop_info
        node.set_marker(MarkerId.LoopStart, loop_start)
        node.set_marker(MarkerId.LoopEnd, loop_end)
        # TODO not sure how to enable/disable looping

    def edit_markers_on_track() -> None:
        track_name = dpg.get_value(f"{base_tag}_child_tracks")
        if not track_name:
            return

        track_id = int(track_name.split("#")[-1])
        track: MusicTrack = bnk[track_id]
        if not track.sources:
            logger.warning(f"{track} has no sources")
            return

        if track.sources[0].source_type == SourceType.Embedded:
            path = track.get_source_path(bnk, 0)
        else:
            path = get_sound_path(bnk, track.sources[0])

        loop_start = node.get_marker_pos(MarkerId.LoopStart, 1000.0)
        loop_end = node.get_marker_pos(MarkerId.LoopEnd, -1000.0)

        edit_markers_dialog(
            path,
            accept_on_okay=True,
            loop_markers_enabled=True,
            loop_start=loop_start,
            loop_end=loop_end,
            on_loop_changed=on_loop_changed,
        )

    add_widget_table(
        node.markers,
        create_row,
        new_item=new_marker,
        on_add=on_marker_added,
        on_remove=on_marker_removed,
        add_item_label="+ Add Marker",
        label="Markers",
    )

    tracks = [cid for cid in node.children if isinstance(bnk.get(cid), MusicTrack)]
    if tracks:
        with dpg.group(horizontal=True):
            dpg.add_combo(
                [f"Track #{t}" for t in tracks],
                tag=f"{base_tag}_child_tracks",
            )
            dpg.add_button(
                label="Edit on Track",
                callback=edit_markers_on_track,
            )
    else:
        dpg.add_text("Segment has no tracks", color=style.yellow)


def _create_attributes_musictrack(
    bnk: Soundbank,
    node: MusicTrack,
    on_node_changed: Callable[[str, HIRCNode, Any], None],
    on_node_selected: Callable[[str, HIRCNode, Any], None],
    *,
    user_data: Any = None,
    base_tag: str = 0,
) -> None:
    def on_source_changed(sender: str, filepath: Path, source_index: int) -> None:
        if filepath.name.endswith(".wav"):
            wwise = get_config().locate_wwise()
            wem_path = wav2wem(wwise, filepath)[0]
        else:
            wem_path = filepath

        source = node.sources[i]
        copy_wems_dialog(bnk, wem_path, source.source_type)

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
        segment.set_marker(MarkerId.LoopStart, loop_start)
        segment.set_marker(MarkerId.LoopEnd, loop_end)
        on_node_changed(base_tag, node, user_data)

    def set_trims(sender: str, trims: tuple[float, float], idx: int) -> None:
        node.set_trims(trims[0], trims[1], idx)
        on_node_changed(base_tag, node, user_data)

    def apply_curves(curves: list[GraphCurve]) -> None:
        for curve in curves:
            auto_type = ClipAutomationType[curve.curve_type]
            for player in players:
                if auto_type == ClipAutomationType.Volume:
                    player.set_volume(curve)
                elif auto_type == ClipAutomationType.LPF:
                    player.set_lowpass(curve)
                elif auto_type == ClipAutomationType.HPF:
                    player.set_highpass(curve)
                elif auto_type == ClipAutomationType.FadeIn:
                    player.set_fadein(curve)
                elif auto_type == ClipAutomationType.FadeOut:
                    player.set_fadeout(curve)
                else:
                    logger.warning(f"Unknown ClipAutomationType {auto_type}")

    def on_clips_changed(
        sender: str, curves: list[GraphCurve], cb_user_data: Any
    ) -> None:
        node.clear_clips()
        for idx, curve in enumerate(curves):
            auto_type = ClipAutomationType[curve.curve_type]
            node.clip_items.append(
                ClipAutomation(idx, auto_type, graph_points=curve.points)
            )

        apply_curves(curves)
        on_node_changed(base_tag, node, user_data)

    segment: MusicSegment = bnk.get(node.parent)
    markers_enabled = bool(isinstance(segment, MusicSegment))
    players: list[add_wav_player] = []

    if markers_enabled:
        loop_start = segment.get_marker_pos(MarkerId.LoopStart)
        loop_end = segment.get_marker_pos(MarkerId.LoopEnd)
    else:
        loop_start = 1000.0
        loop_end = -1000.0

    if len(node.sources) > 1:
        dpg.add_text(
            "Track has multiple sources, might not be handled correctly",
            color=style.yellow,
        )

    # Not sure why music tracks can have several sources or what to do
    # with loop info if that happens, but so far I didn't see that.
    # TODO Otherwise we need a player table here.
    with dpg.group():
        for i, source in enumerate(node.sources):
            path = get_sound_path(bnk, source)
            trims = node.get_trims(i)

            player = add_wav_player(
                path,
                on_file_changed=on_source_changed,
                loop_markers_enabled=markers_enabled,
                edit_markers_inplace=False,
                on_loop_changed=on_loop_changed,
                loop_start=loop_start,
                loop_end=loop_end,
                trim_enabled=True,
                begin_trim=trims[0],
                end_trim=trims[1],
                on_trim_marker_changed=set_trims,
                user_data=i,
            )
            players.append(player)

        add_curves_table(
            [GraphCurve(c.auto_type.name, c.graph_points) for c in node.clip_items],
            sorted([c.name for c in ClipAutomationType]),
            on_clips_changed,
            label="Clips",
            add_item_label="+ Add Clip",
        )

        dpg.add_spacer(height=3)
        dpg.add_separator()
        dpg.add_spacer(height=3)

    apply_curves(
        [GraphCurve(c.auto_type.name, c.graph_points) for c in node.clip_items]
    )


def _create_attributes_randomsequencecontainer(
    bnk: Soundbank,
    node: RandomSequenceContainer,
    on_node_changed: Callable[[str, HIRCNode, Any], None],
    on_node_selected: Callable[[str, HIRCNode, Any], None],
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> None:
    def create_playlist_row(item: tuple[int, int], idx: int) -> None:
        target = bnk.get(item[0])
        if target:
            add_node_link(repr(target), target, on_node_selected)
        else:
            dpg.add_text(f"#{item[0]} (not found)")

        dpg.add_input_int(
            default_value=item[1],
            min_value=0,
            min_clamped=True,
            max_value=100000,
            callback=make_setter(
                node,
                f"playlist/items:{idx}/weight",
                base_tag,
                on_node_changed,
                user_data,
            ),
            user_data=idx,
        )

    with dpg.group():
        dpg.add_combo(
            [p.name for p in PlaybackMode],
            label="Playback mode",
            default_value=PlaybackMode(node.mode).name,
            callback=make_setter(
                node,
                "mode",
                base_tag,
                on_node_changed,
                user_data,
                value_transformer=lambda v: PlaybackMode[v].value,
            ),
            tag=f"{base_tag}_mode",
        )
        dpg.add_combo(
            [r.name for r in RandomMode],
            label="Randomization",
            default_value=RandomMode(node.random_mode).name,
            callback=make_setter(
                node,
                "random_mode",
                base_tag,
                on_node_changed,
                user_data,
                value_transformer=lambda v: RandomMode[v].value,
            ),
            tag=f"{base_tag}_random_mode",
        )
        dpg.add_input_int(
            label="Loop count",
            default_value=node.loop_count,
            min_value=0,
            min_clamped=True,
            callback=make_setter(
                node, "loop_count", base_tag, on_node_changed, user_data
            ),
            tag=f"{base_tag}_loop_count",
        )
        dpg.add_input_int(
            label="Avoid repetitions",
            default_value=node.avoid_repeat_count,
            min_value=0,
            min_clamped=True,
            callback=make_setter(
                node, "avoid_repeat_count", base_tag, on_node_changed, user_data
            ),
            tag=f"{base_tag}_avoid_repeat_count",
        )

        # TODO Allow adding new children (via create object dialog)
        dpg.add_spacer(height=5)
        item_weights = [(p.play_id, p.weight) for p in node.playlist.items]
        add_widget_table(
            item_weights,
            create_playlist_row,
            label="Playlist",
            header_row=True,
            columns=("Item", "Weight"),
            tag=f"{base_tag}_playlist",
        )


def _create_attributes_sound(
    bnk: Soundbank,
    node: Sound,
    on_node_changed: Callable[[str, HIRCNode, Any], None],
    on_node_selected: Callable[[str, HIRCNode, Any], None],
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> None:
    def on_filepath_selected(sender: str, filepath: Path, sound: Sound) -> None:
        if filepath.name.endswith(".wav"):
            wwise = get_config().locate_wwise()
            wem_path = wav2wem(wwise, filepath)[0]
        else:
            wem_path = filepath

        copy_wems_dialog(bnk, wem_path, sound.source_type)

        sound.set_source_from_wem(wem_path)
        dpg.set_value(sender, wem_path.stem)
        on_node_changed(base_tag, sound, user_data)

    path = get_sound_path(bnk, node.bank_source_data)

    with dpg.group():
        add_wav_player(path, on_file_changed=on_filepath_selected)

        dpg.add_spacer(height=3)
        dpg.add_separator()
        dpg.add_spacer(height=3)


def _create_attributes_switchcontainer(
    bnk: Soundbank,
    node: SwitchContainer,
    on_node_changed: Callable[[str, HIRCNode, Any], None],
    on_node_selected: Callable[[str, HIRCNode, Any], None],
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> None:
    def on_show_empty_switches(sender: str, show: bool, node: SwitchContainer) -> None:
        for switch in node.switch_groups:
            dpg.configure_item(
                f"{base_tag}_node_{node.id}_switch_{switch.switch_id}", show=show
            )

    with dpg.group():
        dpg.add_checkbox(
            label="Show empty switches",
            callback=on_show_empty_switches,
            default_value=False,
            user_data=node,
        )

        with dpg.tree_node(label="Switches"):
            for switch in node.switch_groups:
                name = lookup_name(switch.switch_id, "?")
                label = f"({len(switch.nodes)}) / {name} (#{switch.switch_id})"

                with dpg.tree_node(
                    label=label,
                    show=bool(switch.nodes),
                    tag=f"{base_tag}_node_{node.id}_switch_{switch.switch_id}",
                ):
                    for nid in switch.nodes:
                        switch_node = bnk.get(nid)
                        if switch_node:
                            add_node_link(
                                str(switch_node),
                                switch_node,
                                on_node_selected,
                                user_data=user_data,
                            )
                        else:
                            dpg.add_text(f"#{nid} (not found)")
