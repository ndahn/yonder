import time
from dearpygui import dearpygui as dpg

from yonder.util import resource_dir


_texture_w: int = 0
_texture_h: int = 0


def yay(fadeout: float = 2.0):
    global _texture_w, _texture_h

    tag = dpg.generate_uuid()

    if not dpg.does_item_exist("yonder_yay"):
        with dpg.texture_registry():
            img_path = resource_dir() / "yay.png"
            w, h, ch, data = dpg.load_image(str(img_path))
            dpg.add_static_texture(w, h, data, tag="yonder_yay")
            _texture_w = w
            _texture_h = h

    fadeout_start = time.time()

    def fadeout_cb() -> None:
        t = time.time() - fadeout_start
        if t < fadeout:
            alpha = 255 - int(t / fadeout * 255)
            dpg.configure_item(f"{tag}_overlay", color=(255, 255, 255, alpha))
            dpg.set_frame_callback(dpg.get_frame_count() + 1, fadeout_cb)
        else:
            dpg.delete_item(tag)

    vw = dpg.get_viewport_width()
    vh = dpg.get_viewport_height()
    x0 = (vw - _texture_w) / 2
    y0 = (vh - _texture_h) / 2
    x1 = vw - x0
    y1 = vh - y0
    
    with dpg.viewport_drawlist(front=True, tag=tag):
        dpg.draw_image("yonder_yay", (x0, y0), (x1, y1), tag=f"{tag}_overlay")

    fadeout_cb()
