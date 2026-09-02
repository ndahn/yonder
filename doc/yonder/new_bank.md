# Adding a New Soundbank

If you want to add an entirely new soundbank, you should start by creating an empty one from Yonder's *File* menu. Make sure to choose an [appropriate name](../wwise/soundbanks.md#important-soundbanks) for your use case. Afterwards you can edit it just like any other soundbank.

!!! warning

    Soundbanks have internal references to themselves, namely via the *Play* action node. If you want to rename your soundbank, changing the filename is __not__ enough. Use the *Rename* tool instead from the *Bank* menu, and it will update all affected nodes for you.

## What Goes Where

While you do have a lot of freedom with how you fill your soundbank, there are a couple of structures that can only live in specific soundbanks (*until I crack the code :3*):

- *Music* - always goes into `cs_smain` (s!)
- *Ambience* - always goes into `cs_main`

The game also follows hardcoded [naming schemes](../wwise/soundbanks.md) that you have to follow, and only keeps soundbanks loaded that it currently needs. This generally includes the `init`, `cs_main`, `cs_smain`, and `vcmain` banks. Additional banks are loaded based on the present characters, assets, maps, etc. These usually have an entry in the `regulation.bin` telling the game which soundbank(s) to load for this entity.

| Type | Param |
| ---- | ----- |
| Character (sounds) | `NpcParam` |
| Character (dialog) | *TODO* |
| Map | *TODO* |
| Asset | *TODO* |
| Cutscene | *TODO* |

## One Bank to Rule Them All

Many people (like me) like to create a general soundbank which stores most/all sounds for one mod. There is nothing special about such a soundbank other than that it needs to be loaded at all times. Depending on the game there are a few common ways to do this:

- __Elden Ring (1.17+):__ give your soundbank a unique character ID (e.g. `cs_c0010`) and load it on *all* Torrent variants in `NpcParam`: 8002, 8003, 8004, 8005 (and any custom ones). As an alternative, you can use [this dll by Shiki](https://github.com/KamiyamaShiki0704/ERSoundBankLoader/releases).
- __Elden Ring (<1.17.0):__ give your soundbank a unique character ID (e.g. `cs_c0010`) and load it on Torrent's `NpcParam` 8000. The above dll will also work.

- __Nightreign:__ *TODO*
- __Armored Core 6:__ *TODO*
