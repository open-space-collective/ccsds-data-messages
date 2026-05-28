"""
Low-level KVN tokenizer for CCSDS Orbit Data Messages.

Implements the parsing rules of CCSDS 502.0-B-3 §7.3–7.8.  This module has no
knowledge of specific message types or keyword semantics — it produces plain
Python dicts only.  Adapters map the result to domain models.
"""
import re

# §7.4.4 — keywords are all-uppercase, may contain digits and underscores,
# must not contain blanks.
_KW = r'[A-Z][A-Z0-9_]*'

# §7.4.6 — any white space immediately preceding or following the '=' sign is
# not significant.  Trailing whitespace on the line is also not significant
# (§7.4.7).
_KV_RE = re.compile(rf'^({_KW})\s*=\s*(.*?)\s*$')

# §7.8.5 — comment lines begin with the 'COMMENT' keyword followed by at
# least one space; the remainder of the line is the comment value.
_COMMENT_RE = re.compile(r'^COMMENT\s+(.*?)\s*$')

# §7.4.2 — *_START and *_STOP keywords are standalone (no '=' assignment).
# §7.4.4 — uppercase, no blanks, so a bare uppercase-only token is a delimiter.
_DELIMITER_RE = re.compile(rf'^({_KW})$')

# §7.7.1.1, §7.7.3.6 — inline unit suffix '[unit]' may follow a value after
# at least one blank; strip it entirely.
_INLINE_UNIT_RE = re.compile(r'\s+\[.*?\]\s*$')


def _classify(line: str) -> tuple[str, str | None, str | None]:
    """
    Return (kind, key, value) for a single stripped line.

    Kinds:
      'blank'     — empty line (§7.3.5)
      'percent'   — line beginning with '%'; treated as ignored metadata
      'comment'   — COMMENT line (§7.8.5)
      'start'     — *_START block opener (§7.4.2)
      'stop'      — *_STOP block closer (§7.4.2)
      'kv'        — KEY = VALUE assignment (§7.4.1)
      'data'      — raw data line (ephemeris / covariance / maneuver row)
    """
    if not line:
        return ('blank', None, None)

    # §7.3.5 — lines beginning with '%' carry no assignable meaning.
    if line.startswith('%'):
        return ('percent', None, None)

    # §7.8.5 — COMMENT keyword (exception to KVN; no '=' sign).
    m = _COMMENT_RE.match(line)
    if m:
        return ('comment', None, m.group(1))

    # §7.4.2 — *_START / *_STOP delimiters are standalone keywords with no
    # '=' and no value.
    m = _DELIMITER_RE.match(line)
    if m:
        kw = m.group(1)
        if kw.endswith('_START'):
            return ('start', kw[: -len('_START')], None)
        if kw.endswith('_STOP'):
            return ('stop', kw[: -len('_STOP')], None)
        # Bare keyword that is neither _START nor _STOP — treat as data.
        return ('data', None, line)

    # §7.4.1 — KEY = VALUE assignment; strip inline unit suffix (§7.7.1.1,
    # §7.7.3.6).
    m = _KV_RE.match(line)
    if m:
        key = m.group(1)
        value = _INLINE_UNIT_RE.sub('', m.group(2))
        return ('kv', key, value)

    # Anything else is a raw data line (epoch row, covariance row, etc.).
    return ('data', None, line)


def parse_kvn(text: str) -> dict:
    """
    Tokenize a KVN document into a structured dict.

    Returns
    -------
    {
        "header_kvs":      dict[str, str]   — header keyword→value pairs
        "header_comments": list[str]         — header comment texts
        "sections":        list[dict]        — ordered body sections
    }

    Each section is one of:

        {"type": "block",
         "delimiter": str,       — block type, e.g. "META", "TRAJ", "OD"
         "kvs": dict[str, str],  — keyword→value pairs inside the block
         "comments": list[str],  — comment texts inside the block
         "data_lines": list[str] — raw data lines inside the block}

        {"type": "data",
         "kvs": dict[str, str],   — KV pairs between named blocks (OPM/OMM data)
         "data_lines": list[str], — raw lines between named blocks (OEM ephemeris)
         "comments": list[str]}   — comment texts at start of data section

    Parsing rules applied
    ---------------------
    §7.3.5   Blank lines are ignored.
    §7.4.2   'COMMENT', '*_START', '*_STOP' are not KEY = VALUE lines.
    §7.4.4   Keywords are uppercase with no blanks.
    §7.4.6   White space around '=' is not significant.
    §7.4.7   Trailing white space on a line is not significant.
    §7.7.1.1 / §7.7.3.6  Inline unit suffix '[…]' is stripped from values.
    §7.8.5   Comment lines begin with 'COMMENT ' (keyword + space).
    """
    header_kvs: dict[str, str] = {}
    header_comments: list[str] = []
    # Ordered (kind, key, value) triples for all pre-block content.
    # Needed for OPM/OMM where repeated keywords (e.g. MAN_EPOCH_IGNITION
    # for multiple maneuvers) must be processed in document order.
    header_ordered_items: list[tuple] = []
    sections: list[dict] = []

    # Current open block (set when *_START seen, cleared on *_STOP).
    current_block: dict | None = None

    # Accumulator for lines/KVs/comments that fall between named blocks.
    # 'kvs' captures KEY = VALUE lines that appear outside any block
    # (e.g. OPM/OMM state-vector data after META_STOP — §7.4.1).
    pending_kvs: dict[str, str] = {}
    pending_data: list[str] = []
    pending_comments: list[str] = []

    def _flush_pending() -> None:
        """Emit any accumulated inter-block content as a 'data' section."""
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

    header_done = False  # True once the first block/data section starts

    for raw_line in text.splitlines():
        kind, key, value = _classify(raw_line.strip())

        if kind in ('blank', 'percent'):
            # §7.3.5 — blank lines ignored; '%' lines carry no meaning.
            continue

        if kind == 'comment':
            if current_block is not None:
                # §7.8 — comment inside a named block.
                current_block['comments'].append(value)
                current_block['ordered_items'].append(('comment', None, value))
            elif header_done:
                # Comment at the start of an inter-block data section.
                pending_comments.append(value)
            else:
                # §7.8 — comment in the header section.
                header_comments.append(value)
                header_ordered_items.append(('comment', None, value))
            continue

        if kind == 'start':
            # §7.4.2 — opening delimiter; begin a new named block.
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
                # ordered_items preserves the full token sequence so adapters
                # can handle blocks where the same key repeats (e.g. OEM
                # COVARIANCE with multiple EPOCH entries).
                "ordered_items": [],
            }
            continue

        if kind == 'stop':
            # §7.4.2 — closing delimiter; seal the current block.
            if current_block is not None:
                sections.append(current_block)
                current_block = None
            continue

        if kind == 'kv':
            if current_block is not None:
                current_block['kvs'][key] = value          # last value wins
                current_block['ordered_items'].append(('kv', key, value))
            elif not header_done:
                header_kvs[key] = value                    # last value wins
                header_ordered_items.append(('kv', key, value))
            else:
                # KV pair between named blocks: store in the pending KV dict
                # so adapters can read them as typed fields (OPM state vector,
                # OMM mean elements, etc.).
                pending_kvs[key] = value
            continue

        if kind == 'data':
            if current_block is not None:
                current_block['data_lines'].append(value)
                current_block['ordered_items'].append(('data', None, value))
            else:
                header_done = True
                pending_data.append(value)

    # Flush any remaining inter-block content after the last block.
    _flush_pending()

    return {
        "header_kvs": header_kvs,
        "header_comments": header_comments,
        "header_ordered_items": header_ordered_items,
        "sections": sections,
    }


def split_blocks(raw: dict) -> list[dict]:
    """
    Flatten a parse_kvn result into an ordered list of typed section dicts.

    Returns
    -------
    [
        {"type": "header",  "kvs": dict, "comments": list},
        {"type": "block",   "delimiter": str, "kvs": dict,
                            "comments": list, "data_lines": list,
                            "ordered_items": list},
        {"type": "data",    "kvs": dict, "data_lines": list, "comments": list},
        ...
    ]

    The first element is always the header.  Remaining elements appear in
    document order and correspond to named blocks (META, TRAJ, OD, …) and
    any inter-block raw data sections.
    """
    result: list[dict] = [
        {
            "type": "header",
            "kvs": raw["header_kvs"],
            "comments": raw["header_comments"],
            "ordered_items": raw.get("header_ordered_items", []),
        }
    ]
    result.extend(raw["sections"])
    return result
