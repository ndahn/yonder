# Sources

Wwise can play various audio codecs, however, the most common one used is a variant of Ogg Vorbis. These are saved in `.wem` files. Like most things Wwise these files use a [hash](../yonder/hashes.md) as their filename and are shipped along the soundbank in one of three different ways:

- *embedded* - the sound is stored in the [DATA section](soundbanks.md#data) of the soundbank. This is commonly done for small sounds (<200kB).
- *streaming* - to avoid long loading times for soundbanks, larger sounds like music tracks are stored outside the soundbank. You can find them next to the soundank under `wem/XX/`, where `XX` is the first two digits of the filename.
- *prefetch streaming* - for some longer sounds like dialog, frame-accurate playback is important. In these cases, Wwise will store a tiny snippet of just a few kB inside the soundbank. This snippet can be played back immediately while the rest of the sound is being loaded from the external `wem` folder.

!!! tip

    To play back `.wem` files you can use [foobar2000](https://www.foobar2000.org/) with the [vgmstream decoder plugin](https://www.foobar2000.org/components/view/foo_input_vgmstream). Behind the curtains, Yonder uses the [vgmstream CLI](https://vgmstream.org/) to convert your wems to wav for playback.

## Sounds

Sounds are the most common type of source nodes and are basically used for everything that's not music - be it screams, sword strikes, foot steps or ocean waves. They are typically single-shot and not modified live (although they can be looped through properties).

## Music 

For music sources it is often desirable to have more control over their playback, e.g. (cross) fades, stateful playlists, etc. Part of this is realized through dedicated [music containers](containers.md#music-switch-container). These containers typically target a *Music Segment* node, which by itself only defines a fixed duration and a set of markers, e.g. loop points. 

Each segment can contain one or more *Music Track* nodes, which will be played back in parallel and cut off once the segment duration has been reached. Music tracks can also have multiple sources, and depending on the track type, these will either be played in sequence or picked at random.

!!! info

    As far as I know, Fromsoft has never used more than one music track per segment, nor have I seen more than one source per music track; but it is nice to know what would in theory be possible.
