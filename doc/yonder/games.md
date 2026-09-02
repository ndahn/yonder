# Game Presets

 Parts of the "upper hierarchy", specifically actor mixers and busses, are stored in the `cs_main` and `init` banks, the former taking several minutes to load. These nodes are generally stable across versions, so Yonder simply ships with the important information so users can make appropriate choices. The tradeoff is that this information is game-specific. Furthermore, [States, RTPCs](../wwise/game_parameters.md#rtpcs), and a couple other freeform strings are game-specific, too.

When opening a soundbank, Yonder will try to guess the game it's from based on its file path, nearby `regulation.bin`, and a couple other cues. You can also manually choose the game presets from the *Bank* menu at the top. 

!!! info

    Currently, only *Elden Ring* and *Nightreign* are properly supported. Support for *Armored Core 6* could be added in the near future if someone provides me the files. Still, even if your game is not supported you can type in the strings/references manually. You just won't have a list of valid/typical values.
