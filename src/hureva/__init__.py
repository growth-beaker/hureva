"""hureva — the portable core of the spec review & approval workflow.

This package is the canonical "approval & gate" layer (§3): Pydantic models for
the frontmatter/roster/defaults contract, two-commit transition detection,
role→person→channel routing behind a sender interface, and the status gate. The
GitHub Actions wrap this library; they do not reimplement its logic.
"""

from __future__ import annotations

from .events import Event, Notification
from .models import Defaults, Person, Roster, SpecFrontmatter, Status
from .transitions import detect_event

__all__ = [
    "Event",
    "Notification",
    "Defaults",
    "Person",
    "Roster",
    "SpecFrontmatter",
    "Status",
    "detect_event",
]

__version__ = "0.1.0"
