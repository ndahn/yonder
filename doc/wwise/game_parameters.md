# Game Parameters

Besides using [events](events.md) for (de-)activating different subtrees of the [HIRC](soundbanks.md#hirc), there are additional means the game may utilize for more fine-grained control over playback.

## States

States can be thought of as global integer variables that nodes may listen to. Their most common use case is to apply volume, high pass or low pass modifiers on certain state values, but some nodes like [music switch containers](containers.md#music-switch-container) will also use them when deciding which children to play. States affect all listening nodes equally.

!!! example

    A typical example for a state in Elden Ring is the `FieldBattleState`. If it is set to `Battle` (or rather its [hash](../howto/hashes.md)), the active area music node will apply a negative volume modifier to the area music and remove this modifier from the area's battle music. The reverse happens when it is set to any other value.

## Switches

Switches work exactly like states, however, they work on a per-game-object basis. This way, different entities in the game can use the same sound structure and still get different effects based on their circumstances.

!!! example

    A nice example is different sounds for footsteps based on the type of ground a character is walking on. These would be organized in a single structure with a [switch container](containers.md#switch-container) selecting the child node to play based on a per-character `GroundType` switch. Since this is a switch and not a state, two game characters can walk side by side on different surfaces and still have different foot steps.

## RTPCs

RTPCs or Real-Time Parameter Control are floating point variables the game can send to Wwise. Since these don't have discrete states, they can be used to directly alter playback properties, often through a conversion curve.

!!! example

    RTPCs could for example be used to narrow the bandwidth of a low pass filter based on the player character's health. In Fromsoft titles they are also used to link the volume sliders in the settings menu to the output busses.

## Attenuation

Attenuation means modifying a sound based on a listener's position relative to its source. There are 5 parameters that drive attenuation in Wwise:

| Driver | Summary |
| ------ | ---- |
| Distance | Distance of the listener to the source in meters. |
| Angle | Used when the source sound is not omnidirectional. |
| Obstruction | When there is no direct line of sight between source and listener (e.g. hiding behind cover). |
| Occlusion | When there is no onubstructed path between source and listener (e.g. eavesdropping through a door). |
| Diffraction | How sound bends around edges. |
| Transmission | How sound transmits through objects. |

Each object can use a custom attenuation curve to apply volume modifiers, low-pass or high-pass filters based on distance and angle to the source. Some actor mixers also define a default attenuation, but only one attenuation can be active per voice.

!!! note

    The other driver parameters use global curves and cannot be changed on a per-object basis: obstruction and occlusion are defined in the [ENVS section](soundbanks.md#envs), diffraction and transmission in the [STMG section](soundbanks.md#stmg). 
