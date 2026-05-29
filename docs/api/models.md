# Domain Models

All four CCSDS ODM message types implemented as Pydantic v2 `BaseModel` subclasses.
Fields are validated on construction — an invalid value raises `pydantic.ValidationError`
with a message that cites the relevant spec section.

Domain models use only plain Python scalars (`float`, `str`, `int`). They have no
mandatory dependencies on numpy, OSTk, or any other optional library.

## Base class

::: orbit_data_messages.models.base.CCSDSDataMessage

## OEM — Orbit Ephemeris Message

::: orbit_data_messages.models.oem.OEM

## OMM — Orbit Mean-Elements Message

::: orbit_data_messages.models.omm.OMM

## OPM — Orbit Parameter Message

::: orbit_data_messages.models.opm.OPM

## OCM — Orbit Comprehensive Message

::: orbit_data_messages.models.ocm.OCM

## Controlled vocabulary

::: orbit_data_messages.models.values.CenterName

::: orbit_data_messages.models.values.RefFrame

::: orbit_data_messages.models.values.TimeSystem

::: orbit_data_messages.models.values.ManCovRefFrame

## Field metadata annotations

::: orbit_data_messages.models.metadata.FieldMetadata

::: orbit_data_messages.models.metadata.Delineation
