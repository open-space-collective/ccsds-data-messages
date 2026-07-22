# Copyright (c) Loft Orbital Solutions Inc.
"""Domain models for the CCSDS Navigation Data Message types."""

from typing import TypeAlias

from ._base import BaseCovarianceMatrix as CovarianceMatrix

# Shared block types (used by both OPM and OMM).
from ._base import BaseSpacecraftParameters as SpacecraftParameters
from .conversions import oem_to_tracss_ocm
from .conversions import omm_to_tle
from .message import CCSDSDataMessage
from .ocm import OCM
from .oem import OEM
from .omm import OMM
from .opm import OPM
from .tle import TLE

# Commonly referenced OPM inner types - re-exported so users can write
# `from ccsds_data_messages.models import OPMStateVector` instead of
# navigating three levels of nesting.
OPMStateVector: TypeAlias = OPM.Data.StateVector
OPMKeplerianElements: TypeAlias = OPM.Data.OsculatingKeplerianElements
OPMManeuverParameters: TypeAlias = OPM.Data.ManeuverParameters
OPMUserDefinedParameters: TypeAlias = OPM.Data.UserDefinedParameters

# Commonly referenced OMM inner types.
OMMKeplerianElements: TypeAlias = OMM.Data.MeanKeplerianElements
OMMTLERelatedParameters: TypeAlias = OMM.Data.TLERelatedParameters

# Commonly referenced OEM inner types.
OEMEphemerisDataLine: TypeAlias = OEM.Segment.EphemerisData.EphemerisDataLine
OEMCovarianceMatrixLines: TypeAlias = OEM.Segment.CovarianceMatrix.CovarianceMatrixLines

__all__ = [
    # Conversions
    "oem_to_tracss_ocm",
    "omm_to_tle",
    # Concrete message types (spec abbreviations are canonical per CCSDS 502.0-B-3 section 1.2)
    "OCM",
    "OEM",
    "OMM",
    "OPM",
    # Non-message value objects
    "TLE",
    # Abstract base
    "CCSDSDataMessage",
    # Shared block types
    "CovarianceMatrix",
    "SpacecraftParameters",
    # OEM inner types
    "OEMCovarianceMatrixLines",
    "OEMEphemerisDataLine",
    # OMM inner types
    "OMMTLERelatedParameters",
    "OMMKeplerianElements",
    # OPM inner types
    "OPMKeplerianElements",
    "OPMManeuverParameters",
    "OPMStateVector",
    "OPMUserDefinedParameters",
]
