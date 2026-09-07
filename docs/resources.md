# Resources

## DLLs

To load a dll in your game, add an entry to your [ME3 profile](https://me3.help/en/latest/configuration-reference/) like so. You can only have one entry per `[[native]]` section, so add additional ones if you want to load more dlls.

```toml
[[native]]
path=<path/to/your_lib.dll>
```

#### Unlock Music

Allows using custom state strings for [boss music](tools/boss_bgm.md#unlocking-additional-states). The source code can be found [here](https://github.com/ndahn/yonder/blob/main/unlock_wwise_states/).

[:fontawesome-regular-circle-down:&nbsp; Elden Ring](assets/downloads/unlock_wwise_states_er.dll){ .md-button .md-button-small }
[:fontawesome-regular-circle-down:&nbsp; Nightreign ](assets/downloads/unlock_wwise_states_nr.dll){ .md-button .md-button-small }

#### Read Game Syncs

Reads the game's current [game syncs](wwise/game_syncs.md) and streams them to Yonder. For switches the player character is used by default, but you can create the following entry in a file called `mana.yaml` before starting the game:

```yaml
yonder:
    # Set to any chr ID, e.g. 8000 for Torrent
    game_sync_chr_id: 8000
```

[:fontawesome-regular-circle-down:&nbsp; Elden Ring](){ .md-button .md-button-small }

## Mysteries

#### Merged Init Bank

Elden Ring and Nightreign have slightly different `init` soundbanks, which causes problems for some sounds/soundbanks (*cuuuurse you, Adel...*). This soundbank is a merge of both, and will work for both Elden Ring and Nightreign. Just place it in your `Game/sd/` folder like any other soundbank. 

*Many thanks to the lovely Raster for this!*

[:fontawesome-regular-circle-down:&nbsp; init.bnk](assets/downloads/init.bnk){ .md-button .md-button-small }
