# Music

!!! tip

    Also see the guide on how to [work with music](../guides/working_with_music.md)!

For music sources it is often desirable to have more control over their playback, e.g. (cross) fades, stateful playlists, etc. This is realized through hierarchies of specialized music containers that lead into music segments and tracks.

## Music Switch Container

> [Wwise documentation](https://www.audiokinetic.com/en/public-library/2025.1.10_9233/?source=Help&id=music_switch_container_property_editor)

Similar in purpose to _SwitchContainers_, however, they allow to use more complex decision trees that choose a child based on one or more multiple [game_parameters](game_syncs.md). They also define transition rules between children. As the name implies, these are intended for transitioning between different music tracks.

## Music Random Sequence Container

> [Wwise documentation](https://www.audiokinetic.com/en/public-library/2025.1.10_9233/?source=Help&id=defining_playback_behavior_of_music_playlist_containers)

These are comparable to _RandomSequenceContainers_, but with the ability to define multi-layered playlists with different playback/randomization modes per layer. In addition, they allow to define transition rules for their children.

## Segments & Tracks

> [Wwise documentation](https://www.audiokinetic.com/en/public-library/2025.1.10_9233/?source=Help&id=defining_playback_behavior_for_music_tracks)

Music containers will at some point lead into a _MusicSegment_ node, which by itself only defines a fixed duration and a set of markers, e.g. loop points.

Each segment can contain one or more _MusicTrack_ nodes, which will be played back in parallel and cut off once the segment duration has been reached. Music tracks can also have multiple sources, and depending on the track type, these will either be played in sequence or picked at random.

!!! note

    Soundbanks have a size limit of around 90MB, so music tracks are almost always stored as [(Prefetch-)Streaming](sounds.md#sounds) sources.

!!! info

    As far as I know, Fromsoft has never used more than one music track per segment, nor have I seen more than one source per music track; but it is nice to know what would in theory be possible.
