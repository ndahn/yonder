from __future__ import annotations
import atexit
import time
import pyo


# pyo keeps a single global "current server", and a second one pulls the rug
# out from under the first: objects created afterwards attach to the newcomer,
# and shutting either down leaves the other booted but silent, raising
# PyoServerStateException on the next object it tries to build. So there is
# exactly one, booted on first use and kept until the process exits.
_server: pyo.Server = None

# Chains waiting for the server to move past them before they are dropped.
# Module level so a chain can outlive the player that built it
_retired: dict[int, tuple[tuple, pyo.CallAfter]] = {}
_retire_token = 0


def acquire_server() -> pyo.Server:
    """The pyo server, booted and started on the first call.

    There is nothing to give back: it stays up until the process exits, see
    the note at the top of this module.
    """
    global _server

    if _server is None:
        # NOTE crashes on some systems with input enabled, but we don't need it
        _server = pyo.Server(duplex=0)
        _server.deactivateMidi()
        _server.boot()
        _server.start()

        # Registered after booting, so it only runs if there is one to stop.
        # atexit is LIFO and every player registers its own close later, which
        # therefore runs first - their objects are released while the server is
        # still up, exactly as during normal operation
        atexit.register(_shutdown)

    return _server


def _shutdown() -> None:
    """Stop the server on the way out, once nothing can still be using it."""
    global _server

    if _server is None:
        return

    server, _server = _server, None
    if server.getIsStarted():
        server.stop()
        # Allow the server to drain all buffers and callbacks
        time.sleep(0.25)

    # Nothing is processing any more, so whatever is still parked can go
    _retired.clear()

    if server.getIsBooted():
        server.shutdown()


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
