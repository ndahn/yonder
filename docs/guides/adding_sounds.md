# Adding Sounds to your Game

!!! note

    This guide is specifically for setting up simple one-shot [sounds](../wwise/sounds.md). If you want to play music instead, [start reading here](../wwise/music.md).

## Preparation

To use sounds in-game, you first have to add them to a soundbank that's loded when they are supposed to play, i.e. the entity they are associated with is currently loaded. There are a few soundbanks that are always loaded: `init`, `cs_main`, `cs_smain`, and `vcmain` (1).
{ .annotate }

1. See the entry on [soundbanks](../wwise/soundbanks.md) for more information.

However, `init` shouldn't hold any sounds, `cs_main` is huge and takes patience to work with, `cs_smain` is meant for music and `vcmain` is meant for dialog; so it's generally better to create your own [custom soundbank](custom_banks.md).

Whichever way you choose, you need to decide on two things: the [sound type](../wwise/events.md#sound-types), and the ID, which together form the [event name](../wwise/events.md). While the sound type is just a way to categorize sounds, some places like FXR sounds or dialog lines only allow specific types (`s` and `v` in these cases, but depends on the game). 

!!! tip

    As usual, it is best to compare with vanilla things that in spirit already do what you want.

## Modifying the Soundbank

The easiest ways to setup your new sounds is by using the [simple sounds tool](../tools/simple_sounds.md) (or [batch sound builder](../tools/batch_sound_builder.md) if you have many sounds). Don't forget to *save* and *repack* your soundbank once you're done!

Place your modified soundbank in your mod's `Game/sd/` folder. If you have created an entirely new soundbank, see the [in-game setup](custom_banks.md#one-bank-to-rule-them-all) section to get it loaded by the game.

## Playing your Sounds

How to play your sounds very much depends on your game and use case, but to give you a general idea:

| Where | Software | How |
| ----- | -------- | --- |
| Animations | [DSAS](https://github.com/Meowmaritus/DSAnimStudio/releases) | Add a TAE 129 `Wwise_PlaySound_BySlot` event. |
| FXR | [fxr-playground](https://fxr-playground.pages.dev/) | Add a node with a []`NodeSound`](https://fxr-docs.pages.dev/classes/NodeSound) or []`EmissionSound`](https://fxr-docs.pages.dev/classes/EmissionSound) action. |
| SpEffects | [Smithbox](https://github.com/vawser/Smithbox/releases) | *TODO* |
| HKS | (text editor) | Not possible use FXR or SpEffects instead. |
| Events | [Darkscript3](https://github.com/AinTunez/DarkScript3/releases) | Use the [`PlaySE`](https://soulsmods.github.io/emedf/er-emedf.html#PlaySE) instruction. |
| Dialog & Menus | [ESDStudio](https://github.com/GompDS/ESDStudio/releases) | *TODO* |
