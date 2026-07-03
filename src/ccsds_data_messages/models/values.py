# SPDX-License-Identifier: Apache-2.0

"""
StrEnum classes for controlled vocabulary.

Values are taken directly from the authoritative SANA registries.
"""

from __future__ import annotations

import re
from enum import StrEnum


class CenterName(StrEnum):
    """
    Valid values for the ``CENTER_NAME`` keyword.

    Authoritative source: SANA Registry of Orbit Centers
    https://sanaregistry.org/r/orbit_centers

    Member names differ from values where the SANA string contains characters
    illegal in Python identifiers (spaces, hyphens, slashes, leading digits).
    ``member.value`` always returns the authoritative SANA string.
    """

    # Sun, Planets, and Associated Dynamical Points
    SUN = "SUN"
    MERCURY = "MERCURY"
    MERCURY_BARYCENTER = "MERCURY BARYCENTER"
    VENUS = "VENUS"
    VENUS_BARYCENTER = "VENUS BARYCENTER"
    EARTH = "EARTH"
    EARTH_BARYCENTER = "EARTH BARYCENTER"
    EARTH_MOON_L1 = "EARTH-MOON L1"
    EARTH_MOON_L2 = "EARTH-MOON L2"
    MARS = "MARS"
    MARS_BARYCENTER = "MARS BARYCENTER"
    JUPITER = "JUPITER"
    JUPITER_BARYCENTER = "JUPITER BARYCENTER"
    SATURN = "SATURN"
    SATURN_BARYCENTER = "SATURN BARYCENTER"
    URANUS = "URANUS"
    URANUS_BARYCENTER = "URANUS BARYCENTER"
    NEPTUNE = "NEPTUNE"
    NEPTUNE_BARYCENTER = "NEPTUNE BARYCENTER"
    PLUTO = "PLUTO"
    PLUTO_BARYCENTER = "PLUTO BARYCENTER"
    SOLAR_SYSTEM_BARYCENTER = "SOLAR SYSTEM BARYCENTER"
    SUN_EARTH_L1 = "SUN-EARTH L1"
    SUN_EARTH_L2 = "SUN-EARTH L2"
    # Planetary Satellites
    MOON = "MOON"
    PHOBOS = "PHOBOS"
    DEIMOS = "DEIMOS"
    IO = "IO"
    EUROPA = "EUROPA"
    GANYMEDE = "GANYMEDE"
    CALLISTO = "CALLISTO"
    AMALTHEA = "AMALTHEA"
    MIMAS = "MIMAS"
    ENCELADUS = "ENCELADUS"
    TETHYS = "TETHYS"
    DIONE = "DIONE"
    RHEA = "RHEA"
    TITAN = "TITAN"
    HYPERION = "HYPERION"
    IAPETUS = "IAPETUS"
    PHOEBE = "PHOEBE"
    JANUS = "JANUS"
    EPIMETHEUS = "EPIMETHEUS"
    HELENE = "HELENE"
    TELESTO = "TELESTO"
    CALYPSO = "CALYPSO"
    ATLAS = "ATLAS"
    PANDORA = "PANDORA"
    MIRANDA = "MIRANDA"
    ARIEL = "ARIEL"
    UMBRIEL = "UMBRIEL"
    TITANIA = "TITANIA"
    OBERON = "OBERON"
    LARISSA = "LARISSA"
    PROTEUS = "PROTEUS"
    TRITON = "TRITON"
    CHARON = "CHARON"
    # Minor Planets and Asteroids
    CERES_1 = "1 CERES"
    VESTA_4 = "4 VESTA"
    LUTETIA_21 = "21 LUTETIA"
    IDA_243 = "243 IDA"
    MATHILDE_253 = "253 MATHILDE"
    EROS_433 = "433 EROS"
    GASPRA_951 = "951 GASPRA"
    TOUTATIS_4179 = "4179 TOUTATIS"
    ANNEFRANK_5525 = "5525 ANNEFRANK"
    BRAILLE_9969 = "9969 BRAILLE"
    ITOKAWA_25143 = "25143 ITOKAWA"
    APL_132524 = "132524 APL"
    RYUGU_162173 = "162173 RYUGU"
    BENNU_101955 = "101955 BENNU"
    DIDYMOS_65803 = "65803 DIDYMOS/DIMORPHOS"
    ARROKOTH = "ARROKOTH"
    # Comets
    HALLEY = "1P/HALLEY"
    TEMPEL_1 = "9P/TEMPEL 1"
    BORRELLY = "19P/BORRELLY"
    GIACOBINI_ZINNER = "21P/GIACOBINI-ZINNER"
    GRIGG_SKJELLRUP = "26P/GRIGG-SKJELLRUP"
    CHURYUMOV_GERASIMENKO = "67P/CHURYUMOV-GERASIMENKO"
    WILD_2 = "81P/WILD 2"
    HARTLEY_2 = "103P/HARTLEY 2"


# Parametric SANA B4 frame patterns not representable as fixed RefFrame members.
_REF_FRAME_PARAMETRIC_RE: re.Pattern[str] = re.compile(
    r"^(?:DTRF\d{4}|GCRF\d+|ICRF\d+|ITRF\d{4}|MOON_PA\d{3})$"
)


class RefFrame(StrEnum):
    """
    Values for the ``REF_FRAME`` keyword.

    Values are taken directly from the authoritative SANA registries.
    """

    # Spec body section 3.2.3.3 values
    EME2000 = "EME2000"  # Earth Mean Equator and Equinox of J2000
    GCRF = "GCRF"  # Geocentric Celestial Reference Frame
    GRC = "GRC"  # Greenwich Rotating Coordinates
    ICRF = "ICRF"  # International Celestial Reference Frame
    ITRF1997 = "ITRF1997"  # Annex G examples use ITRF1997
    ITRF2000 = "ITRF2000"  # International Terrestrial Reference Frame 2000
    ITRF_93 = "ITRF-93"  # International Terrestrial Reference Frame 1993
    ITRF_97 = "ITRF-97"  # International Terrestrial Reference Frame 1997
    MCI = "MCI"  # Mars Centered Inertial
    TDR = "TDR"  # True of Date, Rotating
    TEME = "TEME"  # True Equator Mean Equinox (only used in OMMs, not OPMs)
    TOD = "TOD"  # True of Date
    # SANA B4 registry values (non-parametric)
    ALIGN_CB = "ALIGN_CB"
    ALIGN_EARTH = "ALIGN_EARTH"
    B1950 = "B1950"
    CIRS = "CIRS"
    EFG = "EFG"
    FIXED_CB = "FIXED_CB"
    FIXED_EARTH = "FIXED_EARTH"
    GTOD = "GTOD"
    INERTIAL_CB = "INERTIAL_CB"
    ITRF = "ITRF"
    J2000 = "J2000"
    J2000A = "J2000A"
    J2000_ECLIPTIC = "J2000_ECLIPTIC"
    MOD_CB = "MOD_CB"
    MOD_EARTH = "MOD_EARTH"
    MOD_MOON = "MOD_MOON"
    MOE_CB = "MOE_CB"
    MOE_EARTH = "MOE_EARTH"
    MOON_ME = "MOON_ME"
    MOON_MEIAUE = "MOON_MEIAUE"
    TEMEOFDATE = "TEMEOFDATE"
    TEMEOFEPOCH = "TEMEOFEPOCH"
    TIRS = "TIRS"
    TOD_CB = "TOD_CB"
    TOD_EARTH = "TOD_EARTH"
    TOD_MOON = "TOD_MOON"
    TOE_CB = "TOE_CB"
    TOE_EARTH = "TOE_EARTH"
    TOE_MOON = "TOE_MOON"
    TRUE_ECLIPTIC = "TRUE_ECLIPTIC"
    UVW_GO_INERTIAL = "UVW_GO_INERTIAL"
    WGS84 = "WGS84"

    @classmethod
    def _missing_(cls, value: object) -> RefFrame | None:
        if isinstance(value, str) and _REF_FRAME_PARAMETRIC_RE.fullmatch(value):
            # Pseudo-member so Python 3.14+ enum machinery accepts it.
            new_member = str.__new__(cls, value)
            new_member._value_ = value
            new_member._name_ = value
            return new_member
        return None

    @staticmethod
    def parametric(base: RefFrame | str, suffix: int | str) -> RefFrame:
        """
        Construct a parametric frame name from a base and numeric/string suffix.

        The combined name must match one of the five parametric patterns:
        DTRFyyyy, GCRFn, ICRFn, ITRFyyyy, MOON_PAxxx.

        Examples::

            RefFrame.parametric(RefFrame.ICRF, 3)      # "ICRF3"
            RefFrame.parametric(RefFrame.ITRF, 2014)   # "ITRF2014"
            RefFrame.parametric("DTRF", 2020)          # "DTRF2020"
            RefFrame.parametric("MOON_PA", 421)        # "MOON_PA421"

        Raises:
            ValueError: If the composed name does not match a recognized parametric pattern.
        """
        name = f"{base}{suffix}"
        if not _REF_FRAME_PARAMETRIC_RE.fullmatch(name):
            raise ValueError(
                f"{name!r} is not a recognized parametric RefFrame pattern. "
                "Expected one of: DTRFyyyy, GCRFn, ICRFn, ITRFyyyy, MOON_PAxxx."
            )
        return RefFrame(name)


class TimeSystem(StrEnum):
    """
    Values for the ``TIME_SYSTEM`` keyword.

    Values are taken directly from the authoritative SANA registries.
    """

    BEIDOU = "BEIDOU"  # BeiDou Time
    ET = "ET"  # Ephemeris Time
    GALILEO = "GALILEO"  # Galileo System Time
    GLONASS = "GLONASS"  # GLONASS Time
    GMST = "GMST"  # Greenwich Mean Sidereal Time
    GPS = "GPS"  # Global Positioning System
    MET = "MET"  # Mission Elapsed Time
    MRT = "MRT"  # Mission Relative Time
    NAVIC = "NAVIC"  # Navigation with Indian Constellation
    SCLK = "SCLK"  # Spacecraft Clock (receiver)
    TAI = "TAI"  # International Atomic Time
    TCB = "TCB"  # Barycentric Coordinate Time
    TDB = "TDB"  # Barycentric Dynamical Time
    TCG = "TCG"  # Geocentric Coordinate Time
    TT = "TT"  # Terrestrial Time
    UT1 = "UT1"  # Universal Time
    UTC = "UTC"  # Coordinated Universal Time


class ManCovRefFrame(StrEnum):
    """
    Narrow set of reference frame values for OPM/OMM COV_REF_FRAME and MAN_REF_FRAME.

    Spec section 3.2.4.11 lists exactly three values; OMM table 4-3 cross-references
    section 3.2.4.11 for the same set.
    Also used for OEM COV_REF_FRAME (orbit-relative side) per section 5.2.5.3.
    """

    RSW = "RSW"  # Another name for 'Radial, Transverse, Normal'
    RTN = "RTN"  # Radial, Transverse, Normal
    TNW = "TNW"  # x-axis along velocity, W along angular momentum, N completing right-hand system


class ExtendedManCovRefFrame(StrEnum):
    """
    Full orbit-relative reference frame registry for OCM (section 6.2.7, Annex B5).

    OCM COV_REF_FRAME and MAN_REF_FRAME reference annex B5 (the full SANA
    orbit-relative registry), which includes the base three (RSW/RTN/TNW from
    section 3.2.4.11) plus all extended frames.

    For OPM/OMM/OEM contexts use the narrower ManCovRefFrame (RSW/RTN/TNW only).

    Extended set from the authoritative SANA registries.
    """

    RSW = "RSW"  # Another name for 'Radial, Transverse, Normal'
    RTN = "RTN"  # Radial, Transverse, Normal
    TNW = "TNW"  # x-axis along velocity, W along angular momentum, N completing right-hand system
    EQW_INERTIAL = "EQW_INERTIAL"
    LVLH_INERTIAL = "LVLH_INERTIAL"
    LVLH_ROTATING = "LVLH_ROTATING"
    NSW_INERTIAL = "NSW_INERTIAL"
    NSW_ROTATING = "NSW_ROTATING"
    NTW_INERTIAL = "NTW_INERTIAL"
    NTW_ROTATING = "NTW_ROTATING"
    PQW_INERTIAL = "PQW_INERTIAL"
    RSW_INERTIAL = "RSW_INERTIAL"
    RSW_ROTATING = "RSW_ROTATING"
    SEZ_INERTIAL = "SEZ_INERTIAL"
    SEZ_ROTATING = "SEZ_ROTATING"
    TNW_INERTIAL = "TNW_INERTIAL"
    TNW_ROTATING = "TNW_ROTATING"
    VNC_INERTIAL = "VNC_INERTIAL"
    VNC_ROTATING = "VNC_ROTATING"


class Interpolation(StrEnum):
    """
    Valid values for the ``INTERPOLATION`` keyword.

    Defined directly in the spec body; not a SANA registry field.
    Table 5-3 (OEM) lists HERMITE, LAGRANGE, LINEAR as "Examples of Values"
    (not a closed set); Table 6-4 (OCM) additionally lists PROPAGATE. No
    validator rejects PROPAGATE on OEM - the spec does not state it is forbidden.
    """

    HERMITE = "HERMITE"
    LAGRANGE = "LAGRANGE"
    LINEAR = "LINEAR"
    PROPAGATE = "PROPAGATE"


class ManeuverBasis(StrEnum):
    """
    Valid values for the ``MAN_BASIS`` keyword.

    Defined directly in the spec body; not a SANA registry field.
    """

    CANDIDATE = "CANDIDATE"
    PLANNED = "PLANNED"
    ANTICIPATED = "ANTICIPATED"
    TELEMETRY = "TELEMETRY"
    DETERMINED = "DETERMINED"
    SIMULATED = "SIMULATED"
    OTHER = "OTHER"


class MeanElementTheory(StrEnum):
    """
    Valid values for the ``MEAN_ELEMENT_THEORY`` keyword.

    Values are those given as examples in the spec body; PPT3 is referenced in section 4.2.4.7
    and the conditional rules for MEAN_MOTION_DOT / MEAN_MOTION_DDOT.
    """

    SGP = "SGP"
    SGP4 = "SGP4"
    SGP4_XP = "SGP4-XP"
    DSST = "DSST"
    USM = "USM"
    PPT3 = "PPT3"


class ObjectType(StrEnum):
    """
    Valid values for the ``OBJECT_TYPE`` keyword.

    Values are taken directly from the authoritative SANA registries.
    """

    PAYLOAD = "PAYLOAD"
    ROCKET_BODY = "ROCKET BODY"
    DEBRIS = "DEBRIS"
    UNKNOWN = "UNKNOWN"
    OTHER = "OTHER"


class OperationalStatus(StrEnum):
    """
    Valid values for the ``OPS_STATUS`` keyword.

    Values are taken directly from the authoritative SANA registries.
    """

    BACKUP_STORAGE_STANDBY = "BACKUP_STORAGE_STANDBY"
    DEAD = "DEAD"
    DECAYED = "DECAYED"
    DEGRADED_OPERATIONS = "DEGRADED_OPERATIONS"
    EXTENDED_MISSION = "EXTENDED_MISSION"
    NONOPERATIONAL = "NONOPERATIONAL"
    OPERATIONAL_MANEUVERABLE = "OPERATIONAL_MANEUVERABLE"
    OPERATIONAL_NONMANEUVERABLE = "OPERATIONAL_NONMANEUVERABLE"
    REENTRY_MODE = "REENTRY_MODE"
    UNKNOWN = "UNKNOWN"


class OrbitCategory(StrEnum):
    """
    Valid values for the ``ORBIT_CATEGORY`` keyword.

    Values are taken directly from the authoritative SANA registries.
    """

    GEO = "GEO"
    GSO = "GSO"
    GTO = "GTO"
    HELIOCENTRIC = "HELIOCENTRIC"
    HEO = "HEO"
    INTERPLANETARY = "INTERPLANETARY"
    LEO = "LEO"
    LUNAR = "LUNAR"
    MEO = "MEO"
    OTHER = "OTHER"
    PLANETARY = "PLANETARY"

    @classmethod
    def lagrange_point_orbit(
        cls,
        primary_attracting_body: CenterName,
        secondary_attracting_body: CenterName,
        index: int,
    ) -> OrbitCategory:
        """
        Return the orbit category for a Lagrange point orbit.

        Constructs a pseudo-member with value ``<P1>_<P2>_<N>`` where P1 and P2
        are the primary and secondary attracting bodies and N is the Lagrange
        point index (1-5). The returned object is a genuine ``OrbitCategory``
        member: ``isinstance(result, OrbitCategory)`` is ``True`` and Pydantic
        validates it correctly.
        """
        if index not in {1, 2, 3, 4, 5}:
            raise ValueError(
                f"Invalid Lagrange point index: {index}, should be in {{1, 2, 3, 4, 5}}"
            )
        name = (
            f"{primary_attracting_body.value}_{secondary_attracting_body.value}_{index}"
        )
        member: OrbitCategory = str.__new__(cls, name)
        member._value_ = name
        member._name_ = name
        return member


class ManeuverPurpose(StrEnum):
    """
    Valid values for the ``MAN_PURPOSE`` keyword.

    Table 6-7 lists these as a free-text field that "could include" the values
    below (not a closed set); non-standard purposes are accepted as plain
    strings via the field's ``ManeuverPurpose | str`` type.
    """

    AEROBRAKE = "AEROBRAKE"
    ATTITUDE = "ATTITUDE"
    COLA = "COLA"
    DEPLOY = "DEPLOY"
    DESAT = "DESAT"
    DISPOSAL = "DISPOSAL"
    INCLINATION = "INCLINATION"
    LEOP = "LEOP"
    MASS_ADJUST = "MASS_ADJUST"
    MNVR_CLEANUP = "MNVR_CLEANUP"
    ORBIT = "ORBIT"
    OTHER = "OTHER"
    PERIOD = "PERIOD"
    RELOCATION = "RELOCATION"
    SCI_OBJ = "SCI_OBJ"
    SK = "SK"
    SPIN_RATE = "SPIN_RATE"
    TRAJ_CORR = "TRAJ_CORR"
    TRIM = "TRIM"

    @classmethod
    def grav_assist_from(cls, body: CenterName) -> ManeuverPurpose:
        """
        Return the maneuver purpose for a gravity assist flyby of ``body``.

        Constructs a pseudo-member with value ``GRAV_ASSIST_FROM_<body>``, per
        Table 6-7's ``GRAV_ASSIST_FROM_XXXX`` pattern (XXXX = SANA body center
        name). The returned object is a genuine ``ManeuverPurpose`` member.
        """
        name = f"GRAV_ASSIST_FROM_{body.value}"
        member: ManeuverPurpose = str.__new__(cls, name)
        member._value_ = name
        member._name_ = name
        return member

    @classmethod
    def pointing_request(cls, prm_id: str) -> ManeuverPurpose:
        """
        Return the maneuver purpose for a Pointing Request Message ``prm_id``.

        Constructs a pseudo-member with value ``PRM_ID_<prm_id>``, per Table
        6-7's ``PRM_ID_xxxx`` pattern. The returned object is a genuine
        ``ManeuverPurpose`` member.
        """
        name = f"PRM_ID_{prm_id}"
        member: ManeuverPurpose = str.__new__(cls, name)
        member._value_ = name
        member._name_ = name
        return member


class OrbitalElements(StrEnum):
    """
    Valid values for the ``TRAJ_TYPE`` keyword.

    Also used as the orbital-element portion of ``COV_TYPE`` (Annex B8 allows any
    ``TRAJ_TYPE`` value as a covariance type).

    Values are taken directly from the authoritative SANA registries.
    """

    ADBARV = "ADBARV"
    CARTP = "CARTP"
    CARTPV = "CARTPV"
    CARTPVA = "CARTPVA"
    DELAUNAY = "DELAUNAY"
    DELAUNAYMOD = "DELAUNAYMOD"
    EQUINOCTIAL = "EQUINOCTIAL"
    EQUINOCTIALMOD = "EQUINOCTIALMOD"
    GEODETIC = "GEODETIC"
    KEPLERIAN = "KEPLERIAN"
    KEPLERIANMEAN = "KEPLERIANMEAN"
    KEPLERIANMEANSGP_4 = "KEPLERIANMEANSGP-4"
    LDBARV = "LDBARV"
    ONSTATION = "ONSTATION"
    POINCARE = "POINCARE"


class CovarianceType(StrEnum):
    """
    Valid values for the event-based portion of the ``COV_TYPE`` keyword (Annex B8).

    ``COV_TYPE`` accepts either an ``OrbitalElements`` value (uncertainties in orbital
    elements) or one of these event-based covariance types that include time uncertainties.

    Values are taken directly from the authoritative SANA registries.
    """

    SIG3EIGVEC3 = "SIG3EIGVEC3"
    TADBARV = "TADBARV"
    TCARTP = "TCARTP"
    TCARTPV = "TCARTPV"
    TCARTPVA = "TCARTPVA"
    TDELAUNAY = "TDELAUNAY"
    TDELAUNAYMOD = "TDELAUNAYMOD"
    TEQUINOCTIALMOD_N = "TEQUINOCTIALMOD_N"
    TEQUINOCTIALMOD_P = "TEQUINOCTIALMOD_P"
    TEQUINOCTIAL_N = "TEQUINOCTIAL_N"
    TEQUINOCTIAL_P = "TEQUINOCTIAL_P"
    TGEODETIC = "TGEODETIC"
    TKEPLERIAN = "TKEPLERIAN"
    TKEPLERIANMEAN = "TKEPLERIANMEAN"
    TLDBARV = "TLDBARV"
    TPOINCARE = "TPOINCARE"
    TSIG3EIGVEC3 = "TSIG3EIGVEC3"


class CovarianceOrdering(StrEnum):
    """
    Valid values for the ``COV_ORDERING`` keyword.

    Defined directly in the spec body; not a SANA registry field.
    """

    LTM = "LTM"
    UTM = "UTM"
    FULL = "FULL"
    LTMWCC = "LTMWCC"
    UTMWCC = "UTMWCC"


class DutyCycleType(StrEnum):
    """
    Valid values for the ``DC_TYPE`` keyword.

    Defined directly in the spec body; not a SANA registry field.
    """

    CONTINUOUS = "CONTINUOUS"
    TIME = "TIME"
    TIME_AND_ANGLE = "TIME_AND_ANGLE"


class ShadowModel(StrEnum):
    """
    Valid values for the ``SHADOW_MODEL`` keyword.

    Defined directly in the spec body; not a SANA registry field.
    """

    NONE = "NONE"
    CYLINDRICAL = "CYLINDRICAL"
    CONE = "CONE"
    DUAL_CONE = "DUAL_CONE"


class Organization(StrEnum):
    """
    Valid values for the ``ORIGINATOR`` keyword.

    Values are taken directly from the authoritative SANA registries.
    """

    SECRETARIAT = "Secretariat"
    SANA = "SANA"
    VIAGENIE = "Viagénie"
    ASI = "ASI"
    ASA = "ASA"
    CCSDS = "CCSDS"
    CNES = "CNES"
    CNSA = "CNSA"
    CSA = "CSA"
    DLR = "DLR"
    ESA = "ESA"
    INPE = "INPE"
    JAXA = "JAXA"
    NASA = "NASA"
    RFSA = "RFSA"
    UKSA = "UKSA"
    CCSDS_CONTROL_AUTHORITY_AGENT = "CCSDS Control Authority Agent"
    EUROPEAN_SPACE_AGENCY_PRIMARY_CONTROL_AUTHORITY_OFFICE = (
        "European Space Agency Primary Control Authority Office"
    )
    ESA_CLUSTER_MISSION_CONTROL_AUTHORITY_OFFICE = (
        "ESA CLUSTER Mission Control Authority Office"
    )
    ESA_EURECA = "ESA/EURECA"
    ESA_GALILEO_SYSTEM_TEST_BED_V2_MISSION_CONTROL_AUTHORITY_OFFICE = (
        "ESA Galileo System Test Bed V2 Mission Control Authority Office"
    )
    ESA_HUYGENS_MISSION_CONTROL_AUTHORITY_OFFICE = (
        "ESA Huygens Mission Control Authority Office"
    )
    ESA_MARS_EXPRESS_MISSION_CONTROL_AUTHORITY_OFFICE = (
        "ESA Mars Express Mission Control Authority Office"
    )
    ESA_XMM_MISSION_CONTROL_AUTHORITY_OFFICE = "ESA XMM Mission Control Authority Office"
    NASA_PRIMARY_CONTROL_AUTHORITY_OFFICE_AT_THE_NATIONAL_SPACE_SCIENCE_DATA_CENTER = (
        "NASA Primary Control Authority Office at the National Space Science Data Center"
    )
    JET_PROPULSION_LABORATORY_CONTROL_AUTHORITY_OFFICE = (
        "Jet Propulsion Laboratory Control Authority Office"
    )
    UARS_CONTROL_AUTHORITY_OFFICE = "UARS Control Authority Office"
    BELSPO = "BELSPO"
    TSNIIMASH = "TsNIIMash"
    DCTA = "DCTA"
    CAS = "CAS"
    CAST = "CAST"
    CSIRO = "CSIRO"
    CRL = "CRL"
    DNSC = "DNSC"
    EUMETSAT = "EUMETSAT"
    EUTELSAT = "EUTELSAT"
    HNSC = "HNSC"
    CSIR = "CSIR"
    ISTRAC = "ISTRAC"
    KFKI = "KFKI"
    KARI = "KARI"
    MOC = "MOC"
    KAZCOSMOS = "KAZCOSMOS"
    TASA = "TASA"
    NOAA = "NOAA"
    SUPARCO = "SUPARCO"
    IKI = "IKI"
    SSC = "SSC"
    USGS = "USGS"
    MSFC = "MSFC"
    GSFC = "GSFC"
    JPL = "JPL"
    NASDA = "NASDA"
    JAXA_OSFO = "JAXA OSFO"
    BNSC = "BNSC"
    GISTDA = "GISTDA"
    ISRO = "ISRO"
    OSTIN = "OSTIN"
    ISRAEL_AI = "ISRAEL AI"
    RSA = "RSA"
    RFSA_TSNIIMASH = "RFSA TSNIIMASH"
    RAL = "RAL"
    TUBITAK = "TUBITAK"
    MBRSC = "MBRSC"
    ESA_ESTEC = "ESA-ESTEC"
    JAXA_ISAS = "JAXA-ISAS"
    SPACEIL = "SpaceIL"
    HARRIS_CORP_NASA_CONTRACTOR = "Harris Corp. (NASA Contractor)"
    THE_AEROSPACE_CORPORATION = "The Aerospace Corporation"
    DOE = "DOE"
    INTELSAT = "INTELSAT"
    DANISH = "DANISH"
    INMARSAT = "INMARSAT"
    APL = "APL"
    UNIVERSITY_OF_CALIFORNIA = "University of California"
    ARSAT_PROJECT_INVAP_S_E = "ARSAT Project INVAP S.E."
    IVIETNAM = "IVIETNAM"
    SPACE_SYSTEMS_LORAL = "Space Systems/Loral"
    TELEBRAS_TELECOMUNICACOES_BRASILEIRAS_SA = (
        "TELEBRAS - Telecomunicações Brasileiras SA"
    )
    INVAP_S_E = "INVAP S.E."
    ST_ENGINEERING_SATELLITE_SYSTEMS_PTE_LTD = "ST Engineering Satellite Systems Pte Ltd"
    IAI = "IAI"
    THALES_ALENIA_SPACE_FRANCE = "Thales Alenia Space France"
    DLR_RB_OD = "DLR-RB-OD"
    IRIDIUM_COMMUNICATIONS = "Iridium Communications"
    ICEYE_LTD = "ICEYE Ltd"
    CAS_CSSAR = "CAS-CSSAR"
    COSMOGIA_INC = "Cosmogia Inc."
    JPL_DEEP_SPACE_NETWORK_DSN = "JPL/Deep Space Network (DSN)"
    EXELIS_INC_NASA_GSFC_CONTRACTOR = "Exelis Inc (NASA GSFC contractor)"
    POCKET_SPACECRAFT = "Pocket Spacecraft"
    MSU = "MSU"
    TPZ = "TPZ"
    KSAT = "KSAT"
    SSC_GROUP = "SSC Group"
    INTA = "INTA"
    JHU = "JHU"
    SANSA = "SANSA"
    CSA_MDA = "CSA/MDA"
    CSA_CCMEO = "CSA/CCMEO"
    OVERLOOK_SYSTEMS_TECHNOLOGIES_INC = "Overlook Systems Technologies, Inc."
    CAESAR = "CAESAR"
    ESA_SST = "ESA SST"
    GNOSE = "GNOSE"
    CSPOC = "CSpOC"
    JSC = "JSC"
    SDC = "SDC"
    COMSPOC = "COMSPOC"
    ISPACE = "ispace"
    HISPASAT = "Hispasat"
    SES_AMERICOM = "SES Americom"
    WORLDSPACE = "WorldSpace"
    CERN = "CERN"
    ARABSAT = "ARABSAT"
    INSTITUTE_OF_AERO_AND_ASTRO_OF_THE_TECHNICAL_UNIVERSITY_OF_BERLIN = (
        "Institute of Aero and Astro of the Technical University of Berlin"
    )
    AFRL = "AFRL"
    PCRF = "PCRF"
    HSCL = "HSCL"
    ROSCOSMOS = "ROSCOSMOS"
    EARTHWATCH = "EarthWatch"
    GERMAN_MINISTRY_OF_DEFENSE_BMVG = "German Ministry of Defense (BMVg)"
    DOD = "DoD"
    MINISTERE_DE_LA_DEFENSE = "Ministère de la Défense"
    NTU = "NTU"
    PERATON = "Peraton"
    ISIS = "ISIS"
    QWALTEC = "Qwaltec"
    ASTROCAST_SA = "Astrocast SA"
    PARSONS = "Parsons"
    BRIGHT_ASCENSION = "Bright Ascension"
    SCISYS = "SCISYS"
    UNIVERSITY_OF_COLORADO = "University of Colorado"
    ST_PETERSBURG_STATE_UNIVERSITY_OF_AEROSPACE_INSTRUMENTATION = (
        "St. Petersburg State University of Aerospace Instrumentation"
    )
    GOONHILLY = "Goonhilly"
    MITRE = "MITRE"
    KELTIK = "Keltik"
    CLTC_BITTT = "CLTC/BITTT"
    ETRI = "ETRI"
    NICT = "NICT"
    NOAA_ENVIRONMENTAL_INFORMATION_SERVICES = "NOAA Environmental Information Services"
    NCST = "NCST"
    NSO = "NSO"
    SSO = "SSO"
    ASRC_FEDERAL = "ASRC Federal"
    LEOLABS = "LEOLABS"
    ESOC = "ESOC"
    GSOC = "GSOC"
    USAF = "USAF"
    YORK_SPACE_SYSTEMS = "York Space Systems"
    ARGONNE_NATIONAL_LABORATORY = "Argonne National Laboratory"
    MBRYONICS_LTD = "mBryonics Ltd"
    OPEN_SPACE_NETWORK_FOUNDATION = "Open Space Network Foundation"
    LANCASTER_UNIVERSITY = "Lancaster University"
    MACDONALD_DETTWILER_AND_ASSOCIATES_LTD = "MacDonald Dettwiler and Associates Ltd."
    RAUMFAHRT_SYSTEMINGENIEURE = "Raumfahrt Systemingenieure"
    HYBRID_NETWORKS_CENTER_HYNET_CENTER = "Hybrid Networks Center (HyNet Center)"
    DIGCOM_INC = "DIGCOM, Inc."
    IBM_UK_LTD = "IBM UK Ltd."
    L_3_CINCINNATI_ELECTRONICS_CORPORATION = "L-3 Cincinnati Electronics Corporation"
    OXFORD_UNIVERSITY = "Oxford University"
    GEOSEREN_LTD = "GeoSeren Ltd"
    A_I_SOLUTIONS_INC = "a.i. solutions Inc."
    GAEL_CONSULTANT = "GAEL Consultant"
    ANTARA_TEKNIK_LLC = "Antara Teknik LLC"
    MBB_DEUTSCHE_AEROSPACE = "MBB - Deutsche Aerospace"
    CS_GROUP = "CS GROUP"
    JEFFRIES_TECHNOLOGY_SOLUTIONS_INC = "Jeffries Technology Solutions, Inc"
    BRISTOL_AEROSPACE_LIMITED = "Bristol Aerospace Limited"
    NOVA_SPACE_ASSOCIATES_LTD = "Nova Space Associates Ltd"
    MPB_TECHNOLOGIES_INC = "MPB Technologies Inc."
    ECSS = "ECSS"
    ALENIA_SPAZIO = "Alenia Spazio"
    AIRBUS_DEFENCE_SPACE = "Airbus Defence & Space"
    AITECH_DEFENSE_SYSTEMS_INC = "Aitech Defense Systems Inc."
    INNOFLIGHT_INC = "Innoflight Inc."
    INSTITUT_FUR_AUTOMATION_UND_KOMMUNICATION_E_V_MAGDEBURG = (
        "Institut für Automation und Kommunication e. V. Magdeburg"
    )
    SAAB_ERICSSON_SPACE_AB = "Saab Ericsson Space AB"
    ADVANCED_SPACE_LLC = "Advanced Space, LLC"
    SURREY_SATELLITE_TECHNOLOGY_LTD = "Surrey Satellite Technology Ltd"
    POD_INC = "POD, Inc."
    PLANEHOOK_AVIATION_SERVICES_LLC = "Planehook Aviation Services, LLC"
    MYNARIC_USA_INC = "Mynaric USA, Inc."
    BAE_SYSTEMS = "BAE Systems"
    DAIMLER_BENZ_AEROSPACE = "Daimler-Benz Aerospace"
    CPI_MALIBU = "CPI Malibu"
    HABCOM_ENGINEERING = "HABCOM Engineering"
    GDP_SPACE_SYSTEMS = "GDP Space Systems"
    JOHNS_HOPKINS_UNIVERSITY_APPLIED_PHYSICS_LABORATORY = (
        "Johns Hopkins University Applied Physics Laboratory"
    )
    FUJITSU_LIMITED = "Fujitsu Limited"
    XIPHOS_TECHNOLOGIES_INC = "Xiphos Technologies, Inc."
    BACK_NINE_ENGINEERING_INC = "Back Nine Engineering, Inc"
    BEIJING_EASOARING_SOFTWARE_TECHNOLOGY_CO_LTD = (
        "Beijing Easoaring Software Technology Co., LTD"
    )
    SPACE_SOFTWARE_ITALIA_S_P_A = "Space Software Italia S.p.A."
    OMITRON_INC = "Omitron, Inc."
    SPACE_INFRASTRUCTURE_FOUNDATION_INC = "Space Infrastructure Foundation, Inc."
    RAYTHEON = "Raytheon"
    SYSRAND_CORPORATION_SPACE_ORBITAL_DEVELOPMENT_AUTHORITY_INC = (
        "sysRAND Corporation Space Orbital Development Authority, Inc."
    )
    BARNHARD_ASSOCIATES_LLC = "Barnhard Associates, LLC"
    ASTRIUM_SATELLITES = "ASTRIUM Satellites"
    GE_GLOBAL_RESEARCH = "GE Global Research"
    UNIVERSITY_OF_SHEFFIELD_SPACE_INSTRUMENTATION_GROUP = (
        "University of Sheffield Space Instrumentation Group"
    )
    MITSUBISHI_ELECTRIC_CORPORATION = "Mitsubishi Electric Corporation"
    SPACE_CONNEXIONS_LIMITED = "Space ConneXions Limited"
    EMS_TECHNOLOGIES_CANADA_LTD = "EMS Technologies Canada Ltd."
    AT_T = "AT&T"
    ASTROBOTIC_TECHNOLOGY_INC = "Astrobotic Technology Inc."
    NETACQUIRE_CORPORATION = "NetAcquire Corporation"
    REAL_TIME_LOGIC_INC_RT_LOGIC = "Real Time Logic, Inc. (RT Logic)"
    ARIANEGROUP_GMBH = "ArianeGroup GmbH"
    GARRETT_SOFTWARE = "Garrett Software"
    CASCO = "CASCO"
    MPR_TELTECH_LTD = "MPR TELTECH Ltd"
    GLOBAL_SCIENCE_AND_TECHNOLOGY_INC = "Global Science and Technology, Inc."
    UNIVERSAL_SPACE_NETWORK_INC = "Universal Space Network, Inc."
    GMV_SECURE_E_SOLUTIONS = "GMV Secure e-Solutions"
    D_C_S_GIFFORD_LLC = "D.C.S. Gifford, LLC"
    INGENICOMM_INC = "Ingenicomm, Inc."
    JOTNE_EPM_TECHNOLOGY_AS = "Jotne EPM Technology AS."
    M_L_MACMEDAN_CONSULTANT = "M. L. MacMedan, Consultant"
    JSC_NATIONAL_COMPANY_KAZAKHSTAN_GHARYSH_SAPARY = (
        "JSC “National Company “Kazakhstan Gharysh Sapary”"
    )
    CAP_GEMINI_S_P_A = "CAP GEMINI S.p.A."
    CSP_ASSOCIATES_INC = "CSP Associates, Inc."
    QUINTRON_SYSTEMS_INC = "Quintron Systems Inc."
    NARA = "NARA"
    INTECS_SISTEMI_S_P_A = "INTECS SISTEMI S.p.A."
    REACH_TECHNOLOGIES_INC = "Reach Technologies Inc."
    GMV_INSYEN = "GMV-Insyen"
    LABEN_S_P_A = "LABEN S.p.A."
    SOUTHWEST_RESEARCH_INSTITUTE = "Southwest Research Institute"
    TELESAT = "Telesat"
    LJT_AND_ASSOCIATES = "LJT and Associates"
    AMERICAN_INSTITUTE_FOR_AERONAUTICS_AND_ASTRONAUTICS_AIAA = (
        "American Institute for Aeronautics and Astronautics (AIAA)"
    )
    ZODIAC_DATA_SYSTEM = "Zodiac Data System"
    TIS_SOLUTION_LINK_INC = "TIS Solution Link Inc."
    TELOIP_INC = "TELoIP Inc."
    BRISA_SOCIETY_FOR_THE_DEVELOPMENT_OF_IT = "BRISA - Society for the Development of IT"
    AETHERIC_ENGINEERING_LTD = "Aetheric Engineering Ltd."
    CAP_GEMINI_ERNST_YOUNG = "Cap Gemini Ernst & Young"
    LOFT_ORBITAL_SOLUTIONS_INC = "Loft Orbital Solutions Inc."
    CISET_S_P_A = "CISET S.p.A"
    TELESPAZIO_VEGA_UK_LTD = "Telespazio VEGA UK Ltd"
    AMERGINT_TECHNOLOGIES = "AMERGINT Technologies"
    LOCKHEED_MARTIN_CORPORATION = "Lockheed Martin Corporation"
    ISO_IEC_JTC_1_SC_29 = "ISO/IEC JTC 1 / SC 29"
    ANTWERP_SPACE = "Antwerp Space"
    SIMON_FRASER_UNIVERSITY = "Simon Fraser University"
    MARTIME_MONITORING_SERVICES_CANADA = "Martime Monitoring Services Canada"
    OMG = "OMG"
    MYNARIC_LASERCOM_GMBH = "Mynaric Lasercom GmbH"
    CANADA_CENTRE_FOR_REMOTE_SENSING = "Canada Centre for Remote Sensing"
    SED_SYSTEMS = "SED Systems"
    SUMMATION_RESEARCH_INC = "Summation Research, Inc."
    NEC_CORPORATION = "NEC Corporation"
    GEO_SPACE_LIMITED = "GEO Space Limited"
    CANADIAN_ASTRONAUTICS_LIMITED = "Canadian Astronautics Limited"
    GRUPO_CEJELSA = "Grupo Cejelsa"
    IOAG = "IOAG"
    DIYROCKETS = "DIYROCKETS"
    PIXIA_CORP = "PIXIA Corp"
    HONEYWELL_TECHNOLOGIES_SOLUTIONS_INC = "Honeywell Technologies Solutions Inc."
    L3_TECHNOLOGIES_CS_W = "L3 Technologies - CS-W"
    LASER_LIGHT_COMMUNICATIONS = "Laser Light Communications"
    COUNCIL_FOR_SCIENTIFIC_AND_INDUSTRIAL_RESEARCH = (
        "Council for Scientific and Industrial Research"
    )
    OAKMAN_AEROSPACE_INC = "Oakman Aerospace Inc."
    BOEING_DEFENSE_SPACE_SYSTEMS = "Boeing Defense & Space Systems"
    VISIONA = "Visiona"
    _18SPCS = "18SPCS"
    BALL = "BALL"
    CMO = "CMO"
    PLANEWAVE_INSTRUMENTS_INC = "PlaneWave Instruments, Inc."
    BLUE_CUBED_LLC = "Blue Cubed LLC"
    MAEE_DIRDEF = "MAEE - DirDef"
    WORK_MICROWAVE = "WORK Microwave"
    UMBRA = "Umbra"
    ISO_TC_20_SC_14 = "ISO/TC 20/SC 14"
    PSAS = "PSAS"
    ROCKET_LAB_USA = "Rocket Lab USA"
    MASTEN = "Masten"
    VISION_ENGINEERING_SOLUTIONS = "Vision Engineering Solutions"
    LSF = "LSF"
    COFOMO_QUEBEC_INC = "Cofomo Quebec Inc."
    DHRUVA_SPACE_PRIVATE_LIMITED = "Dhruva Space Private Limited"
    MDA = "MDA"
    LEIDOS_INC = "Leidos Inc."
    TEK_TERRAIN_LLC = "Tek Terrain LLC"
    TFWIRELESS_INC = "TFWireless Inc."
    SONY_COMPUTER_SCIENCE_LABORATORIES_INC = "Sony Computer Science Laboratories, Inc."
    SECUNET_SECURITY_NETWORKS_AG = "Secunet Security Networks AG"
    D3TN = "D3TN"
    CDA = "CDA"
    INGENIARS = "IngeniArs"
    RAMPART_COMMUNICATIONS = "Rampart Communications"
    NCKU = "NCKU"
    L3HARRIS_CINCINNATI_ELECTRONICS = "L3Harris / Cincinnati Electronics"
    CTI = "CTI"
    DONGASCIENCE = "DongaScience"
    CONAE = "CONAE"
    OHB_SWEDEN = "OHB Sweden"
    MIRATLAS = "Miratlas"
    QS = "QS"
    SEN = "SEN"
    SIDU = "SIDU"
    SPACE_ISAC = "Space ISAC"
    KURTEK_LLC = "Kurtek LLC"
    D3TN_U_S = "D3TN U.S."
    VULCAN_WIRELESS = "Vulcan Wireless"
    UFO_LLC = "UFO LLC"
    PROJECT_KUIPER = "Project Kuiper"
    DIGITALARSENAL_IO_INC = "DigitalArsenal.io Inc."
    UAE_SPACE_AGENCY = "UAE Space Agency"
    NASA_GRC = "NASA GRC"
    ES_HAILSAT = "ES'HAILSAT"
    AMSAT_DL = "AMSAT-DL"
    REUNIWATT = "Reuniwatt"
    SPATIAM = "SPATIAM"
    EGSA = "EgSA"
    SELF = "self"
    SCAN = "SCaN"
    NSN = "NSN"
    PROTOCOL_TECHNOLOGY_LABORATORY = "Protocol Technology Laboratory"
    NOSA = "NOSA"
    BITTT = "BITTT"
    TUI = "TUI"
    CNRS = "CNRS"
    SQ = "SQ"
    SPN = "SPN"
    STS = "STS"
    BLUE_ORIGIN = "Blue Origin"
    LUSOSPACE = "Lusospace"
    MYRADAR = "MyRadar"
    DIGANTARA = "DIGANTARA"
    THALES_ALENIA_SPACE_ITALIA_S_P_A = "Thales Alenia Space Italia S.p.a."
    GOS = "GOS"
    TRL_SPACE = "TRL Space"
    SPACEX = "SpaceX"
    REFLEX_AEROSPACE_GMBH = "Reflex Aerospace GmbH"
    UARX_SPACE = "UARX Space"
    C3S = "C3S"
    CYBERWOLF_INDUSTRIES = "Cyberwolf Industries"
    PROTEUS_SPACE = "Proteus Space"
    APEX_SPACE = "Apex Space"
    DSCOSYS = "DSCoSys"
    ARCA = "ARCA"
    ARIANEGROUP = "ArianeGroup"
    CARE_WEATHER = "Care Weather"
    ARIS = "ARIS"
    ASTROLAB = "Astrolab"
    VUSP = "VUSP"
    REDSPACE = "RedSpace"
    SEA6U = "SEA6U"
    FIREFLY = "Firefly"
    INTUITIVE_MACHINES = "Intuitive Machines"
    SPACENAV = "SPACENAV"
    SWISSTO12 = "Swissto12"
    ORBITAID_AEROSPACE = "OrbitAID Aerospace"
    NIST = "NIST"
    MAXAR_SPACE = "Maxar Space"
    OHB_I = "OHB-I"
    ST = "ST"
    ADBU = "ADBU"
    AIC_DSU = "AIC DSU"
    CGU = "CGU"
    TM2S = "TM2S"
    KST = "KST"
    NATIONAL_SPACE_SCIENCE_AND_TECHNOLOGY_CENTER = (
        "National Space Science and Technology Center"
    )
    AT = "AT"
    ARGOTEC_SRL = "Argotec srl"
    N3O = "N3O"
    CGI = "CGI"
    DEFIANT_SPACE_CORPORATION = "Defiant Space Corporation"
    TEC = "TEC"
    SPACEOPS_NZ = "SpaceOps NZ"
    DLR_GFR = "DLR GfR"
    BLACKVE = "BlackVe"
    AALYRIA = "Aalyria"
    GERMAN_FEDERAL_OFFICE_FOR_INFORMATION_SECURITY = (
        "German Federal Office for Information Security"
    )
    AMA = "AMA"
    XIPHERA_LTD = "Xiphera LTD"
    CDS = "CDS"
    OHB_SYSTEM = "OHB System"
    PANTHERION_SPACE = "Pantherion Space"
    REDSPACE_LTD = "RedSpace Ltd"
