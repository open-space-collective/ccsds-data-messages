# SPDX-License-Identifier: Apache-2.0

"""
CLI: convert an OEM file to a TraCSS-compliant OCM file.

Wraps ``oem_to_tracss_ocm`` (src/ccsds_data_messages/models/conversions.py) with a
thin argparse interface. TraCSS-mandatory metadata not present in the source OEM
(operator, owner, country, contact details, etc.) defaults to Loft Orbital's own
registration details but can be overridden per invocation.
"""

from __future__ import annotations

import argparse

from ccsds_data_messages import oem_to_tracss_ocm
from ccsds_data_messages import read_oem
from ccsds_data_messages import write_ocm


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("oem_path", help="Path to the source OEM file (KVN or XML).")
    parser.add_argument("ocm_path", help="Path to write the resulting OCM file to.")
    parser.add_argument(
        "--traj-basis",
        default="OPERATIONAL",
        choices=["OPERATIONAL", "CANDIDATE"],
        help="Trajectory basis (default: %(default)s).",
    )
    parser.add_argument(
        "--object-designator",
        default="UNKNOWN",
        help="DoD Satellite Catalog Number, or UNKNOWN (default: %(default)s).",
    )
    parser.add_argument(
        "--operator",
        default="Loft Orbital",
        help="Operating organization registered with TraCSS.",
    )
    parser.add_argument(
        "--owner",
        default="Loft Orbital",
        help="Owning organization registered with TraCSS.",
    )
    parser.add_argument(
        "--country", default="US", help="Owner's country (name, code, or abbreviation)."
    )
    parser.add_argument(
        "--originator-address",
        default="321 11th St, San Francisco, CA 94103, USA",
        help="Originator mailing address.",
    )
    parser.add_argument(
        "--originator-email",
        default="satellite-operators@loftorbital.com",
        help="Originator e-mail address.",
    )
    parser.add_argument(
        "--originator-phone",
        default="(415) 993-5638",
        help="Originator phone number.",
    )
    parser.add_argument(
        "--message-id",
        default=None,
        help="Unique message identifier; falls back to the OEM header's MESSAGE_ID when omitted.",
    )
    parser.add_argument(
        "--useable-record-padding",
        type=int,
        default=5,
        help="Data lines at each edge treated as non-useable (default: %(default)s).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    oem = read_oem(args.oem_path)
    ocm = oem_to_tracss_ocm(
        oem,
        traj_basis=args.traj_basis,
        object_designator=args.object_designator,
        operator=args.operator,
        owner=args.owner,
        country=args.country,
        originator_address=args.originator_address,
        originator_email=args.originator_email,
        originator_phone=args.originator_phone,
        message_id=args.message_id,
        useable_record_padding=args.useable_record_padding,
    )
    write_ocm(ocm, args.ocm_path)


if __name__ == "__main__":
    main()
