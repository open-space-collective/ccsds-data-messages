from abc import ABC


class CCSDSDataMessage(ABC):
    """
    Abstract base class for all CCSDS orbit data message types.

    Cannot be instantiated directly. Used only as a type-hint target:

        def read(path: Path) -> CCSDSDataMessage: ...

    Concrete message types multiply-inherit from this class and Pydantic's BaseModel:

        class OEM(CCSDSDataMessage, BaseModel): ...

    MRO reasoning for class OEM(CCSDSDataMessage, BaseModel):
      - CCSDSDataMessage.__mro__ = [CCSDSDataMessage, ABC, object]
      - Pydantic v2's ModelMetaclass is a subclass of ABCMeta — no metaclass
        conflict arises.
      - C3 linearisation produces: OEM → CCSDSDataMessage → ABC → BaseModel
        → ... → object. No ordering contradiction exists because ABC and
        BaseModel both descend from object and neither appears in the other's
        MRO above object.
    """

    def __new__(cls, *args, **kwargs):
        if cls is CCSDSDataMessage:
            raise TypeError(
                "CCSDSDataMessage cannot be instantiated directly. "
                "Use a concrete message type: OEM, OMM, OPM, or OCM."
            )
        return super().__new__(cls)
