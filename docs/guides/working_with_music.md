# Working with Music

## Clip Automations

A music track might sometimes need some adjustment to give it the chef's kiss. This could be a gradual fade-out, adjusting the volume in a small section where the drums stick out too much, or taking off the edge with a low-pass filter. All of this can be done using clip automations, without having to edit the audio source.

!!! tip

    A clever way to use clip automations is to adjust the volume levels around the loop point.

Clip automations can be setup on a *MusicTrack* node and are fairly straight forward: on the x-axis you will have the playback time in seconds, on the y-axis the adjustment of the parameter you chose. You can adjust points by dragging them on the plot, change the selected point's interpolation type, and add/delete points to adjust the curve as you wish. Note that the shown curves are educated guesses of Wwise is interpolating.

!!! tip

    The FadeIn and FadeOut parameters are amplitude multipliers, so a fade-in should start at 0 and then stay at 1, while a fade-out should start at 1 and go towards 0 at the end of the playback time. Yes, this makes them work exactly the same.

## Transition Rules

All [music containers](../wwise/music.md#music-switch-container) allow you to define transition rules that are used when the container switches to a new child branch. Yonder represents these as matrices of colored squares, where each pair will have a color depending on the rule it's using (source branch on the left, target branch at the top).

To add a new transition rule, right click the cell you want to customize and select *Add Rule*. The settings here largely reflect the [Wwise documentation](https://www.audiokinetic.com/en/public-library/2025.1.10_9233/?source=Help&id=setting_source_and_destination_properties), however, if you want to setup a transition segment you'll have to do it manually for now.

!!! warning

    Make sure to use the __exact same__ *sync type* as other rules in this container, otherwise it will most likely break in-game playback.
