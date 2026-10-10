from typing import Any, ClassVar
from enum import Enum
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.util import logger
from yonder.enums import (
    ActionVerb,
    ActionScope,
    CurveInterpolation,
    PropID,
    ValueMeaning,
)
from yonder.types import HIRCNode, Action, Event
from yonder.types.action import get_valid_action_scopes, resolve_action_type
from yonder.game import get_selected_game
from yonder.gui.localization import μ
from yonder.gui.designer import GraphDesignerNode
from yonder.gui.widgets import add_select_node, add_state_value_input


# Verb -> property it sets or resets. Derived from the enum so there is only
# one place where the property/verb pairing lives.
_SET_PROP_VERBS: dict[ActionVerb, PropID] = {}
_RESET_PROP_VERBS: dict[ActionVerb, PropID] = {}

for _prop in (PropID.Pitch, PropID.Volume, PropID.BusVolume, PropID.LPF, PropID.HPF):
    _set_verb, _reset_verb = ActionVerb.get_property_verbs(_prop)
    _SET_PROP_VERBS[_set_verb] = _prop
    _RESET_PROP_VERBS[_reset_verb] = _prop


# The params each verb needs, which is what decides the widgets shown in the
# node's body. Everything not listed here keeps whatever the constructors in
# `Action` default to.
_VERB_PARAMS: dict[ActionVerb, tuple[str, ...]] = {
    ActionVerb.Play: (),
    ActionVerb.PlayEvent: ("event",),
    ActionVerb.Stop: (),
    ActionVerb.Pause: (),
    ActionVerb.Resume: ("master_resume"),
    ActionVerb.Mute: (),
    ActionVerb.Unmute: (),
    ActionVerb.Seek: ("position", "relative", "snap"),
    ActionVerb.SetSwitch: ("switch_group", "switch_value"),
    ActionVerb.SetState: ("state_group", "state_value"),
    ActionVerb.SetGameParameter: (
        "rtpc",
        "value",
        "value_min",
        "value_max",
        "meaning",
    ),
    **{
        verb: ("value", "value_min", "value_max", "meaning", "is_bus")
        for verb in _SET_PROP_VERBS
    },
    **{verb: ("is_bus") for verb in _RESET_PROP_VERBS},
}

# These verbs have exactly one action type, the low byte meaning something else
# than an `ActionScope` (see `resolve_action_type`)
_NO_SCOPE_VERBS = (ActionVerb.PlayEvent, ActionVerb.SetState, ActionVerb.SetSwitch)

# Verbs whose target is a param rather than the node the action is applied to,
# i.e. the event to post, the switch value to set, or the game parameter
_NO_TARGET_VERBS = _NO_SCOPE_VERBS + (ActionVerb.SetGameParameter,)


class ActionNode(GraphDesignerNode):
    """An Action that starts, stops, or otherwise modifies playback of a hierarchy."""

    node_type: ClassVar[type[HIRCNode]] = Action
    label: ClassVar[str] = "Action"
    inputs: ClassVar[tuple[str, ...]] = ("Event",)
    outputs: ClassVar[tuple[str, ...]] = ("Target",)

    def __init__(
        self,
        bnk: Soundbank,
        nid: str | int = 0,
        *,
        action_verb: ActionVerb = ActionVerb.Play,
        action_scope: ActionScope = ActionScope.TargetLocal,
    ):
        super().__init__(bnk, nid)

        self._bnk = bnk
        self._game = get_selected_game()
        self.action_verb: ActionVerb = action_verb
        self.action_scope: ActionScope = action_scope
        self.used_params: list[str] = list(_VERB_PARAMS.get(action_verb, ()))

        # Defaults mirror the ones the `Action` constructors use. The widgets
        # are built from these and write back into the same dict.
        self.params: dict[str, Any] = {
            "event": 0,
            "position": 0.0,
            "relative": False,
            "snap": False,
            "switch_group": 0,
            "switch_value": 0,
            "state_group": 0,
            "state_value": 0,
            "rtpc": 0,
            "bypass_transition": False,
            "value": 0.0,
            "value_min": 0.0,
            "value_max": 0.0,
            "meaning": ValueMeaning.Default,
            "fade_curve": CurveInterpolation.Linear,
            "master_resume": False,
            "is_bus": False,
        }

        # The group a switch/state value is picked from, by label
        self._switch_group_name: str = None
        self._state_group_name: str = None
        self._param_widgets: dict[str, Any] = {}

    def build(self, parent: str | int, pos: tuple[float, float] = None) -> None:
        super().build(parent, pos)

        # Terminals only exist once the node is built, so the initial verb has
        # to be applied from here rather than from build_body
        self._apply_verb(self.action_verb)

    def build_body(self) -> None:
        dpg.add_combo(
            [v.name for v in ActionVerb],
            default_value=self.action_verb.name,
            width=self.body_width,
            callback=self._on_action_verb_changed,
            tag=self._wtag("action_verb"),
        )
        dpg.add_combo(
            [s.name for s in ActionScope],
            default_value=self.action_scope.name,
            width=self.body_width,
            callback=self._on_action_scope_changed,
            tag=self._wtag("action_scope"),
            show=False,
        )

        dpg.add_separator()

        # One widget (or widget group) per param, shown and hidden as the verb
        # changes. Their user_data is the param they stand for.
        with dpg.group(tag=self._wtag("params")):
            self._add_param(
                "event",
                add_select_node(
                    self._bnk,
                    callback=self._on_param_changed,
                    label=µ("Event"),
                    node_type=Event,
                    textbox_width=self.body_width - 60,
                    tag=self._wtag("event"),
                    user_data="event",
                ),
            )
            self._add_param(
                "position",
                dpg.add_input_float(
                    label=µ("Position"),
                    default_value=self.params["position"],
                    min_value=0.0,
                    min_clamped=True,
                    format="%.3f",
                    callback=self._on_param_changed,
                    width=self.body_width - 60,
                    tag=self._wtag("position"),
                    user_data="position",
                ),
            )
            with dpg.tooltip(dpg.last_item(), user_data="position"):
                dpg.add_text(
                    µ("In milliseconds, or as a fraction of the duration", "tips")
                )

            self._add_param(
                "relative",
                dpg.add_checkbox(
                    label=µ("Relative"),
                    default_value=self.params["relative"],
                    callback=self._on_param_changed,
                    tag=self._wtag("relative"),
                    user_data="relative",
                ),
            )
            with dpg.tooltip(dpg.last_item(), user_data="relative"):
                dpg.add_text(µ("Treat the position as a fraction of the duration", "tips"))

            self._add_param(
                "snap",
                dpg.add_checkbox(
                    label=µ("Snap"),
                    default_value=self.params["snap"],
                    callback=self._on_param_changed,
                    tag=self._wtag("snap"),
                    user_data="snap",
                ),
            )
            with dpg.tooltip(dpg.last_item(), user_data="snap"):
                dpg.add_text(µ("Seek to the nearest marker", "tips"))

            self._add_param(
                "switch_group",
                add_state_value_input(
                    list(self._game.game_syncs.switches),
                    self._on_switch_group_changed,
                    label=µ("Group"),
                    width=self.body_width - 60,
                    tag=self._wtag("switch_group"),
                    user_data="switch_group",
                ),
            )
            self._add_param(
                "switch_value",
                add_state_value_input(
                    [],
                    self._on_param_changed,
                    label=µ("Switch"),
                    width=self.body_width - 60,
                    tag=self._wtag("switch_value"),
                    user_data="switch_value",
                ),
            )
            self._add_param(
                "state_group",
                add_state_value_input(
                    list(self._game.game_syncs.states),
                    self._on_state_group_changed,
                    label=µ("Group"),
                    width=self.body_width - 60,
                    tag=self._wtag("state_group"),
                    user_data="state_group",
                ),
            )
            self._add_param(
                "state_value",
                add_state_value_input(
                    [],
                    self._on_param_changed,
                    label=µ("State"),
                    width=self.body_width - 60,
                    tag=self._wtag("state_value"),
                    user_data="state_value",
                ),
            )
            self._add_param(
                "rtpc",
                add_state_value_input(
                    list(self._game.game_syncs.rtpcs),
                    self._on_param_changed,
                    label=µ("RTPC"),
                    width=self.body_width - 60,
                    tag=self._wtag("rtpc"),
                    user_data="rtpc",
                ),
            )
            self._add_param(
                "value",
                dpg.add_input_float(
                    label=µ("Value"),
                    default_value=self.params["value"],
                    callback=self._on_param_changed,
                    width=self.body_width - 60,
                    tag=self._wtag("value"),
                    user_data="value",
                ),
            )
            self._add_param(
                "value_min",
                dpg.add_input_float(
                    label=µ("Min"),
                    default_value=self.params["value_min"],
                    callback=self._on_param_changed,
                    width=self.body_width - 60,
                    tag=self._wtag("value_min"),
                    user_data="value_min",
                ),
            )
            self._add_param(
                "value_max",
                dpg.add_input_float(
                    label=µ("Max"),
                    default_value=self.params["value_max"],
                    callback=self._on_param_changed,
                    width=self.body_width - 60,
                    tag=self._wtag("value_max"),
                    user_data="value_max",
                ),
            )
            with dpg.tooltip(dpg.last_item(), user_data="value_max"):
                dpg.add_text(µ("Randomizes the value on every activation", "tips"))

            self._add_param(
                "meaning",
                dpg.add_combo(
                    [m.name for m in ValueMeaning],
                    default_value=self.params["meaning"].name,
                    width=self.body_width,
                    callback=self._on_param_changed,
                    tag=self._wtag("meaning"),
                    user_data="meaning",
                ),
            )
            with dpg.tooltip(dpg.last_item(), user_data="meaning"):
                dpg.add_text(µ("Whether the value replaces or offsets the current one", "tips"))

            self._add_param(
                "master_resume",
                dpg.add_checkbox(
                    label=µ("Master resume"),
                    default_value=self.params["master_resume"],
                    callback=self._on_param_changed,
                    tag=self._wtag("master_resume"),
                    user_data="master_resume",
                ),
            )
            self._add_param(
                "is_bus",
                dpg.add_checkbox(
                    label=µ("Target is a bus"),
                    default_value=self.params["is_bus"],
                    callback=self._on_param_changed,
                    tag=self._wtag("is_bus"),
                    user_data="is_bus",
                ),
            )

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        if source is self:
            if output != "Target":
                return False

            # Actions can target anything playable, a bus, or an existing node.
            # Never the "Playback" terminal though - that one is where a target
            # expects its parent, and an action is not a parent.
            return input in ("Event", "Parent") or input.startswith("Input")

        return super().link_valid(source, output, target, input)

    def validate(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> str:
        verb = self.action_verb

        if verb not in _VERB_PARAMS:
            return µ("Action verb not supported")

        try:
            resolve_action_type(verb, self.action_scope)
        except ValueError:
            return µ("Action type not supported")

        if "Event" not in input_map:
            return µ("Event not connected")

        if verb not in _NO_TARGET_VERBS and not output_map.get("Target"):
            return µ("Target not connected")

        if verb == ActionVerb.PlayEvent and not self.params["event"]:
            return µ("No event selected")

        if verb == ActionVerb.SetSwitch and not (
            self.params["switch_group"] and self.params["switch_value"]
        ):
            return µ("Switch group or value not set")

        if verb == ActionVerb.SetState and not (
            self.params["state_group"] and self.params["state_value"]
        ):
            return µ("State group or value not set")

        if verb == ActionVerb.SetGameParameter and not self.params["rtpc"]:
            return µ("No game parameter set")

        return super().validate(bnk, input_map, output_map)

    def make_node(
        self, bnk: Soundbank, input_map: dict[str, int], output_map: dict[str, int]
    ) -> Action:
        nid = self.node_id()
        target = output_map.get("Target", 0)
        verb = self.action_verb
        scope = self.action_scope
        p = self.params

        if verb == ActionVerb.Play:
            # Wwise only uses one scope for this verb
            action = Action.new_play(
                nid, target, bank_id=bnk.bank_id, fade_curve=p["fade_curve"]
            )
        elif verb == ActionVerb.PlayEvent:
            action = Action.new_play_event(nid, p["event"])
        elif verb == ActionVerb.Stop:
            action = Action.new_stop(nid, target, scope=scope)
        elif verb == ActionVerb.Pause:
            action = Action.new_pause(
                nid, target, scope=scope, fade_curve=p["fade_curve"]
            )
        elif verb == ActionVerb.Resume:
            action = Action.new_resume(
                nid,
                target,
                scope=scope,
                fade_curve=p["fade_curve"],
                master_resume=p["master_resume"],
            )
        elif verb == ActionVerb.Mute:
            action = Action.new_mute(
                nid, target, scope=scope, fade_curve=p["fade_curve"]
            )
        elif verb == ActionVerb.Unmute:
            action = Action.new_unmute(
                nid, target, scope=scope, fade_curve=p["fade_curve"]
            )
        elif verb == ActionVerb.Seek:
            action = Action.new_seek(
                nid,
                target,
                p["position"],
                scope=scope,
                relative_to_duration=p["relative"],
                snap_to_marker=p["snap"],
            )
        elif verb == ActionVerb.SetSwitch:
            action = Action.new_set_switch(nid, p["switch_group"], p["switch_value"])
        elif verb == ActionVerb.SetState:
            action = Action.new_set_state(nid, p["state_group"], p["state_value"])
        elif verb == ActionVerb.SetGameParameter:
            action = Action.new_set_game_parameter(
                nid,
                p["rtpc"],
                p["value"],
                scope=scope,
                meaning=p["meaning"],
                value_min=p["value_min"],
                value_max=p["value_max"],
                bypass_transition=p["bypass_transition"],
            )
        elif verb in _SET_PROP_VERBS:
            action = Action.new_set_prop(
                nid,
                target,
                _SET_PROP_VERBS[verb],
                p["value"],
                scope=scope,
                meaning=p["meaning"],
                value_min=p["value_min"],
                value_max=p["value_max"],
                fade_curve=p["fade_curve"],
                is_bus=p["is_bus"],
            )
        elif verb in _RESET_PROP_VERBS:
            action = Action.new_reset_prop(
                nid,
                target,
                _RESET_PROP_VERBS[verb],
                scope=scope,
                fade_curve=p["fade_curve"],
                is_bus=p["is_bus"],
            )
        else:
            raise ValueError(f"Action verb {verb.name} is not supported yet")

        # None of the verb constructors but new_play take properties
        for prop, value in self.properties.items():
            action.set_property(prop, value)

        return action

    # === Helpers =======================================================

    def _add_param(self, param: str, widget: Any) -> None:
        """Remember a param's widget and make sure it can be found by user_data."""
        self._param_widgets[param] = widget

        # DpgItem based widgets are a group that doesn't carry our user_data
        tag = getattr(widget, "tag", widget)
        if dpg.get_item_user_data(tag) != param:
            dpg.configure_item(tag, user_data=param)

    def _apply_verb(self, verb: ActionVerb) -> bool:
        """Show the widgets and terminals `verb` needs. False if unsupported."""
        params = _VERB_PARAMS.get(verb)
        if params is None:
            logger.error(f"Action verb {verb.name} not handled yet")
            return False

        # Action scope
        scopes = [] if verb in _NO_SCOPE_VERBS else get_valid_action_scopes(verb)
        scope_widget = self._wtag("action_scope")

        if scopes:
            if self.action_scope not in scopes:
                self.action_scope = scopes[0]

            dpg.configure_item(
                scope_widget,
                items=[s.name for s in scopes],
                # A single scope is not a choice, no point in showing it
                show=len(scopes) > 1,
            )
            dpg.set_value(scope_widget, self.action_scope.name)
        else:
            dpg.hide_item(scope_widget)

        # The constructors in `Action` default to different meanings depending
        # on what is being set, so follow them when the verb changes
        if verb in _SET_PROP_VERBS:
            self._set_param("meaning", ValueMeaning.Offset)
        elif verb == ActionVerb.SetGameParameter:
            self._set_param("meaning", ValueMeaning.Default)

        # Target terminal
        self.sync_terminals([] if verb in _NO_TARGET_VERBS else ["Target"], False)

        # Body widgets
        for child in dpg.get_item_children(self._wtag("params"), slot=1):
            if dpg.get_item_user_data(child) in params:
                dpg.show_item(child)
            else:
                dpg.hide_item(child)

        self.action_verb = verb
        self.used_params = list(params)
        return True

    def _set_param(self, param: str, value: Any) -> None:
        """Set a param and its widget without going through the callback."""
        self.params[param] = value
        dpg.set_value(
            self._wtag(param), value.name if isinstance(value, Enum) else value
        )

    def _update_group_values(self, param: str, values: list[str]) -> None:
        widget: add_state_value_input = self._param_widgets[param]
        widget.items = values
        if widget.string_value not in values:
            widget.value = 0
            self.params[param] = 0

    # === DPG callbacks =================================================

    def _on_action_verb_changed(
        self, sender: str, action_verb: str, user_data: Any
    ) -> None:
        if not self._apply_verb(ActionVerb[action_verb]):
            # Put the combo back to what the node actually is
            dpg.set_value(sender, self.action_verb.name)

    def _on_action_scope_changed(
        self, sender: str, action_scope: str, user_data: Any
    ) -> None:
        self.action_scope = ActionScope[action_scope]

    def _on_param_changed(self, sender: str, value: Any, param: str) -> None:
        current = self.params.get(param)

        if isinstance(value, tuple):
            # State and switch inputs report (hash, label)
            value = value[0]
        elif isinstance(current, Enum) and isinstance(value, str):
            value = type(current)[value]

        self.params[param] = value

    def _on_switch_group_changed(
        self, sender: str, switch_group: tuple[int, str], user_data: Any
    ) -> None:
        self.params["switch_group"] = switch_group[0]
        self._switch_group_name = switch_group[1]
        self._update_group_values(
            "switch_value",
            self._game.game_syncs.switches.get(self._switch_group_name, []),
        )

    def _on_state_group_changed(
        self, sender: str, state_group: tuple[int, str], user_data: Any
    ) -> None:
        self.params["state_group"] = state_group[0]
        self._state_group_name = state_group[1]
        self._update_group_values(
            "state_value",
            self._game.game_syncs.states.get(self._state_group_name, []),
        )
