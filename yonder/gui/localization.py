import yaml
import logging
from pathlib import Path
from functools import wraps
import inspect
from dearpygui import dearpygui as dpg

from yonder.util import resource_dir, logger


ENGLISH = "English"
languages: dict[str, dict[str, str]] = {
    # The first time any item is translated its default label is stored
    # in the English dictionary
    ENGLISH: {
        "language": ENGLISH,
    }
}
_active_lang = ENGLISH
_lang_log_level = logging.DEBUG + 5
logging.addLevelName(_lang_log_level, "I18N")


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
    if not value:
        return

    if not path or not isinstance(path, str):
        return

    keys = path.split("/")
    if len(keys) == 1:
        return

    key_dict = languages[ENGLISH]
    for key in keys[1:-1]:
        # Ignore indices
        key = key.split(":")[0]
        key_dict = key_dict.setdefault(key, {})

    trans_key = keys[-1].split(":")[0]
    if trans_key not in key_dict:
        key_dict[trans_key] = value


def translate(default: str, path: str, lang: str = None, **fmt) -> str:
    if not path or not isinstance(path, str):
        if isinstance(default, str):
            return default.format(**fmt)
        return default

    _update_default_dict(path, default)

    if not lang:
        lang = _active_lang

    lang_dict = languages[lang]
    if not lang_dict:
        if isinstance(default, str):
            return default.format(**fmt)
        return default

    # Paths will follow the pattern <uid>/[subgroups]/widget_tag
    keys = path.split("/")
    if len(keys) == 1:
        # If they do not, don't translate them
        if isinstance(default, str):
            return default.format(**fmt)
        return default

    for k in keys[1:-1]:
        # Ignore indices
        k = k.split(":")[0]
        lang_dict = lang_dict.get(k)
        if not lang_dict:
            break
    else:
        trans_key = keys[-1].split(":")[0]
        trans = lang_dict.get(trans_key)
        if isinstance(trans, str):
            # Entire path resolved
            return trans.format(**fmt)
        elif trans is not None:
            logger.log(
                _lang_log_level,
                translate(
                    "Translation of {name} led to non-dict entry of type {result}",
                    "log_translation_invalid_key",
                    name=path,
                    result=type(trans),
                ),
            )
        else:
            logger.log(
                _lang_log_level,
                translate(
                    "Failed to translate {name}", "log_translation_failed", name=path
                ),
            )

    if isinstance(default, str):
        default = default.format(**fmt)

    return default


def _dpg_translate_label(dpg_func):
    @wraps(dpg_func)
    def inner(*args, **kwargs) -> str:
        # There is a short delay before widgets expose their configuration correctly,
        # so we work on the arguments instead
        alias = kwargs.get("tag")
        if alias:
            label = kwargs.get("label")
            if label:
                _update_default_dict(alias, label)
                trans = translate(None, alias)
                if trans:
                    kwargs["label"] = trans

        return dpg_func(*args, **kwargs)

    return inner


def _dpg_translate_value(dpg_func):
    @wraps(dpg_func)
    def inner(*args, **kwargs) -> str:
        # There is a short delay before widgets expose their configuration correctly,
        # so we work on the arguments instead
        alias = kwargs.get("tag")
        if alias:
            value = kwargs.get("default_value")

            if isinstance(value, str):
                _update_default_dict(alias, value)
                trans = translate(None, alias)
                if trans:
                    kwargs["default_value"] = trans

            elif args and isinstance(args[0], str):
                _update_default_dict(alias, value)
                trans = translate(None, alias)
                if trans:
                    args = (trans,) + tuple(args[1:])

        return dpg_func(*args, **kwargs)

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
    if tag:
        trans = translate(None, tag, lang)
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
