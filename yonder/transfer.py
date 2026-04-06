from yonder import Soundbank, HIRCNode
from yonder.types import Event, Action, Sound, MusicTrack
from yonder.wem import import_wems
from yonder.util import format_hierarchy, logger


def extract_structure(bnk: Soundbank, entrypoint) -> list[HIRCNode]:
    nodes = []

    # Collect the hierarchy responsible for playing the sound(s)
    action_tree = bnk.get_subtree(entrypoint, False)
    nodes.extend(bnk[n] for n in action_tree.nodes)

    # Go upwards through the parents chain and see what needs to be transferred
    upchain = bnk.get_parent_chain(entrypoint)
    nodes.extend((bnk[uid] for uid in upchain))

    return nodes


def copy_event(
    src_bnk: Soundbank,
    dst_bnk: Soundbank,
    event: Event,
    new_name: str = None,
) -> Event:
    event = event.copy()
    actions = []

    if new_name:
        event.name = new_name

    for aid in event.actions:
        action: Action = src_bnk.get(aid)
        if action:
            # Some actions make references to other soundbanks
            action = action.copy()
            if (
                hasattr(action.params, "bank_id")
                and action.params.bank_id == src_bnk.id
            ):
                action.params.bank_id = dst_bnk.id

            actions.append(action)
        else:
            # This probably shouldn't happen
            logger.error(f"Event {event} references non-existing action {aid}")

    dst_bnk.add_nodes(event, *actions)
    return event


def copy_node_structure(
    src_bnk: Soundbank,
    dst_bnk: Soundbank,
    entrypoint: HIRCNode,
) -> list[int]:
    # Collect the hierarchy responsible for playing the sound(s)
    action_tree = src_bnk.get_subtree(entrypoint, False)
    tree_str = format_hierarchy(src_bnk, action_tree)
    logger.info(f"Discovered hierarchy:\n{entrypoint}\n{tree_str}\n")

    # Collect the wems
    wems = set()
    for nid in action_tree:
        node = src_bnk.get(nid)
        if node:
            if isinstance(node, Sound):
                wems.add(node.source_id)
            elif isinstance(node, MusicTrack):
                wems.update(node.source_ids)

    transfer_nodes = []
    for nid in action_tree:
        node = src_bnk.get(nid)
        if node and node.id not in dst_bnk:
            transfer_nodes.append(node.copy())

    dst_bnk.add_nodes(*transfer_nodes)

    # Go upwards through the parents chain and see what needs to be transferred
    upchain = src_bnk.get_parent_chain(entrypoint)
    upchain_str = "\n".join(
        [f" ⤷ {up_id} ({src_bnk[up_id].type})" for up_id in reversed(upchain)]
    )
    logger.info(f"\nThe parent chain consists of the following nodes:\n{upchain_str}\n")

    up_child = entrypoint
    for up_id in upchain:
        # Once we encounter an existing node we can assume the rest of the chain is
        # intact. Child nodes must be inserted *before* the first existing parent.
        up_node = dst_bnk.get(up_id)
        if up_node:
            up_node.children.add(up_child)
            break

        # First time we encounter upchain node, clear the children, as non-existing items
        # will make the soundbank invalid
        up_node = src_bnk[up_id].copy()
        up_node.children.clear()
        up_node.children.add(up_child)
        dst_bnk.add_nodes(up_node)

        up_child = up_node

    return wems


def copy_wems(
    src_bnk: Soundbank,
    dst_bnk: Soundbank,
    wems: list[int],
) -> None:
    wems_str = "\n".join(f"- {w}" for w in wems)
    logger.info(f"Discovered the following WEMs:\n{wems_str}\n")

    logger.info("Copying wems...")
    wem_paths = []
    for wem in wems:
        embedded = src_bnk.bnk_dir / f"{wem}.wem"
        if embedded.is_file():
            wem_paths.append(embedded)

        streamed = src_bnk.bnk_dir.parent / "wem" / str(wem)[:2] / f"{wem}.wem"
        if streamed.is_file():
            wem_paths.append(streamed)

        if not embedded.is_file() and not streamed.is_file():
            logger.warning(f"Could not locate wem {wem}")

    import_wems(dst_bnk, wem_paths)


def copy_wwise_events(
    src_bnk: Soundbank,
    dst_bnk: Soundbank,
    wwise_map: dict[int | str, str],
    save: bool = True,
) -> None:
    wems = []

    map_str = "\n".join(f"\t{src} -> {dst}" for src, dst in wwise_map.items())
    logger.info(f"Transferring structures from {src_bnk} to {dst_bnk}")
    logger.info(f"The following events will be transferred:\n{map_str}\n")

    for wwise_src, wwise_dst in wwise_map.items():
        evt: Event = src_bnk[wwise_src]
        if not isinstance(evt, Event):
            raise ValueError(f"{wwise_src} is not an Event")

        # Copy the event and its actions
        evt = copy_event(src_bnk, dst_bnk, evt, wwise_dst)

        # Collect the structures attached to each action
        for action_id in evt.actions:
            action: Action = src_bnk[action_id]

            # NOTE action_bnk_id will already be translated from src_bnk to dst_bnk
            if hasattr(action.params, "bank_id"):
                if action.params.bank_id != 0 and action.params.bank_id != dst_bnk.id:
                    logger.info(
                        f"Action {action.id} references external soundbank {action.params.bank_id}"
                    )
                    continue

            entrypoint = src_bnk[action.external_id]
            new_wems = copy_node_structure(src_bnk, dst_bnk, entrypoint)
            wems.extend(new_wems)

    # Save and verify
    if save:
        # Save already solves and verifies
        dst_bnk.save()
    else:
        logger.info("\nVerifying soundbank...")
        dst_bnk.solve()
        severity = dst_bnk.verify()
        if severity > 0:
            logger.warning(
                " - some issues were found in your soundbank. Check the log!"
            )
        else:
            logger.info(" - seems surprisingly fine :o\n")

    # Copy WEMs
    copy_wems(src_bnk, dst_bnk, wems)

    # Yay!
    logger.info("Done. Yay!")


def copy_structures_with_new_events(
    src_bnk: Soundbank,
    dst_bnk: Soundbank,
    nodes: dict[HIRCNode, str],
    save: bool = False,
) -> None:
    wems = []

    for entrypoint, wwise_dst in nodes.items():
        play_event = Event.new(f"Play_{wwise_dst}")
        play_action = Action.new_play_action(
            dst_bnk.new_id(), f"Stop_{wwise_dst}", bank_id=dst_bnk.id
        )
        play_action.external_id = entrypoint.id
        play_event.add_action(play_action)

        stop_event = Event.new(f"Stop_{wwise_dst}")
        stop_action = Action.new_stop_action(dst_bnk.new_id(), f"Stop_{wwise_dst}")
        stop_action.external_id = entrypoint.id
        stop_event.add_action(stop_action)

        dst_bnk.add_nodes(play_event, play_action, stop_event, stop_action)
        new_wems = copy_node_structure(src_bnk, dst_bnk, entrypoint)
        wems.extend(new_wems)

    # Save and verify
    if save:
        # Save already solves and verifies
        dst_bnk.save()
    else:
        logger.info("\nVerifying soundbank...")
        dst_bnk.solve()
        issues = dst_bnk.verify()
        if issues:
            for issue in issues:
                logger.warning(f" - {issue}")
        else:
            logger.info(" - seems surprisingly fine :o\n")

    # Copy WEMs
    copy_wems(src_bnk, dst_bnk, wems)

    # Yay!
    logger.info("Done. Yay!")
