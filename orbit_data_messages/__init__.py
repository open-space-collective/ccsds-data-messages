"""
CCSDS Data Messages library.

Quick start::

    from orbit_data_messages import read, write, OEM

    msg = read("my_file.oem")
    write(msg, "output.xml")
"""
from orbit_data_messages.models import CCSDSDataMessage
from orbit_data_messages.models import OEM
from orbit_data_messages.models import OrbitEphemerisMessage
from orbit_data_messages.models import OMM
from orbit_data_messages.models import OrbitMeanElementsMessage
from orbit_data_messages.models import OPM
from orbit_data_messages.models import OrbitParameterMessage
from orbit_data_messages.models import OCM
from orbit_data_messages.models import OrbitComprehensiveMessage
from orbit_data_messages.io import read
from orbit_data_messages.io import read_oem
from orbit_data_messages.io import read_opm
from orbit_data_messages.io import read_omm
from orbit_data_messages.io import read_ocm
from orbit_data_messages.io import write
from orbit_data_messages.io import write_oem
from orbit_data_messages.io import write_opm
from orbit_data_messages.io import write_omm
from orbit_data_messages.io import write_ocm
from orbit_data_messages.io import WriterOptions
from orbit_data_messages.io import MessageReaderPort
from orbit_data_messages.io import MessageWriterPort

__all__ = [
    # Message types
    "CCSDSDataMessage",
    "OEM",
    "OrbitEphemerisMessage",
    "OMM",
    "OrbitMeanElementsMessage",
    "OPM",
    "OrbitParameterMessage",
    "OCM",
    "OrbitComprehensiveMessage",
    # I/O (generic)
    "read",
    "write",
    "WriterOptions",
    # I/O (type-specific)
    "read_oem",
    "read_opm",
    "read_omm",
    "read_ocm",
    "write_oem",
    "write_opm",
    "write_omm",
    "write_ocm",
    # Extension points for custom adapters
    "MessageReaderPort",
    "MessageWriterPort",
]
