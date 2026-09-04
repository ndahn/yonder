# Unmangling Soundbanks

Some of the soundbanks include (partial) duplicates of structures stored in other soundbanks. This is fine for vanilla stuff, since the structures are identical, and any missing branches are lodaed from the other soundbank(s), but makes it incredibly hard to modify them properly. This tool will delete structures that are known or assumed to cause problems from the offending soundbanks.

!!! example

    Nightreign in particular is affected by this, where `cs_main` contains a partial duplicate of the main *MusicSwitchContainer* (usually stored in `cs_smain` (*sss*)). Since the instance from `cs_main` takes priority, any custom music added to `cs_smain` is ignored.
