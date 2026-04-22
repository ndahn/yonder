from __future__ import annotations
from typing import Any, Iterable
import colorsys
from dearpygui import dearpygui as dpg


class RGBA(tuple):
    def __new__(
        cls, color_or_r: int | Iterable[int], g: int = None, b: int = None, a: int = 255
    ):
        if isinstance(color_or_r, Iterable):
            if len(color_or_r) == 3:
                r, g, b = color_or_r
                a = 255
            else:
                r, g, b, a = color_or_r[:4]
            return super().__new__(cls, (r, g, b, a))

        return super().__new__(cls, (color_or_r, g, b, a))

    @classmethod
    def from_floats(cls, r: float, g: float, b: float, a: float = 1.0) -> RGBA:
        return RGBA(int(r * 255), int(g * 255), int(b * 255), int(a * 255))

    def as_floats(self) -> tuple[float, float, float, float]:
        return (self.r / 255, self.g / 255, self.b / 255, self.a / 255)

    @property
    def rgb(self) -> tuple[int, int, int]:
        return self[:2]

    @property
    def hsv(self) -> tuple[int, int, int]:
        h, s, v = colorsys.rgb_to_hsv(self.r, self.g, self.b)
        return (int(h * 255), int(s * 255), int(v * 255))

    @property
    def r(self) -> int:
        return self[0]

    @property
    def g(self) -> int:
        return self[1]

    @property
    def b(self) -> int:
        return self[2]

    @property
    def a(self) -> int:
        return self[3]

    def but(
        self, *, r: int = None, g: int = None, b: int = None, a: int = None
    ) -> RGBA:
        if r is None:
            r = self.r

        if g is None:
            g = self.g

        if b is None:
            b = self.b

        if a is None:
            a = self.a

        return RGBA(r, g, b, a)

    def mix(self, other: "tuple | RGBA", ratio: float = 0.5) -> RGBA:
        r = ratio * self.r + (1 - ratio) * other[0]
        g = ratio * self.g + (1 - ratio) * other[1]
        b = ratio * self.b + (1 - ratio) * other[2]
        a = ratio * self.a + (1 - ratio) * other[3]
        return RGBA(r, g, b, a)

    def brightness(self, brightness: int) -> RGBA:
        h, s, _ = colorsys.rgb_to_hsv(*self.as_floats()[:3])
        r, g, b = colorsys.hsv_to_rgb(h, s, brightness / 255)
        return RGBA.from_floats(r, g, b, self.a / 255)

    def __or__(self, other: "tuple | RGBA") -> RGBA:
        return self.mix(other)

    def __str__(self) -> str:
        return str(self)

    def __repr__(self) -> str:
        return f"Color {self}"


# https://coolors.co/palette/ffbe0b-fb5607-ff006e-8338ec-3a86ff
yellow = RGBA(255, 190, 11, 255)
orange = RGBA(251, 86, 7, 255)
red = RGBA(234, 11, 30, 255)
pink = RGBA(255, 0, 110, 255)
purple = RGBA(127, 50, 236, 255)
blue = RGBA(58, 134, 255, 255)
green = RGBA(138, 201, 38, 255)

white = RGBA(255, 255, 255, 255)
light_grey = RGBA(151, 151, 151, 255)
dark_grey = RGBA(62, 62, 62, 255)
black = RGBA(0, 0, 0, 255)

light_blue = RGBA(112, 214, 255, 255)
light_green = RGBA(112, 255, 162, 255)
light_red = RGBA(255, 112, 119)


# Section colors
muted_orange = RGBA(200, 120, 80, 255)
muted_blue = RGBA(80, 120, 200, 255)
muted_green = RGBA(80, 180, 120, 255)
muted_purple = RGBA(140, 90, 180, 255)
muted_yellow = RGBA(200, 180, 60, 255)
muted_teal = RGBA(60, 180, 180, 255)
muted_rose = RGBA(200, 80, 120, 255)


class themes:
    notification_frame = None
    item_default = None
    item_highlight = None
    link_button = None
    no_padding = None
    plot_blue = None
    plot_red = None


def init_themes():
    # Global theme
    bg_elements = [
        (
            dpg.mvThemeCol_WindowBg,
            dpg.mvThemeCol_ChildBg,
            dpg.mvThemeCol_PopupBg,
            dpg.mvThemeCol_TitleBg,
            dpg.mvThemeCol_TitleBgCollapsed,
            dpg.mvThemeCol_ResizeGrip,
        ),
        (
            dpg.mvThemeCol_FrameBg,
            dpg.mvThemeCol_MenuBarBg,
            dpg.mvThemeCol_ScrollbarBg,
            dpg.mvThemeCol_Button,
            dpg.mvThemeCol_Header,
            dpg.mvThemeCol_ResizeGripHovered,
            dpg.mvThemeCol_ResizeGripActive,
            dpg.mvThemeCol_Tab,
        ),
        (
            dpg.mvThemeCol_Border,
            dpg.mvThemeCol_BorderShadow,
            dpg.mvThemeCol_Separator,
            dpg.mvThemeCol_SeparatorHovered,
            dpg.mvThemeCol_SeparatorActive,
        ),
    ]

    # https://coolors.co/18181d-202229-32333c-1b97ea
    shades = [(24, 24, 29), (32, 34, 41), (50, 51, 60)]

    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(
                dpg.mvStyleVar_FrameRounding, 2, category=dpg.mvThemeCat_Core
            )

            for shade, elements in zip(shades, bg_elements):
                for elem in elements:
                    dpg.add_theme_color(elem, shade, category=dpg.mvThemeCat_Core)

        # Disabled components
        with dpg.theme_component(dpg.mvInputFloat, enabled_state=False):
            dpg.add_theme_color(dpg.mvThemeCol_Text, [168, 168, 168])
            dpg.add_theme_color(dpg.mvThemeCol_Button, [96, 96, 96])

        with dpg.theme_component(dpg.mvInputInt, enabled_state=False):
            dpg.add_theme_color(dpg.mvThemeCol_Text, [168, 168, 168])
            dpg.add_theme_color(dpg.mvThemeCol_Button, [96, 96, 96])

        with dpg.theme_component(dpg.mvInputText, enabled_state=False):
            dpg.add_theme_color(dpg.mvThemeCol_Text, [168, 168, 168])
            dpg.add_theme_color(dpg.mvThemeCol_Button, [96, 96, 96])

        with dpg.theme_component(dpg.mvCheckbox, enabled_state=False):
            dpg.add_theme_color(dpg.mvThemeCol_Text, [168, 168, 168])
            dpg.add_theme_color(dpg.mvThemeCol_Button, [96, 96, 96])

    dpg.bind_theme(global_theme)

    # Additional themes
    with dpg.theme() as themes.notification_frame:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(
                dpg.mvStyleVar_WindowPadding, 7, 0, category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_style(
                dpg.mvStyleVar_FramePadding, 4, 4, category=dpg.mvThemeCat_Core
            )

    with dpg.theme() as themes.item_default:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(
                dpg.mvThemeCol_Text, (255, 255, 255), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_Border, (0, 0, 0), category=dpg.mvThemeCat_Core
            )

    with dpg.theme() as themes.item_highlight:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(
                dpg.mvThemeCol_Text, light_green, category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_Border, light_green, category=dpg.mvThemeCat_Core
            )

    with dpg.theme() as themes.link_button:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(
                dpg.mvThemeCol_Text, light_blue, category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_Button, (0, 0, 0, 0), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_ButtonHovered,
                (255, 255, 255, 40),
                category=dpg.mvThemeCat_Core,
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_ButtonActive,
                (255, 255, 255, 80),
                category=dpg.mvThemeCat_Core,
            )

    with dpg.theme() as themes.no_padding:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(
                dpg.mvStyleVar_WindowPadding, 0, 0, category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_style(
                dpg.mvStyleVar_FramePadding, 0, 0, category=dpg.mvThemeCat_Core
            )

    with dpg.theme() as themes.plot_blue:
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(dpg.mvPlotCol_Line, blue, category=dpg.mvThemeCat_Plots)

    with dpg.theme() as themes.plot_red:
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_color(
                dpg.mvPlotCol_Line, orange, category=dpg.mvThemeCat_Plots
            )


class HighContrastColorGenerator:
    """Generates RGB colors with a certain distance apart so that subsequent colors are visually distinct."""

    def __init__(
        self,
        initial_hue: float = 0.0,
        hue_step: float = 0.61803398875,
        saturation: float = 1.0,
        value: float = 1.0,
        alpha: float = 1.0,
    ):
        # 0.61803398875: golden ratio conjugate, ensures well-spaced hues
        self.hue_step = hue_step
        self.hue = initial_hue
        self.saturation = saturation
        self.value = value
        self.alpha = alpha
        self.initial_hue = initial_hue
        self.cache = {}

    def __iter__(self):
        """Allows the class to be used as an iterable."""
        return self

    def reset(self) -> None:
        self.hue = self.initial_hue
        self.cache.clear()

    def __next__(self) -> tuple[int, int, int]:
        """Generates the next high-contrast color."""
        self.hue = (self.hue + self.hue_step) % 1
        r, g, b = colorsys.hsv_to_rgb(self.hue, self.saturation, self.value)
        return (int(r * 255), int(g * 255), int(b * 255), int(self.alpha * 255))

    def __call__(self, key: Any = None) -> tuple[int, int, int]:
        """Allows calling the instance directly to get the next color."""
        if key is not None:
            if key not in self.cache:
                self.cache[key] = next(self)
            return self.cache[key]

        return next(self)
