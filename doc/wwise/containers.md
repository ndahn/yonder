# Containers
These nodes make up the bulk of playback nodes. Their main purpose is to define which of their children to activate.

## Random Sequence Container
Picks one of its children in one of four different modes:
- *continuous sequential* plays all of its children in sequence
- *continuous step* keeps track of the last played child and plays the next one each time it's activated
- *random sequential* plays all of its children in random order (either truely random or shuffled)
- *random step* plays a random child each time it's activated


## Layer Container
Groups children into layers and allows blending between layers based on game parameters ([RTPCs](rtpcs.md)). The blending can be customized through curves.


## Switch Container
Select one of their children based on a [switch or state](states.md).


## Music Switch Container
These serve a similar purpose as switch containers, however, they allow to use more complex decision trees that choose a child based on one or more multiple [states](states.md). They also define transition rules between children. As the name implies, these are intended for transitioning between different music tracks.


## Music Random Sequence Container
Similar to random sequence containers, but with the ability to define multi-layered playlists with different playback/randomization modes per layer. In addition, they allow to define transition rules for their children.
