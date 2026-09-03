# Audio Playback

Yonder currently has two audio players: the legacy one works well, but only plays source nodes. Whenever you see a visualized audio file it's the legacy player being used. The HIRC player on the other hand plays entire hierarchies and simulates a large chunk of in-game audio playback, but is still new and probably has quite a few bugs. They will probably be merged at some point.

## The HIRC Player

Yonder now comes with a player widget that emulates part of the in-game playback. In particular, it will traverse the currently selected subtree, accumulate modifiers, and mix and play branches based on user-defined virtual game state. In particular you can control the following:

- global and per-voice volume
- frequency equalizer (game-specific presets will be added later)
- [game paramters](../wwise/game_parameters.md)
- listener distance and angle from the source

All of this is still experimental and I'm not sure how far I can (or want to) take it. The following Wwise things are currently *not* supported:

- effects (i.e. only the dry signal is processed)
- transition rules (except for fade durations)
- occlusion, obstruction, diffraction, transmission
- bus properties
- many container attributes that would probably be relevant...
