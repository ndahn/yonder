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

<!-- prettier-ignore -->
| Section | Description |
| ------- | ----------- |
| BKHD (Bank Header) | Soundbank metadata, e.g. name, version, project, etc. |
| DATA (Audio Data) | Stripped audio data, typically in Ogg Vorbis format. |
| DIDX (Data Index) | Index and metadata for the DATA section. |
| ENVS (Sound Environment) | Curves for altering sounds based on obstruction and occlusion. |
| FXPR (Effects Properties) | Unknown for now beyond what can be guessed from the name. |
| HIRC (Hierarchy) | Graphs of playback nodes like containers, events, audio sources, states, etc. This is the main section you will interact with in Yonder. See [node types](index.md) for more details. |
| INIT (Init) | Lists (effect) plugins used by this soundbank. |
| PLAT (Platform) | Platform specific metadata. |
| STID (Short ID (?)) | Contains references to other soundbanks that may be referenced by nodes in this soundbank. |
| STMG (State Management) | Defines transition times for states and switches. Also includes acoustic texture presets, which define diffraction and transmission parameters. |
