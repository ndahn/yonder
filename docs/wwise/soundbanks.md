# Soundbanks

A soundbank is a binary file in Audiokinetik's prorprietary format that organizes information in various sections. The most important sections are HIRC (Hierarchy), where playback graphs are stored, and DATA, which contains (most of) the audio data.

!!! info

    For now, Yonder does not parse the raw soundbanks and instead relies on [rewwise/bnk2json](https://github.com/vswarte/rewwise/), which extracts the audio data as `.wem` files and the other sections into a large `.json`.

## Important Soundbanks

In recent Fromsoft games, soundbanks were organized as follows:

| Bank       | Description                                                                    |
| ---------- | ------------------------------------------------------------------------------ |
| `init`     | Busses and most project-wide sections.                                         |
| `cs_main`  | Character sounds that should always be loaded as well as ambience soundscapes. |
| `cs_smain` | All music tracks, including boss themes.                                       |
| `cs_cXXXX` | Character-specific sounds.                                                     |
| `vcXXX`    | Character-specific (localized) voice lines.                                    |
| `cs_mXX`   | Map-specific sounds.                                                           |
| `cs_smXX`  | Sounds for cutscenes (by map ID).                                              |
| \*         | Others will usually be game-object specific, e.g. `aeg` for game assets.       |

## Sections

### BKHD

_Bank Header Section_ - soundbank metadata, e.g. name, version, project, etc.

### DATA

_Audio Data Section_ - stripped audio data, typically in Ogg Vorbis format.

### DIDX

_Data Index Section_ - index and metadata for the DATA section.

### ENVS

_Sound Environment Section_ - curves for altering sounds based on obstruction and occlusion.

### FXPR

_Effects Properties Section_ - unknown for now beyond what can be guessed from the name.

### HIRC

_Hierarchy Section_ - graphs of playback nodes like containers, events, audio sources, states, etc. This is the main section you will interact with in Yonder. See [node types](index.md) for more details.

### INIT

_Init Section_ - lists (effect) plugins used by this soundbank.

### PLAT

_Platform Section_ - platform specific metadata.

### STID

_Short ID (?) Section_ - contains references to other soundbanks that may be referenced by nodes in this soundbank.

### STMG

_State Management Section_ - defines transition times for states and switches. Also includes acoustic texture presets, which define diffraction and transmission parameters.
