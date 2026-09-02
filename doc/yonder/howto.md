# How To Yonder

First things first, in order to use Yonder properly you'll want to grab and install the following programs. Yonder will ask you to locate them the first time they are needed.

- [rewwise](https://github.com/vswarte/rewwise/releases) - includes `bnk2json` for packing and unpacking soundbanks
- [vgmstream](https://vgmstream.org/) - for converting `wem` to `wav` files for playback
- [Wwise](https://www.audiokinetic.com/en/download) - for converting various audio files to `wem`

The latter two are optional (and Wwise is unfortunately not available for Linux), but will significantly improve your experience.

## First Steps

To get those juicy soundbanks you'll first have to extract them from your game's archives. For Elden Ring and Nightreign this can be done using [Nuxe](https://github.com/JKAnderson/Nuxe). The soundbanks will be placed in the `Game/sd/` folder. Check the [soundbanks overview](../wwise/soundbanks.md#important-soundbanks) to get an idea of what lives where.

Next, open one of the soundbanks from the *File* menu. The first time you do this Yonder will ask you for the location of `bnk2json`, which is part of *rewwise*. Locate it and wait for the bank to load - large soundbanks like `cs_main` can take several minutes.

## What is What?

Yonder is organized in three panels - HIRC nodes on the left, node attributes in the center, utility stuff on the right. 

The panel on the left will show you a list of [events](../wwise/events.md), [globals](../wwise/node_types.md#globals), and [bank sections](../wwise/soundbanks.md#sections). Under the events you will find a list of names and/or numbers, depending on whether the [hashes](hashes.md) are known. These nodes can be expanded to browse the rest of their associated hierarchy (see [node types](../wwise/node_types.md)). From the right-click context menu, nodes or entire subtrees can also be copied, reattached, and deleted.

The central panel's contents depend on the selected node, but will generally show the related parent and child nodes at the top, followed a swath of node-specific widgets. Note that any changes you make are applied to the node immediately.

!!! tip

    Made a change you didn't like? Yonder doesn't have a proper undo function yet; however, when switching to the *Json* panel on the right, you'll find a *Reset Node* button at the bottom. Click it and the node will be returned to the state it had the last time you selected it.

On the right you will see two tabs: a graph view, which can e used to quickly navigate the selected subtree, and a text panel with the node's attributes in `json` format. The latter can be used to modify attributes that are not exposed by Yonder as widgets (yet).

## Doing Things

Most soundbank edits will just come down to this: knowing what you want to do, and understanding how to use the various [node types](../wwise/node_types.md). That being said, Yonder includes a few utilities to make some common operations easier and setup Fromsoft-typical structures.

| Tool | Summary |
| ---- | ------- |
| [Simple Sounds](../tools/simple_sounds.md) | Setup a new play/stop pair that plays a single sound. |
| [Batch Sound Builder](../tools/batch_sound_builder.md) | Use this if you already have a bunch of simple sound files for which you want to setup events. Very useful for porting DS3 sounds. |
| [Boss Bgm](../tools/boss_bgm.md) | A custom boss needs custom music, and this tool will set it up for you. |
| [Area Bgm](../tools/area_bgm.md) | Create a new background music track playing in specific map regions. |
| [Mass Transfer](../tools/mass_transfer.md) | Let's you move sounds between soundbanks. |
| [Unmangle](../tools/unmangle.md) | Cleans up some stuff Fromsoft added that would otherwise prevent your edits from taking effect. |

!!! tip

    Once you've made some edits you need to first **save** the soundbank (which writes your edits to the extracted `soundbank.json`), then **repack** it (which converts it back to a `.bnk`). Both of these actions can be triggered from the *File* menu - a backup will be created. *Always check the terminal output to see if there are any issues!*

## The HIRC Player

Yonder now comes with a player widget that emulates part of the in-game playback. In particular, it will traverse the currently selected subtree, accumulate modifiers, and mix and play branches based on user-defined [game paramters](../wwise/game_parameters.md).

This is still experimental and I'm not sure how far I can (or want to) take it. The following Wwise things are currently *not* supported:

- effects (i.e. only the dry signal is processed)
- transition rules
- occlusion, obstruction, diffraction, transmission
- bus properties
- many container attributes that would probably be relevant...
