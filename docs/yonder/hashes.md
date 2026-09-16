# About Hashes

When Wwise needs unique identifiers for something, it uses hashes - numbers of 6-9 digits derived from a human-readable (or random) name. The hash function used is a variant of [Fowler-Noll-Vo (FNV-1a 32bit)](https://en.wikipedia.org/wiki/Fowler%E2%80%93Noll%E2%80%93Vo_hash_function). This is *the only* thing that's stored in a soundbank, and the original name is thus lost. Wwise will store these names in a `SoundBanks.xml` file, but this is of course not shipped with the games.

It is generally unfeasible to reverse a hash, however, the community and me have extracted and guessed many hash-name pairs. Yonder ships with a somewhat large dictionary of known names (which you can find [here](https://github.com/ndahn/yonder/blob/main/resources/wwise_ids.txt)) and will use this to show human-readable labels wherever possible.

!!! tip

    Any custom names you assign to objects, states, etc. cannot be stored in the soundbank. In order to be able to restore these later, Yonder will create a textfile next to your soundbank (same name, different file extension). I would generally suggest sharing these files along with your mods so others won't suffer as much!
