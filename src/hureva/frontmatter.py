"""Parse and serialize YAML frontmatter on a ``spec.md`` (§4.2).

The frontmatter is the runtime contract, so this module is the single place the
"split the document into frontmatter + body" rule lives. Two entry points:

- :func:`parse_spec` — full validation into a :class:`SpecFrontmatter`.
- :func:`parse_status` — a *lenient* reader that only pulls ``status`` out. Used
  for the *before* version of a spec during transition detection (§7.4), which
  may predate the current schema or be otherwise unparseable as a whole.
"""

from __future__ import annotations

import yaml

from .models import SpecFrontmatter

_FENCE = "---"


class FrontmatterError(ValueError):
    """Raised when a document has no parseable frontmatter block."""


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split ``text`` into (raw_yaml, body).

    Accepts an optional leading BOM/whitespace and a ``---`` fence on its own
    line, matching how docs tools and hand authors write frontmatter.
    """
    stripped = text.lstrip("﻿")
    if not stripped.startswith(_FENCE):
        raise FrontmatterError("document does not start with a '---' frontmatter fence")

    # Everything after the opening fence, split on the closing fence line.
    rest = stripped[len(_FENCE):]
    # Normalize the opening fence's trailing newline away.
    rest = rest.lstrip("\r\n")

    end = _find_closing_fence(rest)
    if end is None:
        raise FrontmatterError("frontmatter block is not closed with a '---' line")

    raw_yaml = rest[:end]
    body = rest[end:]
    # Drop the closing fence line from the body.
    body = body.split("\n", 1)[1] if "\n" in body else ""
    return raw_yaml, body


def _find_closing_fence(text: str) -> int | None:
    """Index in ``text`` of the start of the line that is exactly ``---``."""
    offset = 0
    for line in text.splitlines(keepends=True):
        if line.rstrip("\r\n") == _FENCE:
            return offset
        offset += len(line)
    return None


def load_frontmatter_dict(text: str) -> dict:
    """Parse the frontmatter YAML into a dict (no schema validation)."""
    raw_yaml, _ = split_frontmatter(text)
    data = yaml.safe_load(raw_yaml)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter must be a YAML mapping")
    return data


def parse_spec(text: str) -> SpecFrontmatter:
    """Parse and validate a full spec document into :class:`SpecFrontmatter`."""
    return SpecFrontmatter.model_validate(load_frontmatter_dict(text))


def parse_status(text: str | None) -> str | None:
    """Return just the ``status`` field, tolerating malformed/partial input.

    Returns ``None`` when the text is missing (e.g. the *before* side of a newly
    added file) or has no readable status. Never raises — transition detection
    must survive an unparseable prior version (§7.4).
    """
    if not text:
        return None
    try:
        data = load_frontmatter_dict(text)
    except (FrontmatterError, yaml.YAMLError):
        return None
    status = data.get("status")
    return str(status) if status is not None else None
