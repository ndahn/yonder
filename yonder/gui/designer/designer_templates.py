from __future__ import annotations
from typing import Callable, TYPE_CHECKING

from yonder import Soundbank
from . import (
    EventNode,
    ActionNode,
    AMXNode,
    RSCNode,
    LCNode,
    SoundNode,
    MSCNode,
    MRSCNode,
    MSNode,
    MTNode,
    SCNode,
)

if TYPE_CHECKING:
    from yonder.gui.dialogs.graph_designer import graph_designer_dialog


_templates: dict[str, Callable[[graph_designer_dialog, Soundbank], None]] = {}


def get_templates() -> dict[str, Callable[[], None]]:
    return dict(_templates)


def default_nodes(dlg: graph_designer_dialog, bnk: Soundbank) -> None:
    dlg.chain().node(EventNode(bnk)).to("Play/Stop", RSCNode(bnk), "Event").merge(
        lambda b: b.node(AMXNode(bnk)), "Child 0", "Playback"
    )


def simple_sound(dlg: graph_designer_dialog, bnk: Soundbank) -> None:
    dlg.chain().node(EventNode(bnk)).to("Play/Stop", RSCNode(bnk), "Event").merge(
        lambda b: b.node(AMXNode(bnk)), "Child 0", "Playback"
    ).fork(
        lambda rsc: rsc.to("Item 0", SoundNode(bnk), "Playback"),
        lambda rsc: rsc.to("Item 1", SoundNode(bnk), "Playback"),
    )


def layered_sound(dlg: graph_designer_dialog, bnk: Soundbank) -> None:
    dlg.chain().node(EventNode(bnk)).to("Play/Stop", RSCNode(bnk), "Event").merge(
        lambda b: b.node(AMXNode(bnk)), "Child 0", "Playback"
    ).to("Item 0", LCNode(bnk), "Playback").fork(
        lambda lc: lc.to("Item 0", SoundNode(bnk), "Playback"),
        lambda lc: lc.to("Item 1", SoundNode(bnk), "Playback"),
    )


def switchable_sound(dlg: graph_designer_dialog, bnk: Soundbank) -> None:
    dlg.chain().node(EventNode(bnk)).to("Play/Stop", RSCNode(bnk), "Event").merge(
        lambda b: b.node(AMXNode(bnk)), "Child 0", "Playback"
    ).to("Item 0", SCNode(bnk), "Playback").fork(
        lambda lc: lc.to("Switch 0", SoundNode(bnk), "Playback"),
        lambda lc: lc.to("Switch 1", SoundNode(bnk), "Playback"),
    )


def music_playlist(dlg: graph_designer_dialog, bnk: Soundbank) -> None:
    # Music nodes usually don't have an AMX
    dlg.chain().node(EventNode(bnk)).to("Play/Stop", MRSCNode(bnk), "Event").fork(
        lambda mrsc: mrsc.to("Item 0", MSNode(bnk), "Playback").to(
            "Track 0", MTNode(bnk), "Playback"
        ),
        lambda mrsc: mrsc.to("Item 1", MSNode(bnk), "Playback").to(
            "Track 0", MTNode(bnk), "Playback"
        ),
    )


_templates["Default"] = default_nodes
_templates["Simple Sound"] = simple_sound
_templates["Layered Sound"] = layered_sound
_templates["Switchable Sound"] = switchable_sound
_templates["Music"] = music_playlist
