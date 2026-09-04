# Working with Music

## Clip Automations

TODO

## Transition Rules

All [music containers](../wwise/containers.md#music-switch-container) also allow you to define transition rules that are used when the container switches to a new child branch. Yonder represents these as matrices of colored squares, where each pair will have a color depending on the rule it's using (source branch on the left, target branch at the top).

To add a new transition rule, right click the cell you want to customize and select *Add Rule*. The settings here largely reflect the [Wwise documentation](https://www.audiokinetic.com/en/public-library/2025.1.10_9233/?source=Help&id=setting_source_and_destination_properties), however, if you want to setup a transition segment you'll have to do it manually for now.

!!! warning

    Make sure to use the __exact same__ *sync type* as other rules in this container, otherwise it will most likely break in-game playback.
