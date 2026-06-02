"""
Low-level KVN tokenizer for CCSDS Data Messages.

Implements the parsing rules of CCSDS 502.0-B-3 section 7.3-7.8. This module has no
knowledge of specific message types or keyword semantics: it produces plain
Python dicts only.  Adapters map the result to domain models.
"""
import re
from typing import Any

# Section 7.4.4: keywords are all-uppercase, may contain digits and underscores,
# must not contain blanks.
_KW = r'[A-Z][A-Z0-9_]*'

# Section 7.4.6: any white space immediately preceding or following the '=' sign is
# not significant.  Trailing whitespace on the line is also not significant
# (section 7.4.7).
_KV_RE = re.compile(rf'^({_KW})\s*=\s*(.*?)\s*$')

# Section 7.8.5: comment lines begin with the 'COMMENT' keyword followed by at
# least one space; the remainder of the line is the comment value.
_COMMENT_RE = re.compile(r'^COMMENT\s+(.*?)\s*$')

# Section 7.4.2: *_START and *_STOP keywords are standalone (no '=' assignment).
# Section 7.4.4: uppercase, no blanks, so a bare uppercase-only token is a delimiter.
_DELIMITER_RE = re.compile(rf'^({_KW})$')

# Section 7.7.1.1, section 7.7.3.6: inline unit suffix '[unit]' may follow a value after
# at least one blank; strip it entirely.
_INLINE_UNIT_RE = re.compile(r'\s+\[.*?\]\s*$')


def _classify(line: str) -> tuple[str, str | None, str | None]:
    """
    Classify a single stripped KVN line and extract its key and value.

    Args:
        line (str): A single stripped line from the KVN document.

    Returns:
        tuple[str, str | None, str | None]: A ``(kind, key, value)`` triple.
        ``kind`` is one of: ``'blank'`` (section 7.3.5), ``'percent'`` (ignored
        metadata), ``'comment'`` (section 7.8.5), ``'start'`` (``*_START`` opener,
        section 7.4.2), ``'stop'`` (``*_STOP`` closer, section 7.4.2), ``'kv'`` (``KEY =
        VALUE``, section 7.4.1), or ``'data'`` (raw ephemeris/covariance/maneuver row).
        ``key`` and ``value`` are ``None`` for kinds that do not carry them.
    """
    if not line:
        return ('blank', None, None)

    # Section 7.3.5: lines beginning with '%' carry no assignable meaning.
    if line.startswith('%'):
        return ('percent', None, None)

    # Section 7.8.5: COMMENT keyword (exception to KVN; no '=' sign).
    m: re.Match[str] | None = _COMMENT_RE.match(line)
    if m:
        return ('comment', None, m.group(1))

    # Section 7.4.2: *_START / *_STOP delimiters are standalone keywords with no
    # '=' and no value.
    m: re.Match[str] | None = _DELIMITER_RE.match(line)
    if m:
        kw: str = m.group(1)
        if kw.endswith('_START'):
            return ('start', kw[: -len('_START')], None)
        if kw.endswith('_STOP'):
            return ('stop', kw[: -len('_STOP')], None)
        # Bare keyword that is neither _START nor _STOP: treat as data.
        return ('data', None, line)

    # Section 7.4.1: KEY = VALUE assignment; strip inline unit suffix (section 7.7.1.1,
    # section 7.7.3.6).
    m: re.Match[str] | None = _KV_RE.match(line)
    if m:
        key: str = m.group(1)
        value: str = _INLINE_UNIT_RE.sub('', m.group(2))
        return ('kv', key, value)

    # Anything else is a raw data line (epoch row, covariance row, etc.).
    return ('data', None, line)


def parse_kvn(text: str) -> dict[str, Any]:
    """
    Parse a KVN document into a structured dictionary.

    Applies section 7.3.5 (blank lines), section 7.4.2 (``COMMENT``/``*_START``/``*_STOP``),
    section 7.4.4 (uppercase keywords), section 7.4.6-7 (whitespace), section 7.7.1.1/section 7.7.3.6
    (inline unit suffix stripped), section 7.8.5 (comment syntax).

    Args:
        text (str): Full text of the KVN document.

    Returns:
        dict[str, Any]: A dict with keys:

        - ``header_kvs`` (dict[str, str]): Keyword-value pairs from the
          pre-block header section.
        - ``header_comments`` (list[str]): Comment texts from the header.
        - ``header_ordered_items`` (list[tuple]): Ordered ``(kind, key, value)``
          triples for all pre-block content; needed by flat-format readers (``OPM``,
          ``OMM``) to preserve document order across repeated keywords.
        - ``sections`` (list[dict[str, Any]]): Ordered body sections, each a
          ``'block'`` dict (with ``delimiter``, ``kvs``, ``comments``,
          ``data_lines``, ``ordered_items``) or a ``'data'`` dict (with ``kvs``,
          ``data_lines``, ``comments``).
    """
    header_kvs: dict[str, str] = {}
    header_comments: list[str] = []
    # Ordered (kind, key, value) triples for all pre-block content.
    # Needed for OPM/OMM where repeated keywords (e.g. MAN_EPOCH_IGNITION
    # for multiple maneuvers) must be processed in document order.
    header_ordered_items: list[tuple[str, str | None, str | None]] = []
    sections: list[dict[str, Any]] = []

    # Current open block (set when *_START seen, cleared on *_STOP).
    current_block: dict[str, Any] | None = None

    # Accumulator for lines/KVs/comments that fall between named blocks.
    # 'kvs' captures KEY = VALUE lines that appear outside any block
    # (e.g. OPM/OMM state-vector data after META_STOP: section 7.4.1).
    pending_kvs: dict[str, str] = {}
    pending_data: list[str] = []
    pending_comments: list[str] = []

    def _flush_pending() -> None:
        """
        Emit any accumulated inter-block content as a 'data' section.
        """
        if pending_kvs or pending_data or pending_comments:
            sections.append({
                "type": "data",
                "kvs": dict(pending_kvs),
                "data_lines": list(pending_data),
                "comments": list(pending_comments),
            })
        pending_kvs.clear()
        pending_data.clear()
        pending_comments.clear()

    header_done: bool = False  # True once the first block/data section starts

    for raw_line in text.splitlines():
        kind, key, value = _classify(raw_line.strip())

        if kind in ('blank', 'percent'):
            # Section 7.3.5: blank lines ignored; '%' lines carry no meaning.
            continue

        if kind == 'comment':
            if current_block is not None:
                # Section 7.8: comment inside a named block.
                current_block['comments'].append(value)
                current_block['ordered_items'].append(('comment', None, value))
            elif header_done:
                # Comment at the start of an inter-block data section.
                pending_comments.append(value)
            else:
                # Section 7.8: comment in the header section.
                header_comments.append(value)
                header_ordered_items.append(('comment', None, value))
            continue

        if kind == 'start':
            # Section 7.4.2: opening delimiter; begin a new named block.
            if header_done:
                _flush_pending()
            else:
                header_done = True
            current_block = {
                "type": "block",
                "delimiter": key,
                "kvs": {},
                "comments": [],
                "data_lines": [],
                # ``ordered_items`` preserves the full token sequence so adapters
                # can handle blocks where the same key repeats (e.g. OEM
                # COVARIANCE with multiple EPOCH entries).
                "ordered_items": [],
            }
            continue

        if kind == 'stop':
            # Section 7.4.2: closing delimiter; seal the current block.
            if current_block is not None:
                sections.append(current_block)
                current_block = None
            continue

        if kind == 'kv':
            if current_block is not None:
                current_block['kvs'][key] = value          # Last value wins.
                current_block['ordered_items'].append(('kv', key, value))
            elif not header_done:
                header_kvs[key]: str = value                    # Last value wins.
                header_ordered_items.append(('kv', key, value))
            else:
                # KV pair between named blocks: store in the pending ``KV`` dict
                # so adapters can read them as typed fields (OPM state vector,
                # OMM mean elements, etc.).
                pending_kvs[key]: str = value
            continue

        if kind == 'data':
            if current_block is not None:
                current_block['data_lines'].append(value)
                current_block['ordered_items'].append(('data', None, value))
            else:
                header_done: bool = True
                pending_data.append(value)

    # Flush any remaining inter-block content after the last block.
    _flush_pending()

    return {
        "header_kvs": header_kvs,
        "header_comments": header_comments,
        "header_ordered_items": header_ordered_items,
        "sections": sections,
    }


def split_blocks(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Flatten a ``parse_kvn()`` result into an ordered list of typed section dicts.

    The first element is always the synthetic ``'header'`` section.
    Remaining elements appear in document order: named ``'block'`` sections (``META``, ``TRAJ``, ``OD``, …)
    and inter-block ``'data'`` sections (``'data'``). ``'data'`` sections are created for inter-block content
    that does not fit into a named block (e.g. OPM state vector data after ``META_STOP``: section 7.4.1).

    Args:
        raw (dict[str, Any]): The dict returned by ``parse_kvn()``.

    Returns:
        list[dict[str, Any]]: Ordered list where the first entry is
        ``{'type': 'header', 'kvs': ..., 'comments': ..., 'ordered_items': ...}``
        followed by ``'block'`` dicts (keys: ``type``, ``delimiter``, ``kvs``,
        ``comments``, ``data_lines``, ``ordered_items``) and ``'data'`` dicts
        (keys: ``type``, ``kvs``, ``data_lines``, ``comments``).
    """
    result: list[dict[str, Any]] = [
        {
            "type": "header",
            "kvs": raw["header_kvs"],
            "comments": raw["header_comments"],
            "ordered_items": raw.get("header_ordered_items", []),
        }
    ]
    result.extend(raw["sections"])
    return result
