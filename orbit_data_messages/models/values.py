"""StrEnum classes for controlled vocabulary.

Covers orbit centers (``CenterName``), reference frames (``RefFrame``), time
systems (``TimeSystem``), and maneuver/covariance reference frames
(``ManCovRefFrame``).  Values are taken directly from the authoritative SANA
registries cited in Annex B.
"""
from __future__ import annotations

from enum import StrEnum


class CenterName(StrEnum):
    """Valid values for the ``CENTER_NAME`` keyword (Annex B2).

    Authoritative source: SANA Registry of Orbit Centers —
    https://sanaregistry.org/r/orbit_centers

    Member names differ from values where the SANA string contains characters
    illegal in Python identifiers (spaces, hyphens, slashes, leading digits).
    ``member.value`` always returns the authoritative SANA string.
    """
    # Sun, Planets, and Associated Dynamical Points
    SUN                  = "SUN"
    MERCURY              = "MERCURY"
    MERCURY_BARYCENTER   = "MERCURY BARYCENTER"
    VENUS                = "VENUS"
    VENUS_BARYCENTER     = "VENUS BARYCENTER"
    EARTH                = "EARTH"
    EARTH_BARYCENTER     = "EARTH BARYCENTER"
    EARTH_MOON_L1        = "EARTH-MOON L1"
    EARTH_MOON_L2        = "EARTH-MOON L2"
    MARS                 = "MARS"
    MARS_BARYCENTER      = "MARS BARYCENTER"
    JUPITER              = "JUPITER"
    JUPITER_BARYCENTER   = "JUPITER BARYCENTER"
    SATURN               = "SATURN"
    SATURN_BARYCENTER    = "SATURN BARYCENTER"
    URANUS               = "URANUS"
    URANUS_BARYCENTER    = "URANUS BARYCENTER"
    NEPTUNE              = "NEPTUNE"
    NEPTUNE_BARYCENTER   = "NEPTUNE BARYCENTER"
    PLUTO                = "PLUTO"
    PLUTO_BARYCENTER     = "PLUTO BARYCENTER"
    SOLAR_SYSTEM_BARYCENTER = "SOLAR SYSTEM BARYCENTER"
    SUN_EARTH_L1         = "SUN-EARTH L1"
    SUN_EARTH_L2         = "SUN-EARTH L2"
    # Planetary Satellites
    MOON       = "MOON"
    PHOBOS     = "PHOBOS"
    DEIMOS     = "DEIMOS"
    IO         = "IO"
    EUROPA     = "EUROPA"
    GANYMEDE   = "GANYMEDE"
    CALLISTO   = "CALLISTO"
    AMALTHEA   = "AMALTHEA"
    MIMAS      = "MIMAS"
    ENCELADUS  = "ENCELADUS"
    TETHYS     = "TETHYS"
    DIONE      = "DIONE"
    RHEA       = "RHEA"
    TITAN      = "TITAN"
    HYPERION   = "HYPERION"
    IAPETUS    = "IAPETUS"
    PHOEBE     = "PHOEBE"
    JANUS      = "JANUS"
    EPIMETHEUS = "EPIMETHEUS"
    HELENE     = "HELENE"
    TELESTO    = "TELESTO"
    CALYPSO    = "CALYPSO"
    ATLAS      = "ATLAS"
    PANDORA    = "PANDORA"
    MIRANDA    = "MIRANDA"
    ARIEL      = "ARIEL"
    UMBRIEL    = "UMBRIEL"
    TITANIA    = "TITANIA"
    OBERON     = "OBERON"
    LARISSA    = "LARISSA"
    PROTEUS    = "PROTEUS"
    TRITON     = "TRITON"
    CHARON     = "CHARON"
    # Minor Planets and Asteroids
    CERES_1              = "1 CERES"
    VESTA_4              = "4 VESTA"
    LUTETIA_21           = "21 LUTETIA"
    IDA_243              = "243 IDA"
    MATHILDE_253         = "253 MATHILDE"
    EROS_433             = "433 EROS"
    GASPRA_951           = "951 GASPRA"
    TOUTATIS_4179        = "4179 TOUTATIS"
    ANNEFRANK_5525       = "5525 ANNEFRANK"
    BRAILLE_9969         = "9969 BRAILLE"
    ITOKAWA_25143        = "25143 ITOKAWA"
    APL_132524           = "132524 APL"
    RYUGU_162173         = "162173 RYUGU"
    BENNU_101955         = "101955 BENNU"
    DIDYMOS_65803        = "65803 DIDYMOS/DIMORPHOS"
    ARROKOTH             = "ARROKOTH"
    # Comets
    HALLEY               = "1P/HALLEY"
    TEMPEL_1             = "9P/TEMPEL 1"
    BORRELLY             = "19P/BORRELLY"
    GIACOBINI_ZINNER     = "21P/GIACOBINI-ZINNER"
    GRIGG_SKJELLRUP      = "26P/GRIGG-SKJELLRUP"
    CHURYUMOV_GERASIMENKO = "67P/CHURYUMOV-GERASIMENKO"
    WILD_2               = "81P/WILD 2"
    HARTLEY_2            = "103P/HARTLEY 2"


class RefFrame(StrEnum):
    """Valid values for the ``REF_FRAME`` keyword (CCSDS 502.0-B-3 §3.2.3.3).

    Base set from spec body §3.2.3.3: EME2000, GCRF, GRC, ICRF, ITRF2000, ITRF-93,
    ITRF-97, MCI, TDR, TEME, TOD. GRC, MCI, TDR, TEME, TOD appear only in the spec
    body table, not in the current SANA registry.

    Extended set from SANA Registry of Celestial Body Reference Frames (Annex B4) —
    https://sanaregistry.org/r/celestial_body_reference_frames

    Parametric registry entries (DTRFyyyy, GCRFn, ICRFn, ITRFyyyy, MOON_PAxxx)
    cannot be represented as fixed enum members; use ``str`` for those cases.
    """
    # Spec body §3.2.3.3 values
    EME2000    = "EME2000"    # Earth Mean Equator and Equinox of J2000
    GCRF       = "GCRF"       # Geocentric Celestial Reference Frame
    GRC        = "GRC"        # Greenwich Rotating Coordinates
    ICRF       = "ICRF"       # International Celestial Reference Frame
    ITRF2000   = "ITRF2000"   # International Terrestrial Reference Frame 2000
    ITRF_93    = "ITRF-93"    # International Terrestrial Reference Frame 1993
    ITRF_97    = "ITRF-97"    # International Terrestrial Reference Frame 1997
    MCI        = "MCI"        # Mars Centered Inertial
    TDR        = "TDR"        # True of Date, Rotating
    TEME       = "TEME"       # True Equator Mean Equinox (only used in OMMs, not OPMs)
    TOD        = "TOD"        # True of Date
    # SANA B4 registry values (non-parametric)
    ALIGN_CB       = "ALIGN_CB"
    ALIGN_EARTH    = "ALIGN_EARTH"
    B1950          = "B1950"
    CIRS           = "CIRS"
    EFG            = "EFG"
    FIXED_CB       = "FIXED_CB"
    FIXED_EARTH    = "FIXED_EARTH"
    GTOD           = "GTOD"
    INERTIAL_CB    = "INERTIAL_CB"
    ITRF           = "ITRF"
    J2000          = "J2000"
    J2000A         = "J2000A"
    J2000_ECLIPTIC = "J2000_ECLIPTIC"
    MOD_CB         = "MOD_CB"
    MOD_EARTH      = "MOD_EARTH"
    MOD_MOON       = "MOD_MOON"
    MOE_CB         = "MOE_CB"
    MOE_EARTH      = "MOE_EARTH"
    MOON_ME        = "MOON_ME"
    MOON_MEIAUE    = "MOON_MEIAUE"
    TEMEOFDATE     = "TEMEOFDATE"
    TEMEOFEPOCH    = "TEMEOFEPOCH"
    TIRS           = "TIRS"
    TOD_CB         = "TOD_CB"
    TOD_EARTH      = "TOD_EARTH"
    TOD_MOON       = "TOD_MOON"
    TOE_CB         = "TOE_CB"
    TOE_EARTH      = "TOE_EARTH"
    TOE_MOON       = "TOE_MOON"
    TRUE_ECLIPTIC  = "TRUE_ECLIPTIC"
    UVW_GO_INERTIAL = "UVW_GO_INERTIAL"
    WGS84          = "WGS84"


class TimeSystem(StrEnum):
    """Valid values for the ``TIME_SYSTEM`` keyword (CCSDS 502.0-B-3 §3.2.3.2).

    Base set from spec body §3.2.3.2: GMST, GPS, MET, MRT, SCLK, TAI, TCB, TDB, TCG,
    TT, UT1, UTC. MET and MRT appear only in the spec body table, not in the SANA registry.

    Extended set from SANA Registry of Time Systems (Annex B3) —
    https://sanaregistry.org/r/time_systems
    """
    BEIDOU = "BEIDOU"  # BeiDou Time
    ET     = "ET"      # Ephemeris Time
    GALILEO = "GALILEO"  # Galileo System Time
    GLONASS = "GLONASS"  # GLONASS Time
    GMST   = "GMST"    # Greenwich Mean Sidereal Time
    GPS    = "GPS"     # Global Positioning System
    MET    = "MET"     # Mission Elapsed Time (spec body §3.2.3.2 only)
    MRT    = "MRT"     # Mission Relative Time (spec body §3.2.3.2 only)
    NAVIC  = "NAVIC"   # Navigation with Indian Constellation
    SCLK   = "SCLK"   # Spacecraft Clock (receiver)
    TAI    = "TAI"     # International Atomic Time
    TCB    = "TCB"     # Barycentric Coordinate Time
    TDB    = "TDB"     # Barycentric Dynamical Time
    TCG    = "TCG"     # Geocentric Coordinate Time
    TT     = "TT"      # Terrestrial Time
    UT1    = "UT1"     # Universal Time
    UTC    = "UTC"     # Coordinated Universal Time


class ManCovRefFrame(StrEnum):
    """Valid values for ``MAN_REF_FRAME`` and ``COV_REF_FRAME`` keywords (CCSDS 502.0-B-3 §3.2.4.11).

    Base set (§3.2.4.11 spec body): RSW, RTN, TNW.

    Extended set (Annex B5): SANA Registry of Orbit-Relative Reference Frames —
    https://sanaregistry.org/r/orbit_relative_reference_frames
    """
    # Base set from §3.2.4.11 spec body
    RSW          = "RSW"           # Another name for 'Radial, Transverse, Normal'
    RTN          = "RTN"           # Radial, Transverse, Normal
    TNW          = "TNW"           # x-axis along velocity, W along angular momentum, N completing right-hand system
    # Extended set from SANA B5 registry
    EQW_INERTIAL  = "EQW_INERTIAL"
    LVLH_INERTIAL = "LVLH_INERTIAL"
    LVLH_ROTATING = "LVLH_ROTATING"
    NSW_INERTIAL  = "NSW_INERTIAL"
    NSW_ROTATING  = "NSW_ROTATING"
    NTW_INERTIAL  = "NTW_INERTIAL"
    NTW_ROTATING  = "NTW_ROTATING"
    PQW_INERTIAL  = "PQW_INERTIAL"
    RSW_INERTIAL  = "RSW_INERTIAL"
    RSW_ROTATING  = "RSW_ROTATING"
    SEZ_INERTIAL  = "SEZ_INERTIAL"
    SEZ_ROTATING  = "SEZ_ROTATING"
    TNW_INERTIAL  = "TNW_INERTIAL"
    TNW_ROTATING  = "TNW_ROTATING"
    VNC_INERTIAL  = "VNC_INERTIAL"
    VNC_ROTATING  = "VNC_ROTATING"


class Interpolation(StrEnum):
    """Valid values for the ``INTERPOLATION`` keyword (CCSDS 502.0-B-3 §5.2.3 / §6.2.5).

    Defined directly in the spec body; not a SANA registry field.
    PROPAGATE is valid for OCM only (§6.2.5); OEM restricts to HERMITE, LAGRANGE, LINEAR
    and enforces this via a field validator.
    """
    HERMITE   = "HERMITE"
    LAGRANGE  = "LAGRANGE"
    LINEAR    = "LINEAR"
    PROPAGATE = "PROPAGATE"  # OCM only (§6.2.5)


class ManeuverBasis(StrEnum):
    """Valid values for the ``MAN_BASIS`` keyword (CCSDS 502.0-B-3 §6.2.8, table 6-7).

    Defined directly in the spec body; not a SANA registry field.
    """
    CANDIDATE   = "CANDIDATE"
    PLANNED     = "PLANNED"
    ANTICIPATED = "ANTICIPATED"
    TELEMETRY   = "TELEMETRY"
    DETERMINED  = "DETERMINED"
    SIMULATED   = "SIMULATED"
    OTHER       = "OTHER"


class MeanElementTheory(StrEnum):
    """Valid values for the ``MEAN_ELEMENT_THEORY`` keyword (CCSDS 502.0-B-3 §4.2.3, table 4-2).

    Values are those given as examples in the spec body; PPT3 is referenced in §4.2.4.7
    and the conditional rules for MEAN_MOTION_DOT / MEAN_MOTION_DDOT.
    """
    SGP     = "SGP"
    SGP4    = "SGP4"
    SGP4_XP = "SGP4-XP"
    DSST    = "DSST"
    USM     = "USM"
    PPT3    = "PPT3"


class ObjectType(StrEnum):
    """Valid values for the ``OBJECT_TYPE`` keyword (Annex B11).

    Authoritative source: SANA Registry of Object Types —
    https://sanaregistry.org/r/object_types
    """
    PAYLOAD      = "PAYLOAD"
    ROCKET_BODY  = "ROCKET BODY"
    DEBRIS       = "DEBRIS"
    UNKNOWN      = "UNKNOWN"
    OTHER        = "OTHER"


class OperationalStatus(StrEnum):
    """Valid values for the ``OPS_STATUS`` keyword (Annex B12).

    Authoritative source: SANA Registry of Operational Status of Space Object —
    https://sanaregistry.org/r/operational_status
    """
    BACKUP_STORAGE_STANDBY      = "BACKUP_STORAGE_STANDBY"
    DEAD                        = "DEAD"
    DECAYED                     = "DECAYED"
    DEGRADED_OPERATIONS         = "DEGRADED_OPERATIONS"
    EXTENDED_MISSION            = "EXTENDED_MISSION"
    NONOPERATIONAL              = "NONOPERATIONAL"
    OPERATIONAL_MANEUVERABLE    = "OPERATIONAL_MANEUVERABLE"
    OPERATIONAL_NONMANEUVERABLE = "OPERATIONAL_NONMANEUVERABLE"
    REENTRY_MODE                = "REENTRY_MODE"
    UNKNOWN                     = "UNKNOWN"


class OrbitalElements(StrEnum):
    """Valid values for the ``TRAJ_TYPE`` keyword (Annex B7).

    Also used as the orbital-element portion of ``COV_TYPE`` (Annex B8 allows any
    TRAJ_TYPE value as a covariance type).

    Authoritative source: SANA Registry of Orbital Elements —
    https://sanaregistry.org/r/orbital_elements
    """
    ADBARV           = "ADBARV"
    CARTP            = "CARTP"
    CARTPV           = "CARTPV"
    CARTPVA          = "CARTPVA"
    DELAUNAY         = "DELAUNAY"
    DELAUNAYMOD      = "DELAUNAYMOD"
    EQUINOCTIAL      = "EQUINOCTIAL"
    EQUINOCTIALMOD   = "EQUINOCTIALMOD"
    GEODETIC         = "GEODETIC"
    KEPLERIAN        = "KEPLERIAN"
    KEPLERIANMEAN    = "KEPLERIANMEAN"
    KEPLERIANMEANSGP_4 = "KEPLERIANMEANSGP-4"
    LDBARV           = "LDBARV"
    ONSTATION        = "ONSTATION"
    POINCARE         = "POINCARE"


class CovarianceType(StrEnum):
    """Valid values for the event-based portion of the ``COV_TYPE`` keyword (Annex B8).

    ``COV_TYPE`` accepts either an ``OrbitalElements`` value (uncertainties in orbital
    elements) or one of these event-based covariance types that include time uncertainties.

    Authoritative source: SANA Registry of Covariance Representations —
    https://sanaregistry.org/r/orbital_covariance_matrix_types
    """
    SIG3EIGVEC3      = "SIG3EIGVEC3"
    TADBARV          = "TADBARV"
    TCARTP           = "TCARTP"
    TCARTPV          = "TCARTPV"
    TCARTPVA         = "TCARTPVA"
    TDELAUNAY        = "TDELAUNAY"
    TDELAUNAYMOD     = "TDELAUNAYMOD"
    TEQUINOCTIALMOD_N = "TEQUINOCTIALMOD_N"
    TEQUINOCTIALMOD_P = "TEQUINOCTIALMOD_P"
    TEQUINOCTIAL_N   = "TEQUINOCTIAL_N"
    TEQUINOCTIAL_P   = "TEQUINOCTIAL_P"
    TGEODETIC        = "TGEODETIC"
    TKEPLERIAN       = "TKEPLERIAN"
    TKEPLERIANMEAN   = "TKEPLERIANMEAN"
    TLDBARV          = "TLDBARV"
    TPOINCARE        = "TPOINCARE"
    TSIG3EIGVEC3     = "TSIG3EIGVEC3"


class CovarianceOrdering(StrEnum):
    """Valid values for the ``COV_ORDERING`` keyword (CCSDS 502.0-B-3 §6.2.7, table 6-6).

    Defined directly in the spec body; not a SANA registry field.
    """
    LTM    = "LTM"
    UTM    = "UTM"
    FULL   = "FULL"
    LTMWCC = "LTMWCC"
    UTMWCC = "UTMWCC"


class DutyCycleType(StrEnum):
    """Valid values for the ``DC_TYPE`` keyword (CCSDS 502.0-B-3 §6.2.8, table 6-7).

    Defined directly in the spec body; not a SANA registry field.
    """
    CONTINUOUS    = "CONTINUOUS"
    TIME          = "TIME"
    TIME_AND_ANGLE = "TIME_AND_ANGLE"


class ShadowModel(StrEnum):
    """Valid values for the ``SHADOW_MODEL`` keyword (CCSDS 502.0-B-3 §6.2.9, table 6-10).

    Defined directly in the spec body; not a SANA registry field.
    """
    NONE       = "NONE"
    CYLINDRICAL = "CYLINDRICAL"
    CONE       = "CONE"
    DUAL_CONE  = "DUAL_CONE"
