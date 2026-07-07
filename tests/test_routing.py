import pytest

from hureva.events import Event
from hureva.frontmatter import parse_spec
from hureva.routing import (
    RosterResolutionError,
    build_notifications,
    recipients_for_event,
    resolve_channel,
    resolve_recipients,
)


def test_recipients_for_ready_for_review(make_spec):
    spec = parse_spec(make_spec())
    people = recipients_for_event(spec, Event.ready_for_review)
    assert people == ["elena", "sam", "qa-team"]  # approvers + commenters + viewers


def test_recipients_for_approved_is_owner(make_spec):
    spec = parse_spec(make_spec(status="approved", approvers=["elena"], approved_by=["elena"]))
    assert recipients_for_event(spec, Event.approved) == ["chris"]
    assert recipients_for_event(spec, Event.cleared_to_build) == ["chris"]


def test_resolve_channel_prefers_slack(roster):
    r = resolve_channel(roster, "chris")
    assert r.channel == "slack" and r.handle == "@chris"


def test_resolve_channel_falls_back_to_email(roster):
    r = resolve_channel(roster, "sam")
    assert r.channel == "email" and r.handle == "sam@acme.com"


def test_resolve_channel_missing_raises(roster):
    with pytest.raises(RosterResolutionError):
        resolve_channel(roster, "ghost")


def test_resolve_recipients_collects_missing(roster):
    resolved, missing = resolve_recipients(roster, ["chris", "ghost", "sam"])
    assert [r.person for r in resolved] == ["chris", "sam"]
    assert missing == ["ghost"]


def test_build_notifications_end_to_end(roster, make_spec):
    spec = parse_spec(make_spec())
    notes, missing = build_notifications(spec, Event.ready_for_review, roster, "widget")
    assert missing == []
    assert {n.recipient for n in notes} == {"elena", "sam", "qa-team"}
    elena = next(n for n in notes if n.recipient == "elena")
    assert elena.channel == "slack"
    assert elena.subject == "[widget] Spec ready for review"


def test_build_notifications_reports_missing(roster, make_spec):
    spec = parse_spec(make_spec(viewers=["nobody"]))
    notes, missing = build_notifications(spec, Event.ready_for_review, roster, "widget")
    assert "nobody" in missing
    assert all(n.recipient != "nobody" for n in notes)


def test_build_notifications_includes_prototype_link(roster, make_spec):
    spec = parse_spec(make_spec(prototype="https://preview/widget"))
    notes, _ = build_notifications(
        spec, Event.ready_for_review, roster, "widget",
        links={"prototype": "https://preview/widget"},
    )
    assert notes[0].links["prototype"] == "https://preview/widget"
    assert "https://preview/widget" in notes[0].body
