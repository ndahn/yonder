# Sound Nodes

These nodes make up the bulk of playback nodes. Their main purpose is to define which of their children to activate.

!!! info

    Containers will sometimes set a maximum number of (virtual) "voices". A voice in Wwise is an instance of a playing sound. Voices become *virtual* if their output volume is below a certain threshold, allowing Wwise to skip many computations to save resources. If a containers voice limit is reached, any additional playback requests will be ignored until it has capacity again.

## Random Sequence Container

> [Wwise documentation](https://www.audiokinetic.com/en/public-library/2025.1.10_9233/?source=Help&id=defining_how_objects_within_container_are_played)

Picks one of its children in one of four different modes:

- _continuous sequential_ plays all of its children in sequence
- _continuous step_ keeps track of the last played child and plays the next one each time it's activated
- _random sequential_ plays all of its children in random order (either truely random or shuffled)
- _random step_ plays a random child each time it's activated

## Layer Container

> [Wwise documentation](https://www.audiokinetic.com/en/public-library/2025.1.7_9143/?source=Help&id=defining_contents_and_behavior_of_blend_container)

Groups children into layers and allows blending between layers based on game parameters ([RTPCs](game_syncs.md#rtpcs)). The blending can be customized through curves.

## Switch Container

> [Wwise documentation](https://www.audiokinetic.com/en/public-library/2025.1.10_9233/?source=Help&id=defining_contents_and_behavior_of_switch_containers#defining_playback_behaviors_of_objects_within_switch_container)

Select one of their children based on a [switch or state](game_syncs.md#states).

## Sounds

Sounds are the most common type of source nodes and are basically used for everything that's not music - be it screams, sword strikes, foot steps, or ocean waves. They are typically single-shot and not modified live (although they can be looped through properties).

Wwise stores its audio data in `.wem` files, typically encoded using Ogg Vorbis. Like most things Wwise, these files use a [hash](../yonder/hashes.md) as their filename and are shipped along the soundbank in one of three different ways:

- _embedded_ - the sound is stored in the [DATA section](soundbanks.md#data) of the soundbank. This is commonly done for small sounds (<200kB).
- _streaming_ - to avoid long loading times for soundbanks, larger sounds like music tracks are stored outside the soundbank. You can find them next to the soundank under `wem/XX/`, where `XX` is the first two digits of the filename.
- _prefetch streaming_ - for some longer sounds like dialog, frame-accurate playback is important. In these cases, Wwise will store a tiny snippet of just a few kB inside the soundbank. This snippet can be played back immediately while the rest of the sound is being loaded from the external `wem` folder.

There is also a rather detailed [blog post](https://www.audiokinetic.com/en/community/blog/managing-complexity-external-sources-benefit-vo-mix/?_gl=1%2A4od0no%2A_gcl_au%2ANDAzNDM2MTYwLjE3ODg2ODE1ODQ.) exploring the pros and cons in detail.

!!! tip

    To play back `.wem` files you can use [foobar2000](https://www.foobar2000.org/) with the [vgmstream decoder plugin](https://www.foobar2000.org/components/view/foo_input_vgmstream). Behind the curtains, Yonder uses the [vgmstream CLI](https://vgmstream.org/) to convert your wems for playback, too.
