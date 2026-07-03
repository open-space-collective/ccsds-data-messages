# Copyright (c) Loft Orbital Solutions Inc.
"""
CCSDS Data Messages library.

Quick start - read and write::

    from ccsds_data_messages import read, write, OEM

    msg = read("my_file.oem")
    write(msg, "output.xml")

Quick start - in-memory::

    from ccsds_data_messages import read_string, write_string, MessageFormat, MessageType

    content = write_string(msg, MessageFormat.KVN)
    msg = read_string(content, MessageFormat.KVN, MessageType.OPM)

Quick start - construct a message::

    from ccsds_data_messages import OPM
    from ccsds_data_messages.values import CenterName, RefFrame, TimeSystem

    opm = (
        OPM.builder()
        .header(originator="LOFT")
        .metadata(
            object_name="ISS", object_id="1998-067A",
            center_name=CenterName.EARTH, ref_frame=RefFrame.GCRF,
            time_system=TimeSystem.UTC,
        )
        .state_vector(
            epoch="2024-001T00:00:00.000Z",
            x=6778.0, y=0.0, z=0.0,
            x_dot=0.0, y_dot=7.784, z_dot=0.0,
        )
        .build()
    )
"""

from ccsds_data_messages.exceptions import CCSDSError
from ccsds_data_messages.exceptions import DetectionError
from ccsds_data_messages.exceptions import ParseError
from ccsds_data_messages.exceptions import SpecViolationError
from ccsds_data_messages.exceptions import UnsupportedAdapterError
from ccsds_data_messages.io import MessageFormat
from ccsds_data_messages.io import MessageReaderPort
from ccsds_data_messages.io import MessageType
from ccsds_data_messages.io import MessageWriterPort
from ccsds_data_messages.io import WriterOptions
from ccsds_data_messages.io import read
from ccsds_data_messages.io import read_ocm
from ccsds_data_messages.io import read_oem
from ccsds_data_messages.io import read_omm
from ccsds_data_messages.io import read_opm
from ccsds_data_messages.io import read_string
from ccsds_data_messages.io import write
from ccsds_data_messages.io import write_ocm
from ccsds_data_messages.io import write_oem
from ccsds_data_messages.io import write_omm
from ccsds_data_messages.io import write_opm
from ccsds_data_messages.io import write_string
from ccsds_data_messages.models import OCM
from ccsds_data_messages.models import OEM
from ccsds_data_messages.models import OMM
from ccsds_data_messages.models import OPM
from ccsds_data_messages.models import CCSDSDataMessage
from ccsds_data_messages.models import oem_to_tracss_ocm

__all__ = [
    # Exceptions
    "CCSDSError",
    "DetectionError",
    "ParseError",
    "SpecViolationError",
    "UnsupportedAdapterError",
    # Concrete message types (spec abbreviations are canonical per CCSDS 502.0-B-3 section 1.2)
    "OCM",
    "OEM",
    "OMM",
    "OPM",
    # Abstract base
    "CCSDSDataMessage",
    # Conversions
    "oem_to_tracss_ocm",
    # Typed enums
    "MessageFormat",
    "MessageReaderPort",
    "MessageType",
    "MessageWriterPort",
    # Options and extension points
    "WriterOptions",
    # Generic I/O
    "read",
    "read_ocm",
    # Type-specific file I/O
    "read_oem",
    "read_omm",
    "read_opm",
    "read_string",
    "write",
    "write_ocm",
    "write_oem",
    "write_omm",
    "write_opm",
    "write_string",
]
