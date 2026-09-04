# Globals

## Actor Mixers (AMX)
Mixers combine various voices. Their main use is to define a base set of properties, busses and effects to apply to the signal. In Fromsoft games, the common hierarchy of Actor Mixers is defined in the `cs_main` soundbank.

!!! note

    The bus a sound will be using is usually specified through the actor mixer it is attached to. When you adjust the game's volume in the settings menu (e.g. master, music, voices, sfx), this modifies a property on these busses. If you notice your custom sword clang is controlled by the *voices* volume instead of *sfx* it is because you've selected the wrong actor mixer for it.

## Busses
Wwise uses a dry/wet signal processing architecture typical for many modern audio frameworks. In this context, *dry* means the unprocessed signal that will be sent to the speakers (i.e. no additional effects applied). Part of this signal can also go to one or more auxilliary busses (*AuxBus* in yonder). These will apply additional effects like reverb to form the *wet* signal, which is mixed with the dry signal to form the final output. This way, an audio engineer can e.g. apply location-specific reverb without modifying each sound individually by controlling how much of these effect busses is mixed in.

## Effects
Effect nodes modify the audio signal in complex ways (e.g. reverb, compression, etc.). Wwise uses a plugin-based system for audio effects. Yonder has only basic support for these right now.
