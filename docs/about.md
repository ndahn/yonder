# What is Yonder?

Yonder is an app I wrote for editing [Audiokinetic Wwise](https://www.audiokinetic.com/en/wwise/) soundbanks - containers of complex audio graphs used to control audio audio playback, filtering and mixing in many modern games. It's also capable of simulating a large part of the audio playback. 

!!! warning 

    Yonder was specifically created for modding recent Fromsoft titles like *Elden Ring* and *Nightreign* and may thus not work well for other games. Please note that Dark Souls 3 and earlier titles used other engines like *fmod* which Yonder does not support.

## Soundbanks

A [soundbank](wwise/soundbanks.md) contains (part of) a large tree graph, where branches define [playback behavior](wwise/containers.md), and leaves define the [audio sources](wwise/sources.md) to use (i.e. audio clips and music pieces). Each node can modify playback using static properties (e.g. volume, pitch, high- and lowpass filters), automated curves (e.g. fades, equalizers), and game-state dependent adjustments (e.g. distance-based attenuation, RTPCs, and other [game parameters](wwise/game_parameters.md)). Sub-trees are activated by game [events](wwise/events.md) and different branches will start and stop their children based on the current game state.

> *But Mana, I can't possibly read all of this!* (1)
{ .annotate }

1. Yes you can :raised_eyebrow: At the very least, read the pages I wrote about the various [node types](wwise/node_types.md) - *all of them* :knife:

That's the long and short of it. The rest of this site will be dedicated to explaining soundbanks in more detail, what you can (and can't) do with [Yonder](yonder/howto.md), and how to do certain complex edits.

!!! tip 
    
    Further details can generally be found on the [Audiokinetic website](https://www.audiokinetic.com/en/documentation).
