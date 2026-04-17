import yaml
from pathlib import Path
from functools import wraps
import inspect
import dearpygui.dearpygui as dpg

from yonder.util import resource_dir, logger


ENGLISH = "English"
languages: dict[str, dict[str, str]] = {
    # The first time any item is translated its default label is stored
    # in the English dictionary
    ENGLISH: {
        "language": ENGLISH,
    }
}
_active_lang = "ENGLISH"


def get_available_languages(prefer_native: bool = True) -> list[str]:
    ret = []

    for lang in languages.values():
        label = None
        
        if prefer_native:
            label = lang.get("language_native")
        
        if not label:
            label = lang["language"]

        ret.append(label)

    return ret


def get_active_lang(prefer_native: bool = True) -> str:
    if prefer_native:
        lang = languages[_active_lang].get("language_native")
        if lang:
            return lang

    return _active_lang


def set_active_lang(lang: str) -> None:
    global _active_lang

    if lang not in languages:
        for key, data in languages.items():
            if lang == data.get("language_native"):
                lang = key
                break
        else:
            raise ValueError(f"Unknown language {lang}")

    _active_lang = lang


def _update_default_dict(path: str, value: str) -> None:
    keys = path.split("/")
    
    if len(keys) == 1:
        return

    key_dict = languages[ENGLISH]
    for key in keys[1:-1]:
        key_dict = key_dict.setdefault(key, {})

    if keys[-1] not in key_dict:
        key_dict[keys[-1]] = value


def translate(default: str, path: str, lang: str = None, **fmt) -> str:
    if not lang:
        lang = _active_lang

    if lang == ENGLISH:
        return default

    dictionary = languages[lang]
    if not dictionary:
        return

    # Paths will follow the pattern <uid>/[subgroups]/widget_tag
    keys = path.split("/")
    if len(keys) == 1:
        # If they do not don't translate them
        return None
    
    key_dict = dictionary
    for k in keys[1:-1]:
        key_dict = key_dict.get(k)
        if not key_dict:
            break
    else:
        trans = key_dict.get(keys[-1])
        if isinstance(trans, str):
            # Entire path resolved
            return trans.format(**fmt)
        elif trans is not None:
            logger.warning(
                f"Translation of {path} led to non-dict entry of type {type(trans)}"
            )

    # Try to resolve against the language's base dictionary
    trans = dictionary.get(keys[-1])
    if trans:
        return trans.format(**fmt)
    
    logger.warning(f"Failed to translate {path}")
    return default


def _dpg_translate_label(dpg_func):
    @wraps(dpg_func)
    def inner(*args, **kwargs):
        tag = dpg_func(*args, **kwargs)

        if _active_lang == ENGLISH:
            return tag

        alias = dpg.get_item_alias(tag)
        if alias:
            label = dpg.get_item_label(tag)
            if label:
                trans = translate(None, alias)
                if trans:
                    # Store the default widget label in our defaults dict
                    _update_default_dict(alias, label)
                    dpg.set_item_label(tag, trans)

        return tag

    return inner


def _dpg_translate_value(dpg_func):
    @wraps(dpg_func)
    def inner(*args, **kwargs):
        tag = dpg_func(*args, **kwargs)

        if _active_lang == ENGLISH:
            return tag

        alias = dpg.get_item_alias(tag)
        if alias:
            value = dpg.get_value(tag)
            if value:
                trans = translate(None, alias)
                if trans:
                    _update_default_dict(alias, value)
                    dpg.set_value(tag, trans)

        return tag

    return inner


def apply_dpg_decorators() -> None:
    # Apply the decorators to all dearpygui functions where it matters
    for name in dir(dpg):
        if name.startswith("_"):
            continue

        obj = getattr(dpg, name)

        # Only wrap callables
        if not callable(obj):
            continue

        try:
            sig = inspect.signature(obj)
        except (ValueError, TypeError):
            continue

        if name == "add_text":
            # add_text will ignore the label and only display its value instead
            setattr(dpg, name, _dpg_translate_value(obj))
        elif "label" in sig.parameters:
            # Wrap any widget function that accepts a label argument
            setattr(dpg, name, _dpg_translate_label(obj))


def translate_dpg_items(
    dpg_item: str, lang: str = None, recursive: bool = True
) -> None:
    tag = dpg.get_item_alias(dpg_item)
    trans = translate(None, tag)

    if trans:
        if dpg.get_item_type(dpg_item) == "mvText":
            dpg.set_value(dpg_item, trans)
        else:
            dpg.set_item_label(dpg_item, trans)

    if recursive:
        for child in dpg.get_item_children(dpg_item, slot=1):
            translate_dpg_items(child, lang)


def load_translations() -> None:
    for f in resource_dir().glob("localization/*.yaml"):
        data = yaml.safe_load(f.read_text("utf-8"))
        lang = data.setdefault("language", f.stem.title())
        languages[lang] = data


def save_language_dict(path: Path, lang: str = ENGLISH) -> None:
    # Useful when creating new languages
    data = languages[lang]
    with path.open("w") as f:
        yaml.safe_dump(data, f)
