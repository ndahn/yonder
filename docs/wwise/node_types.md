# Node Types

Wwise includes a large variety of node and data types that influence playback and audio output in many different ways. Yonder (or rather me, arbitrarily :) ) divides these into the two groups: playback nodes and globals.

## Playback Nodes

Playback nodes are activated through [events](events.md) and take active part in deciding what to play and when. Through child and parent references they form tree-structures. When one of these trees is activated, the nodes it contains will decide which branches to play. There are common nodes for [sounds](sounds.md) and more specialized ones for [music](music.md).

!!! info

    Most playback nodes accept properties and can react to [states and RTPCs](game_parameters.md). When a source is played back, it will use the accumulated values of all of these modifiers, e.g. volume, low-pass, high-pass, pitch...

## Globals

[Globals](globals.md) are often referenced from other nodes without becoming part of the playback hierarchy, e.g. audio busses or effects. Yonder separates these from regular nodes to make browing the hierarchy a little less clunky. [States](game_parameters.md) are also stored as nodes.
