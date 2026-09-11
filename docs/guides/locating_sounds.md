# Locating Sounds

Locating sounds can be tough if you don't know what you're looking for. As described on the [events page](../wwise/events.md), the game constructs short strings that are hashed and sent to Wwise, triggering various actions. These strings can be anything, but usually follow the pattern `Play_<type><number>`, where `<type>` is a Fromsoft-defined category (e.g. `c` for character, `s` for sfx, etc., see [sound types](../wwise/events.md#sound-types)), and `<number` is an arbitrary 9-digit number padded with 0s. This number often includes e.g. the character's ID in the beginning, but this is by no means required.

!!! bug

    Can't find an event by its name? Remember that Wwise uses [hashes](../yonder/hashes.md) for everything, and Yonder doesn't know the original names for all of them. Consider searching for the event's hash instead, which you can calculate using the *calc hash* tool.

Now, how do you find the sound you're looking for? It's actually best to start from the system it's used in. E.g. if it's a sound from an animation, look at it's TAE and find the corresponding sound event. 

!!! tip

    Sounds can be played from many places, not all of them immediately obvious (e.g. FXR). See [adding sounds](adding_sounds.md#playing-your-sounds) for more info.

Once you know the ID you need to find the soundbank it's located in. If it's any kind of NPC, boss or enemy, it will probably reside in that entity's soundbank (e.g. Artorias has the character ID 7720, and all his sounds are in `cs_c7720.bnk`). Spoken dialog can generally be found in one of the `sd/<language>/vc<number>` banks, where the number corresponds to the NPC ID. If you can't find it anywhere else, your sound is probably in `cs_main`. See the [soundbanks](../wwise/soundbanks.md#important-soundbanks) page for a broader overview.

If you are interested in the soundfile itself, it is now merely a matter of descending down the subtree and finding the *Sound* nodes you are interested in. They will list the `wem` file in use and also allow you to change it for another one, should you so desire.

## Locating Music

??? tip

    In case you really just want to replace some existing music: Yonder [includes a tool](../tools/replace_music.md) for this very purpose!

Music doesn't work like other sounds. For starters, all music is stored next to the soundbanks in `sd/wem/`, and is triggered from a single event found inside the `cs_smain` (sss!) soundbank: `Play_m000000000`. Inside is a *MusicSwitchContainer*, which blends between different music pieces based on a decision tree controlled by [states](../wwise/game_syncs.md#states).

!!! tip

    To better understand what happens inside the soundbank when playing music, you probably want to read the guide on [working with music](working_with_music.md).

In order to find your music piece, open said *MusicSwitchContainer*, then unfold the decision tree based on the states you're interested in. You will typically see some branches labeled `*` - these are wildcards and will be active when the state's value matches none of the other branches at this level. 

So if you are interested in a particular area's background music, you'd unfold branches until you find the `BgmPlaceType` branch, then pick a branch corresponding to your area and go from there. However, the label for some state hashes may again be unknown to Yonder - these will appear with their hash towards the end of the list. Once you reach a *MusicTrack* the procedure is the same as for sounds.

!!! info

    Fromsoft usually sets up their music as [PrefetchStreaming](../wwise/sounds.md#sounds). This means that a tiny piece of the song will be stored inside the soundbank (so it can be played immediately), while the actual file is stored outside.
