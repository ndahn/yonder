from typing import Callable, Any
from functools import partial
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.hash import Hash, lookup_name
from yonder.util import logger
from yonder.types.sections import (
    Section,
    BKHDSection,
    INITSection,
    DATASection,
    DIDXSection,
    ENVSSection,
    HIRCSection,
    PLATSection,
    STIDSection,
    STIDSectionEntry,
    STMGSection,
)
from yonder.types.base_types import (
    StateGroup,
    StateTransition,
    SwitchGroup,
    SwitchGraphPoint,
    RTPCRamping,
    AcousticTexture,
)
from yonder.enums import RtpcType
from yonder.gui import style
from yonder.gui.localization import µ
from .generic_input_widget import add_generic_widget
from .editable_table import add_widget_table
from .hash_widget import add_hash_widget
from .interpolation_curve import add_interpolation_curve
from .loading_indicator import loading_indicator


def create_section_widgets(
    bnk: Soundbank,
    section: Section,
    on_section_changed: Callable[[str, Section, Any], None] = None,
    *,
    tag: str = 0,
    parent: str = 0,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    with loading_indicator(µ("loading...", "loading")):
        with dpg.group(tag=tag, parent=parent):
            dpg.add_text(section.name)

            dpg.add_spacer(height=3)
            dpg.add_separator()
            dpg.add_spacer(height=3)

            if isinstance(section, BKHDSection):
                _create_widgets_bkhd(
                    bnk,
                    section,
                    on_section_changed,
                    base_tag=tag,
                    user_data=user_data,
                )
            # elif isinstance(section, DATASection):
            #     _create_widgets_data(bnk, section, on_section_changed, base_tag=tag, user_data=user_data)
            # elif isinstance(section, DIDXSection):
            #     _create_widgets_didx(bnk, section, on_section_changed, base_tag=tag, user_data=user_data)
            # elif isinstance(section, ENVSSection):
            #     _create_widgets_envs(bnk, section, on_section_changed, base_tag=tag, user_data=user_data)
            elif isinstance(section, HIRCSection):
                _create_widgets_hirc(
                    bnk,
                    section,
                    on_section_changed,
                    base_tag=tag,
                    user_data=user_data,
                )
            # elif isinstance(section, INITSection):
            #     _create_widgets_init(bnk, section, on_section_changed, base_tag=tag, user_data=user_data)
            # elif isinstance(section, PLATSection):
            #    _create_widgets_plat(bnk, section, on_section_changed, base_tag=tag, user_data=user_data)
            elif isinstance(section, STIDSection):
                _create_widgets_stid(
                    bnk, section, on_section_changed, base_tag=tag, user_data=user_data
                )
            elif isinstance(section, STMGSection):
                _create_widgets_stmg(
                    bnk, section, on_section_changed, base_tag=tag, user_data=user_data
                )
            else:
                dpg.add_text("TODO", color=style.pink)


def make_setter(
    section: Section,
    path: str,
    on_section_changed,
    sender: Callable[[str, Section, Any], None] = None,
    user_data: Any = None,
    transformer: Callable[[Any], Any] = None,
) -> Callable:
    def setter(cb_sender: str, new_val: Any, cb_user_data: Any) -> None:
        if transformer:
            new_val = transformer(new_val)

        section.set_value(path, new_val)

        if on_section_changed:
            on_section_changed(sender, section, user_data)

    return setter


def _add_widgets(
    section: Section,
    attributes: list[str | tuple[str, type] | dict[str, Any]],
    on_section_changed: Callable[[str, Section, Any], None] = None,
    *,
    base_tag: str = 0,
    parent: str = 0,
    user_data: Any,
) -> None:
    if not base_tag:
        base_tag = dpg.generate_uuid()

    with dpg.group(tag=f"{base_tag}_attributes", parent=parent):
        for path in attributes:
            kwargs = {}
            if isinstance(path, str):
                val = section.get_value(path)
                kwargs.update(
                    {
                        "label": path,
                        "value_type": type(val),
                    }
                )
            elif isinstance(path, tuple):
                path, args = path
                val = section.get_value(path)

                if isinstance(args, dict):
                    item_type = args.get("item_type", type(val))
                else:
                    item_type = args

                kwargs.update(
                    {
                        "label": path,
                        "value_type": item_type,
                    }
                )
            elif isinstance(path, dict):
                path = path.pop("path")
                kwargs.update(path)

            if "default" not in kwargs:
                if "path" in kwargs:
                    kwargs["default"] = section.get_value(kwargs.pop("path"))
                else:
                    kwargs["default"] = section.get_value(kwargs["label"])

            if "value_type" not in kwargs:
                kwargs["value_type"] = type(kwargs["default"])

            label = kwargs["label"]
            kwargs["label"] = µ(label, section.name)

            add_generic_widget(
                callback=make_setter(
                    section, path, on_section_changed, base_tag, user_data
                ),
                **kwargs,
            )


def _create_widgets_bkhd(
    bnk: Soundbank,
    section: BKHDSection,
    on_section_changed: Callable[[str, Section, Any], None] = None,
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> str:
    from yonder.gui.dialogs.rename_bank_dialog import rename_bank_dialog

    def on_bank_renamed(bnk: Soundbank) -> None:
        hash_widget.hash_value = bnk.bank_id
        if on_section_changed:
            on_section_changed(base_tag, section, user_data)

    with dpg.group(horizontal=True):
        hash_widget = add_hash_widget(
            bnk.bank_id,
            allow_edit_hash=False,
            allow_edit_name=False,
            hash_label=None,
        )
        dpg.add_button(
            label=µ("Rename"),
            callback=lambda s, a, u: rename_bank_dialog(bnk, on_bank_renamed),
        )
        dpg.add_text("bank_id")

    dpg.add_spacer(height=5)
    _add_widgets(
        section,
        [
            "version",
            ("language_fnv_hash", Hash),
            ("project_id", Hash),
        ],
        on_section_changed,
        base_tag=base_tag,
        user_data=user_data,
    )


def _create_widgets_hirc(
    bnk: Soundbank,
    section: HIRCSection,
    on_section_changed: Callable[[str, Section, Any], None] = None,
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> str:
    dpg.add_text(µ("See Events tab"))


def _create_widgets_stid(
    bnk: Soundbank,
    section: STIDSection,
    on_section_changed: Callable[[str, Section, Any], None] = None,
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> str:
    def stid_to_row(entry: STIDSectionEntry, idx: int) -> None:
        dpg.add_input_text(
            default_value=str(entry.bnk_id),
            decimal=True,
            width=-1,
            callback=make_setter(
                section,
                f"entries:{idx}/bnk_id",
                on_section_changed,
                base_tag,
                user_data,
                int,
            ),
        )
        dpg.add_input_text(
            default_value=entry.name,
            width=-1,
            callback=make_setter(
                section,
                f"entries:{idx}/name",
                on_section_changed,
                base_tag,
                user_data,
                list,
            ),
        )

    def add_bnk_entry(done: Callable[[STIDSectionEntry], None]) -> None:
        done(STIDSectionEntry())

    def on_add_bnk_entry(
        sender: str,
        info: tuple[int, STIDSectionEntry, list[STIDSectionEntry]],
        user_data: Any,
    ) -> None:
        section.entries.append(info[1])
        if on_section_changed:
            on_section_changed(base_tag, section, user_data)

    def on_remove_bnk_entry(
        sender: str,
        info: tuple[int, STIDSectionEntry, list[STIDSectionEntry]],
        user_data: Any,
    ) -> None:
        section.entries.remove(info[1])
        if on_section_changed:
            on_section_changed(base_tag, section, user_data)

    _add_widgets(
        section,
        [("string_encoding", Hash)],
        on_section_changed,
        base_tag=base_tag,
        user_data=user_data,
    )
    dpg.add_spacer(height=5)
    add_widget_table(
        section.entries,
        stid_to_row,
        new_item=add_bnk_entry,
        on_add=on_add_bnk_entry,
        on_remove=on_remove_bnk_entry,
        add_item_label=µ("+ Add Bank"),
        label=µ("Entries"),
        header_row=True,
        columns=[µ("Bank ID", "table"), µ("Name", "table")],
    )


def _create_widgets_stmg(
    bnk: Soundbank,
    section: STMGSection,
    on_section_changed: Callable[[str, Section, Any], None] = None,
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> str:
    _add_widgets(
        section,
        [
            "volume_threshold",
            ("max_voice_instances", {"min_value": 0, "min_clamped": True}),
            (
                "max_num_dangerous_virt_voices_limit_internal",
                {"min_value": 0, "min_clamped": True},
            ),
        ],
        on_section_changed,
        base_tag=base_tag,
        user_data=user_data,
    )

    def state_group_to_row(state_group: StateGroup, idx: int) -> None:
        path = f"state_groups:{idx}"
        label = lookup_name(state_group.id, f"#{state_group.id}")

        # TODO update label on change
        with dpg.tree_node(label=label, span_full_width=True):
            _add_widgets(
                section,
                [
                    (f"{path}/id", Hash),
                    (
                        f"{path}/default_transition_time",
                        {"min_value": 0, "min_clamped": True},
                    ),
                ],
                on_section_changed,
                user_data=user_data,
            )
            add_widget_table(
                state_group.transitions,
                partial(state_transition_to_row, base_path=path),
                label=µ("Transitions"),
            )

    def state_transition_to_row(
        transition: StateTransition, idx: int, base_path: str
    ) -> None:
        path = f"{base_path}/transitions:{idx}"
        from_label = lookup_name(transition.from_state, f"#{transition.from_state}")
        to_label = lookup_name(transition.to_state, f"#{transition.to_state}")

        # TODO update label on change
        with dpg.tree_node(label=f"#{idx} ({from_label} -> {to_label})", span_full_width=True):
            _add_widgets(
                section,
                [
                    (f"{path}/from_state", Hash),
                    (f"{path}/to_state", Hash),
                    (f"{path}/transition_time", {"min_value": 0, "min_clamped": True}),
                ],
                on_section_changed,
                user_data=user_data,
            )

    def switch_group_to_row(switch_group: SwitchGroup, idx: int) -> None:
        path = f"switch_groups:{idx}"
        label = lookup_name(switch_group.id, f"#{switch_group.id}")

        # TODO update label on change
        with dpg.tree_node(label=label, span_full_width=True):
            _add_widgets(
                section,
                [
                    (f"{path}/id", Hash),
                    (f"{path}/rtpc_id", Hash),
                    (f"{path}/rtpc_type", RtpcType),
                ],
                on_section_changed,
                user_data=user_data,
            )
            # TODO graph_points
            dpg.add_text("TODO: graph_points curve")

    def ramping_param_to_row(ramping_param: RTPCRamping, idx: int) -> None:
        path = f"ramping_params:{idx}"
        label = lookup_name(ramping_param.rtpc_id, f"#{ramping_param.rtpc_id}")

        # TODO update label on change
        with dpg.tree_node(label=label, span_full_width=True):
            _add_widgets(
                section,
                [
                    (f"{path}/rtpc_id", Hash),
                    f"{path}/value",  # TODO meaning?
                    f"{path}/ramp_type",  # TODO unknown enum
                    f"{path}/ramp_up",
                    f"{path}/ramp_down",
                    f"{path}/bind_to_built_in_param",  # TODO should be bool, add conversion
                ],
                on_section_changed,
                user_data=user_data,
            )

    def texture_to_row(texture: AcousticTexture, idx: int) -> None:
        path = f"textures:{idx}"
        label = lookup_name(texture.id, f"#{texture.id}")

        # TODO update label on change
        with dpg.tree_node(label=label, span_full_width=True):
            _add_widgets(
                section,
                [
                    (f"{path}/id", Hash),
                    f"{path}/absorption_offset",
                    f"{path}/absorption_low",
                    f"{path}/absorption_mid_low",
                    f"{path}/absorption_mid_high",
                    f"{path}/absorption_high",
                    f"{path}/scattering",
                ],
                on_section_changed,
                user_data=user_data,
            )

    dpg.add_spacer(height=3)
    dpg.add_separator()
    dpg.add_spacer(height=3)

    # TODO sort by label without breaking updates to json
    # TODO add editing functions
    with dpg.tree_node(label=µ("State Groups"), span_full_width=True):
        add_widget_table(
            section.state_groups,
            state_group_to_row,
        )

    with dpg.tree_node(label=µ("Switch Groups"), span_full_width=True):
        add_widget_table(
            section.switch_groups,
            switch_group_to_row,
        )

    with dpg.tree_node(label=µ("Ramping Params"), span_full_width=True):
        add_widget_table(
            section.ramping_params,
            ramping_param_to_row,
        )

    with dpg.tree_node(label=µ("Textures"), span_full_width=True):
        add_widget_table(
            section.textures,
            texture_to_row,
        )
