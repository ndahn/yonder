# About Hashes
Nodes a soundbank are identified by unique hashes - numbers of 6-9 digits derived from a human-readable name. The hash function used is a variant of [Fowler-Noll-Vo (FNV-1a 32bit)](https://en.wikipedia.org/wiki/Fowler%E2%80%93Noll%E2%80%93Vo_hash_function).

It is generally unfeasible to reverse a hash, but the community and me have extracted and guessed many hash-name pairs that Yonder will use where available. Yonder ships with a somewhat large dictionary of known names and will use this to show human-readable labels wherever possible. 

!!! tip

    When you assign custom names to objects, states, etc., only their hashes will be saved in the soundbank. In order to be able to restore these later, Yonder will create a textfile next to your soundbank with the same name. This is similar to the *SoundBanks.xml* file Wwise creates for this purpose.
