"""Transition detection — the one place the "compare two versions" rule lives (§7.4).

A pure function of two status strings. Events fire on frontmatter *transitions*,
not on every push, so the caller reads ``status`` from the push's ``before`` and
``after`` commits and hands both here.

Rules (§7.4):
- Fire only when ``status`` changed, and only for the new status.
- New file (no ``before``) → transition into its initial status.
- Body-only edit (status unchanged) → no event (this is the dedup).
- A push that jumps several states → fire for the state it *landed* in
  (we only look at ``after``, so this is automatic).

Only two statuses are fireable by this action; comments come from the docs tool's
native alerts (§7.3), so ``commented`` is not produced here.
"""

from __future__ import annotations

from .events import Event

# Landed status → event to fire (§7.1). Statuses not present here fire nothing.
_STATUS_TO_EVENT: dict[str, Event] = {
    "in_review": Event.ready_for_review,
    "approved": Event.approved,
}


def detect_event(before_status: str | None, after_status: str | None) -> Event | None:
    """Return the event for a status transition, or ``None``.

    ``before_status`` is ``None`` for a newly added file. ``after_status`` is the
    current status. Returns ``None`` when the status is unchanged or the landed
    status is not one this action notifies on.
    """
    if after_status is None:
        return None
    if before_status == after_status:
        return None
    return _STATUS_TO_EVENT.get(after_status)
