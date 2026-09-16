# What is this?

This dll let's yonder read a game's live Wwise states. It is intended for playback, modding and debugging. It currently has no means to influence the game's state - have a look at [Wwise State](https://github.com/Dasaav-dsv/wwise-state/) if you are interested in that instead.


# How does it work?

Wwise exposes several functions as part of its public API for querying game syncs: `GetRTPCValue`, `GetState`, `GetSwitch`. When a trigger arrives on the port this dll listens on, it queries these functions for the game syncs specified in the `gamesyncs` yaml file, then replies to the sender with a json blob like below:

```json
{
    "game_object_id": <u32>,
    "rtpcs": {
        <rtpc1_hash>: <rtpc1_value_f32>,
        ...
    },
    "states": {
        <state1_hash>: <state1_value_hash>,
        ...
    },
    "switches": {
        <switch1_hash>: <switch1_value_hash>,
        ...
    }
}
```

RTPCs and switches can be game-object specific. By default this dll will check for game-object 0 (typically the player). You can change this by placing the `yonder_live_states.yaml` configuration file next to the dll and adjusting it as needed.


# How can I use it?

Place this dll together with one (*and only one!*) of the `gamesyncs` yaml files somewhere you can find it. If you are using [me3](https://me3.help/) (you should!) you can then add the following lines to your profile:

```toml
[[native]]
path="path/to/yonder_live_states.dll"
```

The states can then be used to control playback of Yonder's HIRC player. See the [documentation](https://ndahn.github.io/yonder/yonder/playback/) for details.
