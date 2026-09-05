# Setting up Attenuations

[Attenuations](../wwise/game_parameters.md) allow you to customize how a sound behaves depending on the distance and angle between source and listener. The game has standard attenuations in place for most *ActorMixers* that you automatically inherit when you select them. Only one attenuation is applied per sound, so it's easy to override the default as needed.

To setup an attenuation, select the *Bank/Isolated Node* tool and choose *Attenuation* as the node type. Choose a different ID if you like (the default will already be unique); once created you will find it in the "pinned nodes" panel.

## Distance Curves

!!! info

    All sound-specific attenuations are distance-angle-driven. Other attenuation drivers like obstruction and transmission are set globally in the `init` bank. See [Attenuations](../wwise/game_parameters.md) for details.

An attenuation is defined by one or more distance-curves, which are associated with up to [7 different properties](https://www.audiokinetic.com/fr/public-library/2025.1.10_9233/?source=Help&id=defining_attenuation_curves_for_various_object_properties#wwise_properties_for_attenuation_curves_list):

| Property | Unit | Description |
| -------- | ---- | ----------- |
| Volume | dB | The sound's loudness |
| AuxSendGame | dB | Related to [effects](../wwise/globals.md) |
| AuxSendUser | dB | Related to [effects](../wwise/globals.md) |
| LPF | Cents | Low-pass filter |
| HPF | Cents | High-pass filter |
| Spread | Cents | Related to surround sound, distributes virtual sources across spatial cannels |
| [Focus](https://www.audiokinetic.com/fr/public-library/2025.1.10_9233/?source=Help&id=focus) | Cents | Rleated to surround sound, separates spatial channels  |

Each curve has the distance on the x-axis and its property value on the y-axis, so the y-axis' units depend on the property (see [units](../wwise/units.md)). The effects applied by the attenuation are (like all modifiers) accumulated.

## Cone Params

Attenuations can also limit the sound to a cone relative to the emitter source. This behavior is defined by an inner cone, inside of which no additional attenuation applies, and an outer cone, outside of which the full cone attenuation applies. Between these two cones lies the transition zone, which linearly interpolates between zero and full cone attenuation, and no curve can be applied. The cone attenuation will be added on top of the distance attenuation for volume, LPF, and HPF.

## Applying to Sounds

Attenuations are applied through a property, which you can generally set on any playback node. Simply add the *Attenuation* property and enter your attenuation's node ID. In addition, you will want to set the following attributes:

- Enable `listener_relative_routing`
- Enable `enable_attenuation`
- Set `three_dimensional_spatialization` to either `PositionOnly` or `PositionAndOrientation`
