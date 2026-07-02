# SPDX-License-Identifier: Apache-2.0

"""
Shared parsing/serialization of OCM maneuver data lines (tables 6-8 / 6-9).

OCM maneuver data lines are stored on the model as typed
``ManeuverDataLine`` / ``DeploymentDataLine`` rows, but their column set is
declared per block by ``MAN_COMPOSITION`` rather than fixed at class-definition
time. Both the KVN and XML adapters therefore need the same
composition-driven column<->field mapping; it lives here so it is written once.

Trajectory and covariance data lines are *not* handled here: their column schema
is registry-driven (``TRAJ_TYPE`` / ``COV_TYPE``), so they remain raw strings.
"""

from __future__ import annotations

from ccsds_data_messages.exceptions import ParseError
from ccsds_data_messages.io._utils import build_keyword_map
from ccsds_data_messages.io._utils import format_value
from ccsds_data_messages.models.ocm import OCM

_MAN_SPEC = OCM.ManeuverSpecification
_TIME_COLUMNS: frozenset[str] = frozenset({"TIME_ABSOLUTE", "TIME_RELATIVE"})

ManeuverRow = _MAN_SPEC.ManeuverDataLine | _MAN_SPEC.DeploymentDataLine


def _composition_columns(composition: str) -> list[str]:
    return [element.strip() for element in composition.split(",") if element.strip()]


def _row_class(columns: list[str]) -> type[ManeuverRow]:
    """Pick the row model for a composition: deployment (table 6-9) or propulsive."""
    if any(column.upper().startswith("DEPLOY") for column in columns):
        return _MAN_SPEC.DeploymentDataLine
    return _MAN_SPEC.ManeuverDataLine


def parse_maneuver_rows(composition: str, raw_lines: list[str]) -> list[ManeuverRow]:
    """
    Parse raw maneuver data lines into typed rows keyed by MAN_COMPOSITION.

    Each column keyword maps to its row-model field via ``build_keyword_map``; the
    single time column maps to ``time_tag``. Pydantic then coerces each token and
    enforces the per-element constraints declared on the row model (THR_INTERP
    'ON'/'OFF', DEPLOY_MASS <= 0.0).

    Raises:
        ParseError: If a line's token count differs from the column count, or a
            column keyword has no corresponding row field.
    """
    columns: list[str] = _composition_columns(composition)
    row_class: type[ManeuverRow] = _row_class(columns)
    keyword_to_field: dict[str, str] = build_keyword_map(row_class)
    rows: list[ManeuverRow] = []
    for raw in raw_lines:
        tokens: list[str] = raw.split()
        if len(tokens) != len(columns):
            raise ParseError(
                f"OCM: maneuver line has {len(tokens)} value(s) but MAN_COMPOSITION "
                f"declares {len(columns)}: {raw!r}"
            )
        kwargs: dict[str, str] = {}
        for column, token in zip(columns, tokens, strict=True):
            if (key := column.upper()) in _TIME_COLUMNS:
                kwargs["time_tag"] = token
                continue
            if (field := keyword_to_field.get(key)) is None:
                raise ParseError(
                    f"OCM: unrecognized maneuver column {column!r} in MAN_COMPOSITION."
                )
            kwargs[field] = token
        rows.append(row_class(**kwargs))
    return rows


def serialize_maneuver_rows(
    composition: str,
    rows: list[ManeuverRow],
    float_formats: dict[str, str] | None = None,
) -> list[str]:
    """
    Serialize typed maneuver rows to space-delimited lines in MAN_COMPOSITION order.

    Numeric values use ``format_value``. A per-column override may be supplied via
    ``float_formats`` (keyed by CCSDS column keyword, e.g. ``"DEPLOY_DV_X"``) -
    the same ``WriterOptions.float_formats`` mechanism the KVN writer applies to
    every other field, so a caller can force e.g. floating-point notation for a
    column: ``float_formats={"DEPLOY_DV_X": " .8e"}``. With no override, the default
    ``.15g`` (<= 15 significant digits) is used, matching the OEM writer. The
    override always reflects the row's current value, so it can never emit a stale
    number the way retaining the source string could. The time column reads
    ``time_tag`` verbatim.
    """
    formats: dict[str, str] = float_formats or {}
    columns: list[str] = _composition_columns(composition)
    keyword_to_field: dict[str, str] = build_keyword_map(_row_class(columns))
    lines: list[str] = []
    for row in rows:
        tokens: list[str] = []
        for column in columns:
            if (key := column.upper()) in _TIME_COLUMNS:
                tokens.append(row.time_tag)
            else:
                value = getattr(row, keyword_to_field[key])
                tokens.append(format_value(value, formats.get(key)))
        lines.append(" ".join(tokens))
    return lines
