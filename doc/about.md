# What is Yonder?

Yonder is an app I wrote for editing [Audiokinetic Wwise](https://www.audiokinetic.com/en/wwise/) soundbanks - containers of complex audio graphs used to control audio audio playback, filtering and mixing in many modern games. It's also capable of simulating a large part of the audio playback. 

!!! warning 

    Yonder was specifically created for modding recent Fromsoft titles like *Elden Ring* and *Nightreign* and may thus not work well for other games.

## Soundbanks

A soundbank contains (part of) a large tree graph, where branches define [playback behavior](soundbanks/node_types.md), and leaves define the [audio sources](soundbanks/sounds_and_music.md) to use (i.e. audio clips and music pieces). Each node can modify playback using static properties (e.g. volume, pitch, high- and lowpass filters), automated curves (e.g. fades, equalizers), and game-state dependent adjustments (e.g. [distance-based attenuation](soundbanks/attenuation.md), [RTPCs](soundbanks/rtpcs.md)). Sub-trees are activated by game [events](soundbanks/events.md) and different branches can be selected through [states and switches](soundbanks/states.md).

That's the long and short of it. The rest of this site will be dedicated to explaining soundbanks in more detail, what you can (and can't) do with [Yonder](howto/yonder.md), and how to do certain complex edits.

!!! tip 
    
    Further details can generally be found on the [Audiokinetic website](https://www.audiokinetic.com/en/documentation).
