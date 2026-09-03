# Boss Music

Boss tracks are regular music tracks with complications. It's worth considering the following:

- should your boss theme play an intro before going into the loop?
- does your boss have additional phases and if so, how many?

Yonder can set all of this up for you (in the Fromsoft-typical fashion), but everything you add will require additional effort and attention to detail.

!!! tip

    Highly recommend you read up on [music containers](../wwise/containers.md#music-switch-container) and [sources](../wwise/sources.md#music) before you continue.

## BgmEnemyType

As briefly described in the section about [custom banks](../yonder/new_bank.md#what-goes-where), in Fromsoft games all music lives under a single *MusicSwitchContainer* which transitions between music pieces using a decision tree that's reading global [states](../wwise/game_parameters.md#states). For this reason, music can *only* be added to the `cs_smain` (s!) for now. The state that causes the container to switch to boss music is called `BgmEnemyType` - if it's set to a value associated with a boss bgm the boss music plays, otherwise the decision is left to other state variables (e.g. `BgmPlaceType` for different maps).

!!! tip

    To find and browse the music decision tree, open the `cs_smain` (sss!) soundbank and unfold the `Play_m000000000` event. You will find a music switch container with several dozen children. Open it and let it load, then unfold the *Decision Tree* widget.

When setting up a new boss bgm you need to choose a string it should react to. This can be your boss' *chr ID*, it's name, or anything else as long as you're able to remember it. Write it down somewhere. *No, really - do it*.

!!! warning

    Unfortunately, for whatever reason Fromsoft has decided to hardcode *and* validate the strings that are allowed to be used for boss themes. However, there are a couple of unused ones that can be used straight away (depending on the game). Keep an eye out for "Reserved" strings. Yonder also provides a `dll` that allows you to use arbitrary strings - this is described [further down](#unlocking-additional-states).

## Trims and Loop Points

Even if you don't want any extras, you probably still want to trim your song and define where it should loop. To adjust these, simply drag the red and green markers on the track view (by default they will be placed at the very beginning and end). You can test your loop by enabling the *Loop* and *Test* checkboxes, which will cause yonder to only play a few seconds around the loop on repeat.

!!! info

    In Yonder, trims directly change the music segment's duration, making it difficult to manage multiple tracks within one segment. This came about because I didn't really understand how these work. This will need an overhaul in the future, but since Fromsoft never uses this it's not a priority for now.

## Intros

An intro plays the first part of a track before the loop-start point once and then enters the loop. If enabled, Yonder will do exactly that: setup the part between begin-trim and loop-start as an intro, then setup a segment with the actual loop. This is done using a [MusicRandomSequenceContainer](../wwise/containers.md#music-random-sequence-container) with a playlist where the first playlist item is marked as a *loop base*.

## Boss Phases

When adding additional audio files to the boss bgm tool they are setup as additional boss phases (also known as heatup or HU). Each file past the first will become one additional heatup track. Fromsoft allows for at least 2 heatup phases in Elden Ring (e.g. Malenia), 3 in Nightreign (Straghess). Music phases are controlled via [EMEVD](#emevd) which sets the `BossBattleState` Wwise state.

## Transition Rules

Once the tool has finished its work you will find that both the created *MusicSwitchContainer* and *MusicRandomSequenceContainer* (small) matrices of colored squares. Those are the transition rules between their children, and each pair will have a color depending on the rule it's using.

## Game Setup

Boss music is controlled through EMEVD, Fromsoft's event scripting language, which you can edit using [Darkscript3](https://github.com/AinTunez/DarkScript3/releases). There are several [very nice tutorials](https://www.soulsmodding.com/doku.php?id=tutorial:intro-to-elden-ring-emevd) on how to write EMEVD (or rather MattScript), but the two instructions you want to look out for are [`SetBosBGM`](https://soulsmods.github.io/emedf/er-emedf.html#SetBossBGM) and [`SetFieldBattleBGMHeatUp`](https://soulsmods.github.io/emedf/er-emedf.html#SetFieldBattleBGMHeatUp). 

These instructions __don't__ set the `BgmEnemyType` or `BossBattleState` directly. For the `SetFieldBattleBGMHeatUp` you pass it a "threat level" integer (a number between 0 and ~50). This will be mangled into a string like *FieldBoss_ThreatLevel15* and is meant for generic bosses open-world that don't have a unique theme.

More interestingly, of course, is `SetBossBGM`, which is used for unique boss themes. Still, you don't pass it a string - instead you give it an ID which maps to a row in the `WwiseValueToStringParam_BgmBossChrIdConv` param in the regulation bin, which then contains the actual string which is used to set the Wwise state. However, as mentioned above, unless you're using a [dll](#unlocking-additional-states), only the predefined strings can be used, which leaves you with 8 unused "Reserved" states in Elden Ring and 1 (*2?*) in Nightreign.

To activate a heatup phase you don't need to do anything extra. Simply pass e.g. `BossBGMState.HeatUp` to the `SetBossBGM` instruction instead of `BossBGMState.Start/Stop/etc.`.

## Unlocking Additional States


