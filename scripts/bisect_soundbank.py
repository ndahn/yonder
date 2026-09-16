"""Bisect a soundbank to find which part of it triggers a bug.

Workflow
--------
1. Run this script. It rebuilds cs_c4340.bnk containing only a slice of the bank.
2. Test that bnk in game.
3. Append the outcome to RESULTS below:
       True  -> the bug still happened with this bank
       False -> the bug was gone
4. Run again. Repeat until a single unit is left.

Why not bisect over events
--------------------------
Every playable container in this bank is targeted by *two* events: a Play event
and a StopEO event, and the two are far apart in HIRC order.  `delete_subtree`
follows Action.external_id, so a Stop event's subtree is the exact same node set
as its Play partner's.  Deleting "the other half" of the event list therefore
deletes containers the kept half still needs -- with a naive event split, both
halves come back gutted and both "fix" the bug.

So we bisect over *units* instead.  A unit is a connected component of
(events <-> actions <-> target node), i.e. a Play event, its Stop event, any
PlayEvent-linked events, all their actions, and the whole container subtree they
point at.  Units are disjoint, so removing one can never damage another.

Nodes that belong to no unit (ActorMixers, Buses, Attenuations, States, FX,
orphan actions) are shared infrastructure and are always kept.
"""

import sys
import json
import shutil
from pathlib import Path
from collections import defaultdict

from tqdm.contrib.logging import logging_redirect_tqdm

from yonder import Soundbank
from yonder.enums import BelowThresholdBehavior, SourceType
from yonder.types import Event
from yonder.util import unpack_soundbank, repack_soundbank, logger


ORIG = Path("E:/Games/Elden Ring/Modding/Tools/yonder/test/discord/cs_c4340_orig.bnk")
BNK2JSON = Path("E:/Games/Elden Ring/Modding/Tools/rewwise_0.3.2/bnk2json.exe")

# One entry per completed test round, oldest first.
# True  = the bank produced by that round still showed the bug
# False = it did not
RESULTS: list[bool] = []

# "bisect"    - assume one unit is at fault, narrow down to it.
# "threshold" - assume no single unit is at fault and the bug needs a certain
#               amount of the bank present.  Keeps units[0:N] and binary
#               searches for the smallest N that reproduces.  The unit at N-1
#               is then whatever tips it over.
# "ddmin"     - Zeller delta debugging.  Makes no assumption about how many
#               units are involved and returns a 1-minimal failing set: every
#               unit in it is necessary, removing any one makes the bug go away.
#               Costs more rounds than threshold but is the only mode that
#               actually answers "what is the minimum set".
MODE = "threshold"

# Restrict which units the search may choose from, as (start, end) or an
# explicit list.  Everything outside this pool and outside PIN_UNITS is deleted
# every round.  Use it to seed a search from a smaller known-failing set.
SEARCH_POOL: tuple[int, int] | list[int] | None = None

# threshold mode only: seed the search with what you already know.
# THRESHOLD_LO = largest prefix known to be clean
# THRESHOLD_HI = smallest prefix known to reproduce (None = all units)
THRESHOLD_LO = 0
THRESHOLD_HI: int | None = None

# Units that are ALWAYS kept and excluded from the search.  Use this once you
# know one half of an interaction: pin it and search the rest for its partner.
# e.g. PIN_UNITS = [209] then MODE="threshold" finds the smallest prefix of the
# remaining units that reproduces together with unit 209.
PIN_UNITS: list[int] = []

# Keep exactly units[start:end] and nothing else, ignoring RESULTS entirely.
# Use this to re-confirm an earlier result: any round that was reported as
# testing "units[0:N]" can be replayed with KEEP_RANGE = (0, N).
KEEP_RANGE: tuple[int, int] | None = None

# Set to an explicit list of unit indices to build that exact selection instead
# of following RESULTS.  Useful for confirming a suspected pair interaction.
KEEP_OVERRIDE: list[int] | None = None

# Control run: keep *everything* and delete nothing, so the only thing that
# happens is unpack -> (solve) -> save -> repack.  If the bug disappears from
# this bank then the fault is not in the logical content at all, it is in the
# original file's node ordering / serialisation, and no bisection can ever
# reproduce it.
CONTROL_RUN = True

# Whether save() re-solves the HIRC dependency order.  Run the control once
# with True and once with False to tell "solve() reordered the HIRC" apart
# from "rewwise round-tripped the file".
SOLVE = True

# Also drop every Sound whose source is marked Embedded but has no media in the
# bank (268 of them, spread thinly across ~all units).  Combine with
# CONTROL_RUN=True for a one-shot test of that hypothesis on the full bank.
DROP_MISSING_MEDIA = False

# Class-wide tests.  Each clears one whole category of setting across the bank
# so a single run can acquit or implicate the entire category.  Combine with
# CONTROL_RUN=True to test on the full bank.
CLEAR_INSTANCE_LIMITS = False  # every max_instance_count -> 0 (unlimited)
CLEAR_INFINITE_LOOPS = False  # every loop_count 0 -> 1 (play once)
CLEAR_VIRTUAL_BEHAVIOUR = False  # below_threshold KillIfOneShotElseVirtual -> KillVoice

# Shared-infrastructure tests.  The unit search NEVER touches these nodes - they
# are kept in every build - yet they are the only things in the bank that can
# couple otherwise unrelated voices.  Each flag is a one-run probe.
CLEAR_BUS_LIMITS = False  # Bus max_instance_count -> 0 (CLEAR_INSTANCE_LIMITS misses these)
CLEAR_HDR = False  # hdr_flags -> 0 on every Bus / AuxiliaryBus
CLEAR_AUX_SENDS = False  # drop every user aux send (381 nodes feed Aux_ReverbTest_*)
DROP_BUS_INFRA = False  # delete all Bus / AuxiliaryBus / EffectCustom nodes outright
DROP_NODES: list[int] = []  # generic escape hatch: extra node ids to delete

# Strip the `layers` list from every LayerContainer.  All 82 layers in this bank
# have layer_id=0 (27 of 34 containers therefore hold duplicates), rtpc_id=0 and
# a single (0,0) Linear crossfade point - i.e. constructed defaults, not real
# Wwise data.  In cs_main only 6 of 2238 LayerContainers have layers at all, so
# an empty list is the overwhelmingly normal shape and behaviourally inert when
# no RTPC drives the crossfade.
CLEAR_LAYERS = True

# Build the unit list and report, but don't touch any files.
DRY_RUN = False


def build_units(bnk: Soundbank) -> list[dict]:
    """Group the bank into disjoint event/action/target components."""
    uf: dict[int, int] = {}

    def find(x: int) -> int:
        uf.setdefault(x, x)
        while uf[x] != x:
            uf[x] = uf[uf[x]]
            x = uf[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            uf[ra] = rb

    events: list[Event] = list(bnk.query(node_type=Event))

    for evt in events:
        find(evt.id)
        for aid in evt.actions:
            action = bnk.get(aid)
            if action is None:
                continue
            union(evt.id, action.id)
            # PlayEvent targets another event, Play/Stop target a container.
            # Either way the two ends belong to the same unit.
            if action.external_id and action.external_id in bnk:
                union(action.id, action.external_id)

    groups: dict[int, dict] = defaultdict(
        lambda: {"events": set(), "actions": set(), "targets": set()}
    )

    for evt in events:
        grp = groups[find(evt.id)]
        grp["events"].add(evt.id)
        for aid in evt.actions:
            action = bnk.get(aid)
            if action is None:
                continue
            grp["actions"].add(action.id)
            target = bnk.get(action.external_id)
            if target is not None and not isinstance(target, Event):
                grp["targets"].add(target.id)

    order = {n.id: i for i, n in enumerate(bnk.hirc.objects)}
    units = []

    for grp in groups.values():
        nodes = set(grp["events"]) | set(grp["actions"])
        for tid in grp["targets"]:
            nodes |= set(bnk.get_subtree(tid, True, False).nodes)

        units.append(
            {
                "events": sorted(grp["events"]),
                "actions": sorted(grp["actions"]),
                "targets": sorted(grp["targets"]),
                "nodes": nodes,
            }
        )

    # Stable, human-readable ordering: by the first event in HIRC order
    units.sort(key=lambda u: min(order[e] for e in u["events"]))
    return units


def next_slice(n_units: int, results: list[bool]) -> tuple[int, int, int, int]:
    """Standard bisection over [lo, hi), the smallest interval known to fail.

    Each round tests the first half of the current interval; results[i] says
    whether that first half reproduced the bug.
    """
    lo, hi = 0, n_units

    for reproduced in results:
        if hi - lo <= 1:
            break
        mid = (lo + hi) // 2
        if reproduced:
            hi = mid  # culprit is in the first half we just tested
        else:
            lo = mid  # it wasn't, so it must be in the second half

    mid = (lo + hi) // 2 if hi - lo > 1 else hi
    return lo, mid, lo, hi


def next_threshold(n_units: int, results: list[bool]) -> tuple[int, int, int]:
    """Binary search the smallest prefix units[0:N] that still reproduces."""
    lo = THRESHOLD_LO
    hi = THRESHOLD_HI if THRESHOLD_HI is not None else n_units

    for reproduced in results:
        if hi - lo <= 1:
            break
        mid = (lo + hi) // 2
        if reproduced:
            hi = mid
        else:
            lo = mid

    n = (lo + hi) // 2 if hi - lo > 1 else hi
    return n, lo, hi


def ddmin_plan(items: list[int]):
    """Zeller's ddmin as a generator.

    Yields (candidate, current_set, granularity); receives True if that
    candidate reproduced the bug.  Returns the 1-minimal failing set.
    """
    c = list(items)
    n = 2

    while len(c) > 1:
        size = max(1, len(c) // n)
        chunks = [c[i : i + size] for i in range(0, len(c), size)]
        if len(chunks) > n:  # fold any overflow into the last chunk
            chunks[n - 1 :] = [[x for ch in chunks[n - 1 :] for x in ch]]

        hit = None
        for ch in chunks:  # can we narrow to a single chunk?
            if ch and (yield ch, c, n):
                hit = ch
                break
        if hit is not None:
            c, n = hit, 2
            continue

        if n > 2:  # at n == 2 the complements are the chunks we just tried
            for ch in chunks:
                comp = [x for x in c if x not in set(ch)]
                if comp and (yield comp, c, n):
                    hit = comp
                    break
            if hit is not None:
                c, n = hit, max(n - 1, 2)
                continue

        if n >= len(c):
            break
        n = min(2 * n, len(c))

    return c


def next_ddmin(items: list[int], results: list[bool]):
    """Replay ddmin against the recorded results. -> (next_candidate, minimal)."""
    gen = ddmin_plan(items)
    try:
        cfg = gen.send(None)
        for reproduced in results:
            cfg = gen.send(reproduced)
        return cfg, None
    except StopIteration as stop:
        return None, stop.value


def describe(bnk: Soundbank, unit: dict) -> str:
    lines = []
    for eid in unit["events"]:
        lines.append(f"    event   {bnk[eid]!r}")
    for aid in unit["actions"]:
        lines.append(f"    action  {bnk[aid]}  -> {bnk[aid].external_id}")
    for tid in unit["targets"]:
        node = bnk[tid]
        lines.append(f"    target  {node!r}  ({len(unit['nodes'])} nodes in subtree)")
    return "\n".join(lines)


def main() -> None:
    test_bnk = shutil.copyfile(ORIG, ORIG.parent / "cs_c4340.bnk")
    test_bnk_dir = unpack_soundbank(BNK2JSON, test_bnk)
    bnk = Soundbank.load(test_bnk_dir)

    units = build_units(bnk)
    all_ids = {n.id for n in bnk.hirc.objects}
    in_units = set().union(*(u["nodes"] for u in units)) if units else set()
    shared = all_ids - in_units

    logger.info(f"{len(bnk)} nodes -> {len(units)} units, {len(shared)} shared nodes")

    # Units must be disjoint, otherwise removing one damages another
    seen: dict[int, int] = {}
    for i, unit in enumerate(units):
        for nid in unit["nodes"]:
            if nid in seen:
                logger.warning(
                    f"unit {i} and unit {seen[nid]} both contain node {nid} "
                    f"- bisection results will be unreliable"
                )
            seen[nid] = i

    # Validate every unit index the config refers to, so a typo fails loudly
    # here instead of as an IndexError halfway through building the selection.
    for label, idxs in (
        ("PIN_UNITS", PIN_UNITS),
        ("KEEP_OVERRIDE", KEEP_OVERRIDE or []),
        ("SEARCH_POOL", list(range(*SEARCH_POOL)) if isinstance(SEARCH_POOL, tuple)
         else (SEARCH_POOL or [])),
        ("KEEP_RANGE", list(KEEP_RANGE) if KEEP_RANGE else []),
    ):
        bad = [i for i in idxs if not 0 <= i <= len(units)]
        if bad:
            raise SystemExit(
                f"{label} contains out-of-range unit indices {bad}; "
                f"this bank has {len(units)} units (valid: 0..{len(units) - 1})"
            )

    # Pinned units are always kept and take no part in the search
    pinned = sorted(set(PIN_UNITS))
    if SEARCH_POOL is None:
        candidates = range(len(units))
    elif isinstance(SEARCH_POOL, tuple):
        candidates = range(*SEARCH_POOL)
    else:
        candidates = SEARCH_POOL
    pool = [i for i in candidates if 0 <= i < len(units) and i not in set(pinned)]
    if pinned:
        logger.info(f"Pinned units (always kept): {pinned}")
    if SEARCH_POOL is not None:
        logger.info(f"Search pool restricted to {len(pool)} units: {pool[0]}..{pool[-1]}")

    if CONTROL_RUN:
        keep_idx = list(range(len(units)))
        lo = hi = None
        logger.info(f"CONTROL_RUN: keeping all {len(units)} units, solve={SOLVE}")
    elif KEEP_RANGE is not None:
        rs, re_ = KEEP_RANGE
        rs = max(0, rs)
        re_ = min(len(units), re_)
        keep_idx = sorted(set(range(rs, re_)) | set(pinned))
        lo = hi = None
        logger.info(
            f"KEEP_RANGE: keeping units[{rs}:{re_}] "
            f"({re_ - rs} units)" + (f" + pinned {pinned}" if pinned else "")
        )
    elif KEEP_OVERRIDE is not None:
        keep_idx = sorted(set(KEEP_OVERRIDE) | set(pinned))
        lo = hi = None
        logger.info(f"KEEP_OVERRIDE: keeping units {keep_idx}")
    elif MODE == "ddmin":
        cfg, minimal = next_ddmin(pool, RESULTS)
        lo = hi = None

        if cfg is None:
            keep = sorted(set(minimal) | set(pinned))
            logger.info(f"ddmin complete after {len(RESULTS)} rounds.")
            logger.info(
                f"1-minimal failing set: {len(keep)} units {keep} "
                f"(of which {pinned} were pinned)"
            )
            for i in keep:
                print(f"  unit {i}:")
                print(describe(bnk, units[i]))
            sys.exit(0)

        candidate, current, gran = cfg
        keep_idx = sorted(set(candidate) | set(pinned))
        logger.info(
            f"ddmin round {len(RESULTS)}: working set {len(current)} units, "
            f"granularity {gran}, testing {len(candidate)} of them "
            f"(+{len(pinned)} pinned)"
        )
    elif MODE == "threshold":
        n, lo, hi = next_threshold(len(pool), RESULTS)

        if hi - lo <= 1:
            logger.info(f"Threshold search complete after {len(RESULTS)} rounds.")
            logger.info(
                f"pool[0:{lo}] is clean, pool[0:{hi}] reproduces "
                f"(pinned: {pinned}). Unit {pool[hi - 1]} is what tips it over:"
            )
            print(describe(bnk, units[pool[hi - 1]]))
            sys.exit(0)

        keep_idx = sorted(pool[:n] + pinned)
        logger.info(
            f"Round {len(RESULTS)}: clean at {lo}, reproduces at {hi}, "
            f"testing pool[0:{n}] (= units up to {pool[n - 1]}) + pinned"
        )
    else:
        start, end, lo, hi = next_slice(len(pool), RESULTS)

        if hi - lo <= 1:
            logger.info(f"Bisection complete after {len(RESULTS)} rounds.")
            logger.info(f"Culprit is unit {pool[lo]}:")
            print(describe(bnk, units[pool[lo]]))
            sys.exit(0)

        keep_idx = sorted(pool[start:end] + pinned)
        logger.info(
            f"Round {len(RESULTS)}: failing interval is pool [{lo}..{hi}), "
            f"testing first half [{start}..{end}) ({len(keep_idx)} units incl. pinned)"
        )

    keep_nodes = set(shared)
    for i in keep_idx:
        keep_nodes |= units[i]["nodes"]

    if DROP_MISSING_MEDIA:
        have = {int(p.stem) for p in bnk.wems()}
        orphaned = {
            n.id
            for n in bnk.query(node_type="Sound")
            if int(n.bank_source_data.source_type) == SourceType.Embedded
            and n.source_id not in have
        }
        logger.info(f"DROP_MISSING_MEDIA: dropping {len(orphaned)} sounds")
        keep_nodes -= orphaned

    if CLEAR_INSTANCE_LIMITS:
        n = 0
        for node in bnk:
            nbp = getattr(node, "node_base_params", None)
            if nbp and nbp.adv_settings_params.max_instance_count:
                nbp.adv_settings_params.max_instance_count = 0
                n += 1
        logger.info(f"CLEAR_INSTANCE_LIMITS: cleared {n} instance limits")

    if CLEAR_INFINITE_LOOPS:
        n = 0
        for node in bnk:
            if getattr(node, "loop_count", None) == 0:
                node.loop_count = 1
                n += 1
        logger.info(f"CLEAR_INFINITE_LOOPS: made {n} containers play once")

    if CLEAR_VIRTUAL_BEHAVIOUR:
        n = 0
        for node in bnk:
            nbp = getattr(node, "node_base_params", None)
            if nbp and int(nbp.adv_settings_params.below_threshold_behavior) == 3:
                nbp.adv_settings_params.below_threshold_behavior = (
                    BelowThresholdBehavior.KillVoice
                )
                n += 1
        logger.info(f"CLEAR_VIRTUAL_BEHAVIOUR: changed {n} nodes to KillVoice")

    buses = [n for n in bnk if n.type_name in ("Bus", "AuxiliaryBus")]

    if CLEAR_BUS_LIMITS:
        n = 0
        for node in buses:
            bp = node.initial_values.bus_initial_params
            if bp.max_instance_count:
                logger.info(
                    f"  {node.get_name(str(node.id))}: "
                    f"max_instance_count {bp.max_instance_count} -> 0"
                )
                bp.max_instance_count = 0
                n += 1
        logger.info(f"CLEAR_BUS_LIMITS: cleared {n} bus instance limits")

    if CLEAR_HDR:
        n = 0
        for node in buses:
            bp = node.initial_values.bus_initial_params
            if bp.hdr_flags:
                bp.hdr_flags = 0
                n += 1
        logger.info(f"CLEAR_HDR: disabled HDR on {n} buses")

    if CLEAR_AUX_SENDS:
        n = 0
        for node in bnk:
            nbp = getattr(node, "node_base_params", None)
            if not nbp:
                continue
            aux = nbp.aux_params
            if aux.has_aux or any((aux.aux1, aux.aux2, aux.aux3, aux.aux4)):
                aux.has_aux = False
                aux.override_user_aux_sends = False
                aux.aux1 = aux.aux2 = aux.aux3 = aux.aux4 = 0
                n += 1
        logger.info(f"CLEAR_AUX_SENDS: cleared aux sends on {n} nodes")

    if CLEAR_LAYERS:
        n = layers = 0
        for node in bnk.query(node_type="LayerContainer"):
            if node.layers:
                layers += len(node.layers)
                node.layers = []
                node.layer_count = 0
                n += 1
        logger.info(f"CLEAR_LAYERS: stripped {layers} layers from {n} LayerContainers")

    extra = set(DROP_NODES)
    if DROP_BUS_INFRA:
        extra |= {n.id for n in buses}
        extra |= {n.id for n in bnk.query(node_type="EffectCustom")}
        logger.info(f"DROP_BUS_INFRA: deleting {len(extra)} bus/fx nodes")
    keep_nodes -= extra

    to_delete = sorted(all_ids - keep_nodes)
    logger.info(
        f"Keeping {len(keep_idx)}/{len(units)} units "
        f"({len(keep_nodes)} nodes), deleting {len(to_delete)}"
    )

    if DRY_RUN:
        logger.info("DRY_RUN - not writing anything")
        for i in keep_idx[:5]:
            print(f"  unit {i}:")
            print(describe(bnk, units[i]))
        return

    if to_delete:
        bnk.delete_nodes(*to_delete)
    bnk.save(solve=SOLVE)
    repack_soundbank(BNK2JSON, bnk.bnk_dir)

    if lo is None:
        # Explicit selection - print it so the exact run can be replayed later
        events = sum(len(units[i]["events"]) for i in keep_idx)
        logger.info(
            f"Explicit selection: {len(keep_idx)} units, {events} events, "
            f"{len(keep_nodes)} nodes. Replay with "
            f"KEEP_OVERRIDE = {keep_idx if len(keep_idx) <= 20 else '...'}"
        )
    else:
        remaining = hi - lo
        logger.info(
            f"Test this bank, then append True to RESULTS if the bug is still "
            f"there, False if it is gone. ~{max(remaining - 1, 0).bit_length()} "
            f"rounds left."
        )


if __name__ == "__main__":
    with logging_redirect_tqdm():
        main()
