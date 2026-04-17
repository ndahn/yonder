from dearpygui import dearpygui as dpg


class Dialog:
    def __init__(self, tag: int | str = 0):
        if not tag:
            tag = dpg.generate_uuid()
        elif dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        self._tag = tag

    @property
    def tag(self) -> int | str:
        return self._tag

    def _t(self, suffix: str) -> str:
        return f"{self._tag}/{suffix}"
 
    @property
    def size(self) -> tuple[int, int]:
        return dpg.get_item_rect_size(self._tag)

    @property
    def width(self) -> int:
        return dpg.get_item_rect_size(self._tag)[0]
 
    @property
    def height(self) -> int:
        return dpg.get_item_rect_size(self._tag)[1]
 
