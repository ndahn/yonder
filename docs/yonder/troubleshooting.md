# Troubles from Beyond

Debugging soundbanks is not a fun task, but there are a couple of common failure modes:

???+ example "None of the soundbank's sounds play"

    This typically happens when Wwise failed to parse your soundbank. For one, nodes within a soundbank need to be in a very specific order (children before parents and a couple other rules). The types of all attributes must also match exactly (e.g. you can't have a `bool` instead of an `int`). By now, after many a trial, Yonder is very good at detecting and enforcing both of these and will do so when saving. You can trigger this manually from the *Bank* menu - check the terminal output to see the results!

???+ example "The game crashes when the soundbank gets loaded"

    This problem is much rarer, but also harder to diagnose. The cause is often a structural issue, e.g. a circular reference in the node graph, or layers with non-unique IDs. Yonder has some basic checks in place, but the best thing you can do is trying to isolate the subtree causing this.

???+ example "Sounds from Adel don't work"

    *We don't talk about Adel.*
