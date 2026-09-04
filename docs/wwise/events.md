# Events & Actions

Playback of sounds is controlled from the game by posting events to Wwise. These are short strings (encoded as hashes) that will cause an event node with matching name/hash to activate. Each event node has one or more actions attached that may start or stop certain sounds, set states, mute or modify busses, and more. 

In Fromsoft games, most events follow the pattern `<action>_<type><id>`, where
- `<action>` is either `Play` or `Stop`
- `<type>` is a single character to differentiate different types of sounds (e.g. `s` for sound effects, `c` for character sounds, `v` for voice lines...)
- `<id>` is a 9-digit number

| Type | Name (1) |
| ---- | ---- |
| `a` | Environment |
| `c` | Character |
| `f` | Menu |
| `o` | Object |
| `p` | CutsceneSe |
| `s` | Sfx |
| `m` | Bgm |
| `v` | Voice |
| `x` | FloorMaterialDetermined |
| `b` | ArmorMaterialDetermined |
| `i` | Phantom |
| `y` | MultiChannelStreaming |
| `z` | MaterialRelated |
| `e` | FootEffect |
| `g` | GeometryAsset |
| `d` | DynamicDialog |

{ .annotate }

1. These names and type characters are valid for Elden Ring and Nightreign. While past games used similar patterns, Fromsoft has and will make changes depending on the game.

!!! info

    When modifying e.g. a TAE (animation events), you will typically only specify the type and ID (or just the ID if the type is fixed). The game will then use this information to derive the full play-event name and send it to Wwise.

## Actions

When an event is activated, it triggers all of its actions, which most commonly include a *Play* or *Stop* action to (de-)activate part of the hierarchy. Actions can also be used to mute or "duck" busses (i.e. lower their volume for the duration of the event), set [game parameters](game_parameters.md), stop other sounds, etc. Depending on the action type these can also make exceptions, and it is even possible to in turn trigger other events (*allowing for some truely cursed setups if you're willing to go the extra mile*).
