# Node Types

Wwise includes a large variety of node and data types that influence playback and audio output in many different ways. Yonder (or rather me, arbitrarily :) ) separates these nodes into two groups: globals and playback.

## Globals

"Globals" are often referenced from other nodes without becoming part of the playback hierarchy, e.g. audio busses.

| Group                         | Summary                                                                               |
| ----------------------------- | ------------------------------------------------------------------------------------- |
| [Routing](routing.md)         | Assemble, mix and post-process audio data before sending it off the the audio driver. |
| [Game Parameters](game_parameters.md)           | Various ways that allow the game to influence audio playback beyond play/pause.       |

## Playback

"Playback" nodes on the other hand take active part in what to play and when. Through child and parent references they form tree-structures. When one of these trees is activated, the nodes it contains will decide which branches to play.

!!! info

    Most playback nodes accept properties and can react to [states and RTPCs](game_parameters.md). When a source is played back, it will use the accumulated values of all of these modifiers, e.g. volume, low-pass, high-pass, pitch...

| Group                         | Summary                                                                                              |
| ----------------------------- | ---------------------------------------------------------------------------------------------------- |
| [Events & Actions](events.md) | Immediate entrypoints for the game to start and stop individual sounds.                              |
| [Containers](containers.md)   | Manage one or more child nodes and decide upon activation which ones to play back.                   |
| [Sources](sources.md)         | These are usually leaves in the hierarchy and reference audio files inside or outside the soundbank. |
