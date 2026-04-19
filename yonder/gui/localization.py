from typing import Any
import logging
import gettext
from dearpygui import dearpygui as dpg

from yonder.util import resource_dir


_languages: dict[str, str] = {
    "en": "English",
    "zh-cn": "中文",
}

_active_lang = "en"
_translations_dir = resource_dir() / "localization"
_translation = gettext.translation(
    "yonder", _translations_dir, languages=[_active_lang], fallback=True
)
_reverse_map: dict[str, tuple[str, str]] = {}

_lang_log_level = logging.DEBUG + 5
logging.addLevelName(_lang_log_level, "I18N")


def get_available_languages() -> dict[str, str]:
    return dict(_languages)


def get_active_language() -> str:
    return _active_lang


def set_active_language(lang: str) -> None:
    global _translation, _active_lang
    _translation = gettext.translation(
        "yonder", _translations_dir, languages=[lang], fallback=True
    )
    _active_lang = lang


def µ(msg: str, ctx: str = None) -> str:
    if ctx:
        trans = _translation.pgettext(ctx, msg)
    else:
        trans = _translation.gettext(msg)

    _reverse_map[trans] = (msg, ctx)
    return trans


def µr(trans: str, default: Any = None) -> tuple[str, str]:
    return _reverse_map.get(trans, default)


def translate_dpg_item(tag: str, recursive: bool = True) -> None:
    label = dpg.get_item_label(tag)
    if label:
        trans = µ(label)

        if trans == label:
            # Convert back to base language, then translate to active language
            trans = None
            reverse = µr(label)

            if reverse:
                trans = µ(*reverse)

        if trans:
            if dpg.get_item_type(tag) == "mvAppItemType::mvText":
                dpg.set_value(tag, trans)
            else:
                dpg.set_item_label(tag, trans)

    if recursive:
        for child in dpg.get_item_children(tag, slot=1):
            translate_dpg_item(child, True)
