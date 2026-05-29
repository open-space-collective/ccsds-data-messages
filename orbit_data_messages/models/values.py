"""StrEnum classes for CCSDS ODM controlled vocabulary.

Covers orbit centers (``CenterName``), reference frames (``RefFrame``), time
systems (``TimeSystem``), and maneuver/covariance reference frames
(``ManCovRefFrame``).  Values are taken directly from the authoritative SANA
registries cited in CCSDS 502.0-B-3 Annex B.
"""
from enum import StrEnum


class CenterName(StrEnum):
    """Valid values for the ``CENTER_NAME`` keyword (CCSDS 502.0-B-3 Annex B2).

    Authoritative source: SANA Registry of Orbit Centers —
    https://sanaregistry.org/r/orbit_centers

    Note:
        Member names differ from values where the SANA string contains
        characters illegal in Python identifiers (spaces, hyphens, slashes,
        leading digits). ``member.value`` always returns the authoritative
        SANA string.
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

    Authoritative source: SANA Registry of Celestial Body Reference Frames (Annex B4) —
    https://sanaregistry.org/r/celestial_body_reference_frames
    """
    EME2000  = "EME2000"   # Earth Mean Equator and Equinox of J2000
    GCRF     = "GCRF"      # Geocentric Celestial Reference Frame
    GRC      = "GRC"       # Greenwich Rotating Coordinates
    ICRF     = "ICRF"      # International Celestial Reference Frame
    ITRF2000 = "ITRF2000"  # International Terrestrial Reference Frame 2000
    ITRF_93  = "ITRF-93"   # International Terrestrial Reference Frame 1993
    ITRF_97  = "ITRF-97"   # International Terrestrial Reference Frame 1997
    MCI      = "MCI"       # Mars Centered Inertial
    TDR      = "TDR"       # True of Date, Rotating
    TEME     = "TEME"      # True Equator Mean Equinox (only used in OMMs, not OPMs)
    TOD      = "TOD"       # True of Date


class TimeSystem(StrEnum):
    """Valid values for the ``TIME_SYSTEM`` keyword (CCSDS 502.0-B-3 §3.2.3.2).

    Authoritative source: SANA Registry of Time Systems (Annex B3) —
    https://sanaregistry.org/r/time_systems
    """
    GMST = "GMST"  # Greenwich Mean Sidereal Time
    GPS  = "GPS"   # Global Positioning System
    MET  = "MET"   # Mission Elapsed Time
    MRT  = "MRT"   # Mission Relative Time
    SCLK = "SCLK"  # Spacecraft Clock (receiver)
    TAI  = "TAI"   # International Atomic Time
    TCB  = "TCB"   # Barycentric Coordinate Time
    TDB  = "TDB"   # Barycentric Dynamical Time
    TCG  = "TCG"   # Geocentric Coordinate Time
    TT   = "TT"    # Terrestrial Time
    UT1  = "UT1"   # Universal Time
    UTC  = "UTC"   # Coordinated Universal Time


class ManCovRefFrame(StrEnum):
    """Valid values for ``MAN_REF_FRAME`` and ``COV_REF_FRAME`` keywords (CCSDS 502.0-B-3 §3.2.4.11).

    Authoritative source: SANA Registry of Orbit-Relative Reference Frames (Annex B5) —
    https://sanaregistry.org/r/orbit_relative_reference_frames
    """
    RSW = "RSW"  # Another name for 'Radial, Transverse, Normal'
    RTN = "RTN"  # Radial, Transverse, Normal
    TNW = "TNW"  # x-axis along velocity, W along angular momentum, N completing right-hand system
