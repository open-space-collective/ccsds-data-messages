"""
Strongly-typed KVN lexer.

Applies the line classification rules of sections 7.3-7.8. No knowledge of
specific message types or keyword semantics: callers receive a flat list of
typed line objects and walk it with isinstance dispatch.
"""

from __future__ import annotations

import re
import warnings
from typing import NamedTuple

# Section 7.4.4: keywords are all-uppercase, may contain digits and underscores.
_KEYWORD_PATTERN: str = r"[A-Z][A-Z0-9_]*"

# Section 7.4.6: whitespace around '=' is not significant.
# Section 7.4.7: trailing whitespace is not significant.
_KV_RE: re.Pattern[str] = re.compile(rf"^({_KEYWORD_PATTERN})\s*=\s*(.*?)\s*$")

# Section 7.8.5: COMMENT keyword followed by at least one space, then free text.
_COMMENT_RE: re.Pattern[str] = re.compile(r"^COMMENT\s+(.*?)\s*$")

# Section 7.4.2: *_START and *_STOP are standalone keywords (no '=' sign).
_DELIMITER_RE: re.Pattern[str] = re.compile(rf"^({_KEYWORD_PATTERN})$")

# Section 7.7.1.1, 7.7.3.6: inline unit suffix '[unit]' may follow a value; strip it.
_INLINE_UNIT_RE: re.Pattern[str] = re.compile(r"\s+\[.*?\]\s*$")

# Section 7.3.2: line length limit for OPM/OMM/OEM (OCM has no limit, per 7.3.3).
ODM_MAX_LINE_LENGTH: int = 254

# Section 7.3.4: only printable ASCII (0x20-0x7E) is permitted; control characters
# (e.g. TAB) are forbidden, except line terminators, already stripped by splitlines().
_NON_PRINTABLE_ASCII_RE: re.Pattern[str] = re.compile(r"[^\x20-\x7e]")

# Diagnostics only (do not change classification): catch malformed lines that would
# otherwise fall through to DataLine and be silently skipped by all readers.
_BARE_COMMENT_RE: re.Pattern[str] = re.compile(r"^COMMENT$")
_MIXED_CASE_KV_RE: re.Pattern[str] = re.compile(r"^[A-Za-z][A-Za-z0-9_]*\s*=")


class BlankLine(NamedTuple):
    """Section 7.3.5: blank or whitespace-only line. Carries no information."""


class CommentLine(NamedTuple):
    """Section 7.8.5: COMMENT keyword followed by free-text."""

    text: str


class BlockStartLine(NamedTuple):
    """Section 7.4.2: standalone *_START keyword. block_name is the prefix before _START."""

    block_name: str


class BlockStopLine(NamedTuple):
    """Section 7.4.2: standalone *_STOP keyword. block_name is the prefix before _STOP."""

    block_name: str


class KeyValueLine(NamedTuple):
    """Section 7.4.1: KEY = VALUE assignment. Inline unit suffixes are already stripped."""

    keyword: str
    value: str


class DataLine(NamedTuple):
    """Raw numeric row (ephemeris, covariance, maneuver). Everything that is not another type."""

    text: str


KVNLine = (
    BlankLine | CommentLine | BlockStartLine | BlockStopLine | KeyValueLine | DataLine
)


def _classify(stripped_line: str) -> KVNLine:
    if not stripped_line:
        return BlankLine()

    if match := _COMMENT_RE.match(stripped_line):
        return CommentLine(text=match.group(1))

    if _BARE_COMMENT_RE.match(stripped_line):
        # §7.8.5: COMMENT must be followed by at least one space. A bare COMMENT
        # falls through to DataLine like any other unrecognized line, which all
        # readers silently skip — warn so the issue doesn't vanish without a trace.
        # No stacklevel: it would only point inside parse_kvn's own comprehension,
        # itself internal to this module, not at any meaningful external caller.
        # Must be checked before _DELIMITER_RE: "COMMENT" alone also matches that
        # pattern (it's a valid all-caps identifier), which would otherwise return
        # early as a bare-keyword DataLine and skip this warning entirely.
        warnings.warn(  # noqa: B028
            "Bare 'COMMENT' line (no trailing space) is not valid CCSDS KVN (§7.8.5) "
            "and will be ignored by all readers.",
            UserWarning,
        )
        return DataLine(text=stripped_line)

    # Must check delimiter before KV: bare KEYWORD_START has no '=' so KV won't match,
    # but we check here explicitly to emit typed BlockStart/BlockStopLine objects.
    if match := _DELIMITER_RE.match(stripped_line):
        keyword = match.group(1)
        if keyword.endswith("_START"):
            return BlockStartLine(block_name=keyword[: -len("_START")])
        if keyword.endswith("_STOP"):
            return BlockStopLine(block_name=keyword[: -len("_STOP")])
        # Bare keyword that is neither _START nor _STOP: treat as a data row.
        return DataLine(text=stripped_line)

    if match := _KV_RE.match(stripped_line):
        keyword = match.group(1)
        value = _INLINE_UNIT_RE.sub("", match.group(2))
        return KeyValueLine(keyword=keyword, value=value)

    if _MIXED_CASE_KV_RE.match(stripped_line):
        # §7.4.4: keywords must be uppercase. A mixed-case 'Key = value' line falls
        # through to DataLine like any other unrecognized line and is silently
        # skipped by all readers — warn so the issue doesn't vanish without a trace.
        # No stacklevel: see note above.
        warnings.warn(  # noqa: B028
            f"Ignoring keyword line with non-uppercase keyword: {stripped_line!r}. "
            "CCSDS KVN requires uppercase keywords (§7.4.4).",
            UserWarning,
        )

    return DataLine(text=stripped_line)


def parse_kvn(text: str, *, max_line_length: int | None = None) -> list[KVNLine]:
    """
    Lex a KVN document into a flat list of typed line objects.

    Applies sections 7.3.4-7.3.5, 7.4.1-7.4.7, 7.7.1.1, 7.7.3.6, 7.8.5.
    BlankLine instances are included; callers skip them with isinstance checks.

    Args:
        text: Full text of the KVN document.
        max_line_length: When set, warn (do not reject) on lines exceeding this
            many characters, excluding the line terminator (§7.3.2: 254 for
            OPM/OMM/OEM). Pass None (the default) for formats with no limit,
            e.g. OCM (§7.3.3).

    Returns:
        Ordered list of KVNLine objects, one per input line.
    """
    lines: list[str] = text.splitlines()
    for line_number, raw_line in enumerate(lines, start=1):
        # No stacklevel on either warning below: parse_kvn is called through several
        # internal layers (reader -> parse_kvn), so no fixed stacklevel reaches a
        # meaningful external caller.
        if max_line_length is not None and len(raw_line) > max_line_length:
            warnings.warn(  # noqa: B028
                f"Line {line_number} is {len(raw_line)} characters, exceeding the "
                f"{max_line_length}-character limit (§7.3.2): {raw_line[:80]!r}...",
                UserWarning,
            )
        if bad_chars := sorted(set(_NON_PRINTABLE_ASCII_RE.findall(raw_line))):
            warnings.warn(  # noqa: B028
                f"Line {line_number} contains non-printable-ASCII or control "
                f"characters {bad_chars!r} (§7.3.4): {raw_line[:80]!r}...",
                UserWarning,
            )
    return [_classify(raw_line.strip()) for raw_line in lines]
