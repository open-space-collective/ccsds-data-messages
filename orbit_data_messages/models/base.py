"""Abstract base class for all CCSDS Data Message types."""
from abc import ABC


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

    def __new__(cls, *args, **kwargs):
        if cls is CCSDSDataMessage:
            raise TypeError(
                "CCSDSDataMessage cannot be instantiated directly. "
                "Use a concrete message type: such as OEM, OMM, OPM, or OCM."
            )
        return super().__new__(cls)
