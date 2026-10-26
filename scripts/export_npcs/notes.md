# Extraction

## NPCs
### Batch export
One-time setup in `<mod>/data/`:
- Export all ESD scripts to `esd/` (esdtool.exe)
- Export the full `TalkParam` to `talkparam.csv` (Smithbox)

Then run `export_npc.py` in the conda *base* environment (where yonder is installed):
- `python export_npc.py 301 800 000003000` (or `--all` for every NPC in `npcs_er.yaml`)
- The ID is the number after the `t` in the ESD file names (`t301006000.py` -> `301`). All scripts
  starting with it are merged, so NPCs with multiple talk scripts just work
- A longer ID like `000003000` selects a single script. Use this for the generic `000` prefix,
  which is shared by multiple NPCs (e.g. Melina)
- Folder names come from `npcs_er.yaml` (`301` -> `white_mask_varre`). Use `301=varre` to override.
  Add missing NPCs to the yaml
- Existing folders are overwritten, including the wems zip
- The `=name` is only used for the folder name, default is `c<ID>`. Add frequent NPCs to `npcs` in the script
  to run without arguments
- Voice IDs are looked up in the TalkParam and the soundbank is derived from them (`301001000` -> `vc301`,
  anything without its own bank -> `vcmain`). If an NPC uses multiple banks, one folder per bank is created

Creates `data/audio/white_mask_varre_vc301/` with `subtitles.csv`, `talkparam.csv`, `wems/`, and `white_mask_varre_wems.zip`.
Events that can't be found in the soundbank are listed in `*_missing.txt`.


## Movie Cutscenes
- No need to convert audio files
- Audio needs to be baked
	- Intro cutscene contains music, voicelines, sfx, and X on tracks 0-3
	- Baked audio on track 4
- Open bk2 movie in RAD Video Tools
- Mix in new audio and select baked audio file, replace track 4


## In-game Cutscenes
- Are probably prefetch, so the actual audio is outside the soundbank
- Soundbank can be identified via the map ID (intro awakening scene: m19)
- Might have to create a matching prefetch or edit the audio object for it to work properly