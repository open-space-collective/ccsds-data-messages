"""I/O functions for reading and writing CCSDS ODM files."""

from orbit_data_messages.io.options import WriterOptions
from orbit_data_messages.io.ports import MessageReaderPort
from orbit_data_messages.io.ports import MessageWriterPort
from orbit_data_messages.io.reader import read
from orbit_data_messages.io.reader import read_oem
from orbit_data_messages.io.reader import read_opm
from orbit_data_messages.io.reader import read_omm
from orbit_data_messages.io.reader import read_ocm
from orbit_data_messages.io.registry import register_reader
from orbit_data_messages.io.registry import register_writer
from orbit_data_messages.io.writer import write
from orbit_data_messages.io.writer import write_oem
from orbit_data_messages.io.writer import write_opm
from orbit_data_messages.io.writer import write_omm
from orbit_data_messages.io.writer import write_ocm

__all__ = [
    "read",
    "read_oem",
    "read_opm",
    "read_omm",
    "read_ocm",
    "write",
    "write_oem",
    "write_opm",
    "write_omm",
    "write_ocm",
    "WriterOptions",
    "register_reader",
    "register_writer",
    # Extension points for custom adapters.
    "MessageReaderPort",
    "MessageWriterPort",
]
