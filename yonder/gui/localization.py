import yaml
from pathlib import Path
import dearpygui.dearpygui as dpg

from yonder.util import resource_dir


ENGLISH = "English"
languages: dict[str, dict[str, str]] = {
    # The first time any item is translated its default label is stored
    # in the English dictionary
    ENGLISH: {
        "language": ENGLISH,
    }
}
_active_lang = ENGLISH


def get_active_lang() -> str:
    return _active_lang


def set_active_lang(lang: str) -> None:
    global _active_lang
    _active_lang = lang


def load_translations() -> None:
    for f in resource_dir().glob("*.yaml"):
        data = yaml.safe_load(f.read_text("utf-8"))
        lang = data.get("language", f.stem.title())
        languages[lang] = data


def safe_language_dict(path: Path, lang: str = ENGLISH) -> None:
    # Useful when creating new languages
    data = languages[lang]
    with path.open("w") as f:
        yaml.safe_dump(data, f)


def get_dictionary(group: str, lang: str) -> dict[str, str]:
    if not lang:
        lang = _active_lang

    dictionary = languages[lang]
    if group:
        return dictionary.get(group, {})
    return dictionary


def get_translation(key: str, group: str, lang: str = None, **fmt) -> str:
    if not lang:
        lang = _active_lang

    dictionary = languages[lang]
    if not dictionary:
        return

    if group:
        dictionary = dictionary.get(group, dictionary)

    trans = dictionary.get(key)
    if trans and fmt:
        trans.format(**fmt)

    return trans


def dpg_translate(
    dpg_item: str, group: str, lang: str = None, recursive: bool = True
) -> None:
    dictionary = get_dictionary(group, lang)
    if not dictionary:
        return

    tag = dpg.get_item_alias(dpg_item)

    if lang and lang != ENGLISH:
        label = dpg.get_item_label(dpg_item)
        if label:
            en = languages.setdefault(ENGLISH, {})
            if group:
                en = en.setdefault(group, {})
            if tag not in en:
                en[tag] = label

    trans = dictionary.get(tag)
    if trans:
        dpg.set_item_label(dpg_item, trans)

    if recursive:
        for child in dpg.get_item_children(dpg_item, slot=1):
            dpg_translate(child, group, lang)


class AutoStr(str):
    def __new__(cls, val: str, key: str, group: str = None, lang: str = None, **fmt):
        get_dictionary(group, ENGLISH)[key] = val
        trans = get_translation(key, group, lang, **fmt)
        obj = str.__new__(cls, trans or val)
        return obj


load_translations()
