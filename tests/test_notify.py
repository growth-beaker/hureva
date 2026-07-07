import pytest

from hureva.events import Event
from hureva.notify import SpecChange, process_change, process_push, dispatch
from hureva.senders import DryRunSender, MultiSender


def _change(slug, before, after):
    return SpecChange(slug=slug, path=f"specs/{slug}/spec.md",
                      before_text=before, after_text=after)


def test_process_change_fires_on_transition(roster, make_spec):
    change = _change("widget", make_spec(status="draft"), make_spec(status="in_review"))
    result = process_change(change, roster)
    assert result.event is Event.ready_for_review
    assert {n.recipient for n in result.notifications} == {"elena", "sam", "qa-team"}


def test_process_change_dedups_body_only_edit(roster, make_spec):
    before = make_spec(status="in_review", title="A")
    after = make_spec(status="in_review", title="B")  # status unchanged
    result = process_change(_change("widget", before, after), roster)
    assert result.event is None
    assert result.notifications == []


def test_process_change_new_file_in_review(roster, make_spec):
    result = process_change(_change("widget", None, make_spec(status="in_review")), roster)
    assert result.event is Event.ready_for_review


def test_process_change_approved_notifies_owner(roster, make_spec):
    before = make_spec(status="in_review", approvers=["elena"])
    after = make_spec(status="approved", approvers=["elena"], approved_by=["elena"])
    result = process_change(_change("widget", before, after), roster)
    assert result.event is Event.approved
    assert [n.recipient for n in result.notifications] == ["chris"]


def test_process_change_reports_missing_roster_name(roster, make_spec):
    before = make_spec(status="draft", viewers=["ghost"])
    after = make_spec(status="in_review", viewers=["ghost"])
    result = process_change(_change("widget", before, after), roster)
    assert "ghost" in result.missing


def test_dispatch_delivers_via_dry_run(roster, make_spec):
    change = _change("widget", make_spec(status="draft"), make_spec(status="in_review"))
    results = process_push([change], roster)
    dry = DryRunSender()
    dispatch(results, MultiSender({"slack": dry, "email": dry}, fallback=dry))
    assert len(dry.sent) == 3
