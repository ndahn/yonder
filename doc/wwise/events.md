# Events

Playback of sounds is controlled from the game by posting events to Wwise. These are short strings (encoded as hashes) that will cause an event node with matching name/hash to activate. Each event node has one or more actions attached that may start or stop certain sounds, set states, mute or modify busses, and more. 

In Fromsoft games, most events follow the pattern `<action>_<type><id>`, where
- `<action>` is either `Play` or `Stop`
- `<type>` is a single character to differentiate different types of sounds (e.g. `s` for sound effects, `c` for character sounds, `v` for voice lines...)
- `<id>` is a 9-digit number

!!! info

    When modifying e.g. a TAE (animation events), you will typically only specify the type and ID (or just the ID if the type is fixed). The game will then use this information to derive the full play-event name and send it to Wwise.
