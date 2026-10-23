from __future__ import annotations
import time
import pyo


# pyo keeps a single global "current server", and a second one pulls the rug
# out from under the first: objects created afterwards attach to the newcomer,
# and shutting either down leaves the other booted but silent, raising
# PyoServerStateException on the next object it tries to build. Players
# therefore share one server, booted with the first of them and shut down with
# the last. Closing the marker dialog must not kill the preview that opened it.
_server: pyo.Server = None
_users = 0

# Chains waiting for the server to move past them before they are dropped.
# Module level so a chain can outlive the player that built it
_retired: dict[int, tuple[tuple, pyo.CallAfter]] = {}
_retire_token = 0


def acquire_server() -> pyo.Server:
    """Claim the shared server, booting and starting it on the first claim."""
    global _server, _users

    if _server is None:
        # NOTE crashes on some systems with input enabled, but we don't need it
        _server = pyo.Server(duplex=0)
        _server.deactivateMidi()
        _server.boot()
        _server.start()

    _users += 1
    return _server


def release_server() -> bool:
    """Give up one claim on the shared server.

    Returns
    -------
    bool
        True if this was the last claim and the server actually went down, in
        which case nothing is processing any more and pyo objects can be
        dropped on the spot. False means other players are still running on
        it, so anything being released has to go through `retire`.
    """
    global _server, _users

    _users = max(0, _users - 1)
    if _users or _server is None:
        return False

    server, _server = _server, None
    if server.getIsStarted():
        server.stop()
        # Allow the server to drain all buffers and callbacks
        time.sleep(0.25)

    # Nothing is processing any more, so whatever is still parked can go
    _retired.clear()

    if server.getIsBooted():
        server.shutdown()

    return True


def is_running() -> bool:
    return _server is not None and _server.getIsStarted()


def retire(nodes: list[pyo.PyoObject], keep: tuple = (), delay: float = 0.1) -> None:
    """Stop a chain of pyo objects and hold it until the server is past it.

    Dropping the last reference to a pyo object while the server may still be
    processing it is what hard crashes the whole app. `pyo.CallAfter` runs the
    release from the server's own callback thread, the one place where nothing
    else can be touching the streams at the same time. This mirrors what
    `yonder.types.HIRCNode.release_pyo` does for the node tree.

    Parameters
    ----------
    nodes : list of pyo.PyoObject
        The chain, in creation order. Stopped back to front.
    keep : tuple
        Anything else that has to stay referenced for as long as the chain
        does, such as the tables its readers point at.
    delay : float
        Seconds to hold on for. 0 releases immediately, which is only safe
        while the server is stopped, since no callback would ever fire to do
        it later.
    """
    global _retire_token

    # Back to front, so nothing keeps pulling from a node that already quit
    for node in reversed(nodes):
        node.stop()

    if delay <= 0 or not is_running():
        return

    _retire_token += 1
    token = _retire_token
    _retired[token] = ((nodes, keep), pyo.CallAfter(_drop_retired, delay, token))


def _drop_retired(token: int) -> None:
    """Called from pyo's callback thread once a grace period is up. Dropping
    the entry here is what finally frees the objects."""
    _retired.pop(token, None)
