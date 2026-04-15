from typing import Callable, Any
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.types import (
    Hash,
    Section,
    BKHDSection,
    INITSection,
    DATASection,
    DIDXSection,
    ENVSSection,
    HIRCSection,
    PLATSection,
    STIDSection,
    STMGSection,
)
from yonder.gui import style
from .generic_input_widget import add_generic_widget
from .hash_widget import add_hash_widget


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
        # elif isinstance(section, INITSection):
        #     _create_widgets_init(bnk, section, on_section_changed, base_tag=tag, user_data=user_data)
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
        # elif isinstance(section, PLATSection):
        #    _create_widgets_plat(bnk, section, on_section_changed, base_tag=tag, user_data=user_data)
        # elif isinstance(section, STIDSection):
        #    _create_widgets_stid(bnk, section, on_section_changed, base_tag=tag, user_data=user_data)
        # elif isinstance(section, STMGSection):
        #    _create_widgets_stmg(bnk, section, on_section_changed, base_tag=tag, user_data=user_data)
        else:
            dpg.add_text("TODO", color=style.pink)


def _add_widgets(
    section: Section,
    attributes: list[str | tuple[str, type] | dict[str, Any]],
    on_section_changed: Callable[[str, Section, Any], None] = None,
    *,
    base_tag: str = 0,
    parent: str = 0,
    user_data: Any,
) -> None:
    def make_setter(key: str) -> Callable:
        def set_value(sender: str, new_val: Any, cb_user_data: Any) -> None:
            setattr(section, key, new_val)
            if on_section_changed:
                on_section_changed(base_tag, section, user_data)

        return set_value

    with dpg.group(tag=f"{base_tag}_attributes", parent=parent):
        for key in attributes:
            kwargs = {}
            if isinstance(key, str):
                val = getattr(section, key)
                kwargs.update(
                    {
                        "label": key,
                        "value_type": type(val),
                    }
                )
            elif isinstance(key, tuple):
                key, item_type = key
                val = getattr(section, key)
                kwargs.update(
                    {
                        "label": key,
                        "value_type": item_type,
                    }
                )
            elif isinstance(key, dict):
                kwargs.update(key)

            if "default" not in kwargs:
                if "key" in kwargs:
                    kwargs["default"] = getattr(section, kwargs.pop("key"))
                else:
                    kwargs["default"] = getattr(section, kwargs["label"])

            add_generic_widget(callback=make_setter(key), **kwargs)


def _create_widgets_bkhd(
    bnk: Soundbank,
    section: Section,
    on_section_changed: Callable[[str, Section, Any], None] = None,
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> str:
    _add_widgets(
        section,
        [
            "version",
            ("bank_id", Hash),
            ("language_fnv_hash", Hash),
            ("project_id", Hash),
        ],
        on_section_changed,
        base_tag=base_tag,
        user_data=user_data,
    )


def _create_widgets_hirc(
    bnk: Soundbank,
    section: Section,
    on_section_changed: Callable[[str, Section, Any], None] = None,
    *,
    base_tag: str = 0,
    user_data: Any = None,
) -> str:
    dpg.add_text("See Events tab")
