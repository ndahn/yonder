# The Misty Shores of Yonder

> [!TIP]
> A tool for editing Wwise soundbanks, primarily developed for Elden Ring & Nightreign. 
> Now with [documentation](https://ndahn.github.io/yonder/)!

![](docs/assets/images/yonder.png)

---

## What can you do?
Yonder provides a comfortable way to make low- and medium-level edits. This includes:

- playback sounds and change loop/transition markers
- transfer sound hierarchies between soundbanks
- create entirely new event structures
- add boss music tracks and boss phase transitions
- add area music tracks with custom decision trees
- add or remove sounds of existing events
- edit properties like volume, low/high pass, pitch, ...
- mass convert .wav files to .wem and vice versa
- playback of sound hierarchies, including layers
- and SO much more >.<

Despite my best efforts, it is by no means as feature rich and exhaustive as Wwise (and I don't think it will ever get there), but it makes a tedious and error prone task a lot more comfortable. 

## Building your own Tools
Yonder was originally written as a library providing classes and functions to make working with soundbanks more convenient.

To get started, I suggest you take a look at the code in [convenience.py](yonder/convenience.py) which will cover a lot of the functionality. The most central code parts can be found in the [soundbank.py](yonder/types/soundbank.py), [node.py](yonder/types/base_types.py), and [hirc_node.py](yonder/types/hirc_node.py) units. I did not add proper documentation (yet), so if you need help, feel free to reach out.

## A Word on AI
95% of Yonder was written by me by hand without the help of any AI tools. The remaining 5% are some of the more tedious widgets and some of the audio math that I lack understanding of. I don't expect others to do the same, but the least anyone can do is make a [conscious decision](CONTRIBUTING.AI.md) on what they let AI do for them.

## Future Work
If you have an earthshattering need for a particular feature in mind, it's best to create an issue here on Github. In case your burning desire doesn't go *that* far after all, feel free to contact me on the [?ServerName?](https://discord.gg/wzMynmW) discord *@Managarm*.

# Hall of Fame
This app would not have been possible without the invaluable help and prior work by [Vswarte](https://github.com/vswarte/), **Shion** and [DaSaav](https://github.com/Dasaav-dsv/). A huge shoutout also goes to **Themyys**, **Raster**, **LittleBear**, **Shiki**, and many others for their very help and support while developing this. 

Thanks! ~
