import pytest

from hureva.events import Event
from hureva.transitions import detect_event


@pytest.mark.parametrize(
    "before,after,expected",
    [
        # fireable transitions
        ("draft", "in_review", Event.ready_for_review),
        ("in_review", "approved", Event.approved),
        # new file landing directly in a fireable state
        (None, "in_review", Event.ready_for_review),
        (None, "approved", Event.approved),
        # jump several states -> fire for the landed state
        ("draft", "approved", Event.approved),
        # unchanged status -> dedup, no event
        ("in_review", "in_review", None),
        ("approved", "approved", None),
        # non-fireable landings
        (None, "draft", None),
        ("approved", "implemented", None),
        ("in_review", "archived", None),
        # after missing (deletion) -> nothing
        ("approved", None, None),
    ],
)
def test_detect_event(before, after, expected):
    assert detect_event(before, after) is expected
