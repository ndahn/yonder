#!/usr/bin/env python3
import sys
import traceback

from yonder import Soundbank
from yonder.hash import calc_hash
from yonder.transfer import copy_wwise_events


# ------------------------------------------------------------------------------------------
# Set these paths so they point to your extracted source and destination soundbanks.
SRC_BNK_DIR = "soundbanks/nr_cs_main"
DST_BNK_DIR = "soundbanks/cs_main"

# NPC sounds are usually named "c<npc-id>0<sound-id>". When moving npc sounds to the player, I
# recommend renaming them as follows.
#
#     <soundtype>4<npc-id><sound-id>
#
# This should make it easy to avoid collisions and allows you to keep track of which IDs you've
# ported so far and from where.
#
# The soundtype has (afaik) no meaning other than being used for calculating the event hashes, so
# you should be able to use whatever you like from this list:
#
WWISE_IDS = {
    "c512006630": "s451206630",
    "c512006635": "s451206635",
}

# Enables writing to the destination.
ENABLE_WRITE = True

# If True, don't ask for confirmation: make reasonable assumptions and write once ready
NO_QUESTIONS = False
# ------------------------------------------------------------------------------------------


def line_to_hash(line: str) -> int:
    line: str = line.strip()
    if not line:
        return None

    if line.startswith("#"):
        return int(line[1:])

    if not line.startswith(("Play_", "Stop_")):
        line = "Play_" + line
    return calc_hash(line)


def prune_ids(ids: list[str]) -> list[str]:
    # NOTE it's important to maintain the order
    pruned = []
    seen = set()

    for line in ids:
        h = line_to_hash(line)
        if h is not None and h not in seen:
            seen.add(h)
            pruned.append(line)

    return pruned


def collect_event_map(
    src_bnk: Soundbank, dst_bnk: Soundbank, src_ids: list[str], dst_ids: list[str]
) -> dict[Hash, str]:
    src_ids = prune_ids(src_ids)
    dst_ids = prune_ids(dst_ids)

    if not src_ids:
        raise ValueError("No source IDs selected")

    if len(src_ids) != len(dst_ids):
        raise ValueError("Source and destination IDs not balanced")

    for line in src_ids:
        src_play_id = line_to_hash(line)
        if src_play_id not in src_bnk:
            raise ValueError(f"{line} not found in source bank")

    for line in dst_ids:
        if line.startswith("#"):
            raise ValueError("Destination IDs cannot be hashes")

        dst_play_id = line_to_hash(line)
        if dst_play_id in dst_bnk:
            raise ValueError(f"{line} already exists in destination bank")

    event_map = {}
    for sid, did in zip(src_ids, dst_ids):
        src_explicit = sid.startswith(("Play_", "Stop_", "#"))
        dst_explicit = did.startswith(("Play_", "Stop_"))
        if src_explicit != dst_explicit:
            raise ValueError("Cannot pair explicit with implicit event names")

        if src_explicit:
            event_map[line_to_hash(sid)] = did
        else:
            play_evt = f"Play_{sid}"
            if play_evt in src_bnk:
                event_map[play_evt] = f"Play_{did}"

            stop_evt = f"Stop_{sid}"
            if stop_evt in src_bnk:
                event_map[stop_evt] = f"Stop_{did}"


if __name__ == "__main__":
    if len(sys.argv) == 1:
        src_bnk_dir = SRC_BNK_DIR
        dst_bnk_dir = DST_BNK_DIR
        event_map = WWISE_IDS
        enable_write = ENABLE_WRITE
        no_questions = NO_QUESTIONS
    else:
        import argparse

        parser = argparse.ArgumentParser(
            description="A nifty tool for transfering wwise sounds between From software soundbanks."
        )

        parser.add_argument("src_bnk", type=str, help="The source soundbank folder")
        parser.add_argument(
            "dst_bnk", type=str, help="The destination soundbank folder"
        )
        parser.add_argument(
            "sound_ids",
            type=str,
            nargs="+",
            help="Specify as '<id>' or '<id>:=<new-id>', where IDs are either full event names, hashes of event names, or wwise IDs (x123456789)",
        )

        args = parser.parse_args()

        if args.help:
            parser.print_help()
            sys.exit(1)

        src_bnk = Soundbank.from_file(args.src_bnk)
        dst_bnk = Soundbank.from_file(args.dst_bnk)

        src_ids = []
        dst_ids = []

        for s in args.sound_ids:
            if ":=" in s:
                src_id, dst_id = s.split(":=")
            else:
                src_id = dst_id = s

            src_ids.append(src_id)
            dst_ids.append(dst_id)

        event_map = collect_event_map(src_bnk, dst_bnk, src_ids, dst_ids)

    try:
        copy_wwise_events(src_bnk, dst_bnk, event_map)
    except Exception:
        if hasattr(sys, "gettrace") and sys.gettrace() is not None:
            # Debugger is active, let the debugger handle it
            raise

        # In case we are run from a temporary terminal, otherwise we won't see what's wrong
        print(traceback.format_exc())

    input("Press enter to exit...")
