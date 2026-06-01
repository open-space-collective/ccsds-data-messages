"""Abstract base class for all CCSDS Data Message types."""
from __future__ import annotations

from abc import ABC
from typing import Any
from typing import Self


class CCSDSDataMessage(ABC):
    """Abstract base for CCSDS Data Message types (such as OEM, OMM, OPM, OCM).

    Cannot be instantiated directly; use one of the concrete subtypes. Exists
    primarily as a type-hint target so that ``Reader.read()`` can declare a
    return type that spans all message types::

        def read(path: Path) -> CCSDSDataMessage: ...

    Concrete subtypes use multiple inheritance::

        class OEM(CCSDSDataMessage, BaseModel): ...

    The MRO is well-defined: Pydantic v2's ``ModelMetaclass`` is a subclass of
    ``ABCMeta``, so no metaclass conflict arises, and C3 linearization produces
    a valid ordering.

    Raises:
        TypeError: If instantiated directly (i.e. ``CCSDSDataMessage()``).
    """

    def __new__(cls: type[Self], *args: Any, **kwargs: Any) -> Self:
        """Create a new instance, blocking direct instantiation of the abstract base.

        Args:
            cls (type[Self]): The class being instantiated.
            *args (Any): Positional arguments forwarded to ``super().__new__``.
            **kwargs (Any): Keyword arguments forwarded to ``super().__new__``.

        Returns:
            Self: A new instance of the concrete subclass.

        Raises:
            TypeError: If ``cls`` is ``CCSDSDataMessage`` itself.
        """
        if cls is CCSDSDataMessage:
            raise TypeError(
                "CCSDSDataMessage cannot be instantiated directly. "
                "Use a concrete message type: such as OEM, OMM, OPM, or OCM."
            )
        return super().__new__(cls)
