"""
Compute backend registry and thread-local context manager.

Primary API — always explicit, always unambiguous:

    view = EphemerisView(data, backend=NumpyBackend())

Convenience layer — thread-local stack (secondary API):

    with using_backend("numpy") as b:
        view = EphemerisView(data, backend=b)

    # or, read the ambient backend:
    b = current_backend()

The context manager is thread-local.  It is NOT safe for asyncio: concurrent
coroutines in the same thread share the same stack.
"""
from __future__ import annotations

import importlib
import threading
from contextlib import contextmanager
from typing import Any
from typing import Iterator

# ---------------------------------------------------------------------------
# Backend registry table
#
# Backend classes are referenced as "module_path:ClassName" strings so that
# importing this module has zero side-effects and no optional dependency
# (numpy, OSTk) is loaded until backend() is called.
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, str] = {
    "pure":  "orbit_data_messages.compute.backends.pure:PurePythonBackend",
    "numpy": "orbit_data_messages.compute.backends.numpy_:NumpyBackend",
    "ostk":  "orbit_data_messages.compute.backends.ostk_:OSTkBackend",
}

# Thread-local stack of active backend instances.
_local = threading.local()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def backend(name: str) -> Any:
    """
    Instantiate and return the named backend.

    Backend classes are imported lazily — calling this function is the first
    time the corresponding module is loaded.

    Parameters
    ----------
    name : 'pure' | 'numpy' | 'ostk'

    Raises
    ------
    ValueError  : unknown backend name
    ImportError : required extra not installed (e.g., numpy)
    """
    reference = _REGISTRY.get(name)
    if reference is None:
        available = ", ".join(f"'{k}'" for k in sorted(_REGISTRY))
        raise ValueError(
            f"Unknown backend {name!r}. "
            f"Available backends: {available}"
        )
    module_path, class_name = reference.split(":")
    module = importlib.import_module(module_path)   # lazy import
    cls = getattr(module, class_name)
    return cls()


def current_backend() -> Any:
    """
    Return the backend at the top of the thread-local stack.

    Never raises.  When no ``using_backend`` context is active on this
    thread, returns a fresh ``PurePythonBackend()`` instance — the only
    backend that works without any optional extras installed.
    """
    stack: list[Any] = getattr(_local, "stack", [])
    if stack:
        return stack[-1]
    # Lazy import — PurePythonBackend has no optional dependencies.
    from orbit_data_messages.compute.backends.pure import PurePythonBackend
    return PurePythonBackend()


@contextmanager
def using_backend(name: str) -> Iterator[Any]:
    """
    Push a backend onto the thread-local stack for the duration of the block.

    Yields the instantiated backend so it can be passed to views explicitly::

        with using_backend("numpy") as b:
            view = EphemerisView(data, backend=b)

    Nesting is supported — the inner context overrides the outer one; the
    outer is restored on exit::

        with using_backend("pure") as b_outer:
            with using_backend("numpy") as b_inner:
                assert current_backend() is b_inner
            assert current_backend() is b_outer

    .. warning::
        **Thread-local; not safe for asyncio.**
        Concurrent coroutines running on the same OS thread share the same
        stack, so the context manager cannot isolate backends across
        coroutines.  Use the explicit ``backend=`` parameter instead.
    """
    b = backend(name)
    if not hasattr(_local, "stack"):
        _local.stack = []
    _local.stack.append(b)
    try:
        yield b
    finally:
        _local.stack.pop()
