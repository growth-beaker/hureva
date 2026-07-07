import json
import subprocess
import textwrap

import pytest

from hureva import ci
from hureva.cli import main as cli_main

_ROSTER = textwrap.dedent("""
    people:
      chris: { email: chris@acme.com, slack: "@chris" }
      elena: { email: elena@acme.com, slack: "@elena" }
      sam:   { email: sam@acme.com }
      qa-team: { slack: "#qa" }
""")


def _spec(status, approved_by="[]"):
    return textwrap.dedent(f"""\
        ---
        title: Widget
        status: {status}
        owner: chris
        approvers: [elena]
        commenters: [sam]
        viewers: [qa-team]
        approved_by: {approved_by}
        version: "1.0"
        ---
        # Widget
    """)


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _make_repo(tmp_path, before_status, after_status, approved_by="[]"):
    specs = tmp_path / "specs"
    (specs / "widget").mkdir(parents=True)
    (specs / "roster.yml").write_text(_ROSTER, encoding="utf-8")
    (specs / "widget" / "spec.md").write_text(_spec(before_status), encoding="utf-8")
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t.com")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "before")
    before = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    (specs / "widget" / "spec.md").write_text(_spec(after_status, approved_by), encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "after")
    after = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
                           capture_output=True, text=True, check=True).stdout.strip()
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"before": before, "after": after}), encoding="utf-8")
    return event


def _args(event, *extra):
    # Run as the workflow does: from the repo root, with relative paths so the
    # git-relative changed paths match --specs-dir.
    return [
        "--specs-dir", "specs",
        "--repo-dir", ".",
        "--event-file", str(event),
        "--dry-run",
        *extra,
    ]


def test_ci_notifies_and_gates_advisory(tmp_path, monkeypatch, capsys):
    event = _make_repo(tmp_path, "draft", "in_review")
    monkeypatch.chdir(tmp_path)
    rc = ci.main(_args(event))
    out = capsys.readouterr().out
    assert rc == 0                       # advisory
    assert "ready_for_review" in out     # notified on the transition
    assert "advisory" in out             # gate reported, not blocking


def test_ci_enforced_blocks_unapproved(tmp_path, monkeypatch):
    event = _make_repo(tmp_path, "draft", "in_review")
    monkeypatch.chdir(tmp_path)
    rc = ci.main(_args(event, "--enforced"))
    assert rc == 1                       # not approved -> blocked


def test_ci_enforced_passes_when_approved(tmp_path, monkeypatch):
    event = _make_repo(tmp_path, "in_review", "approved", approved_by="[elena]")
    monkeypatch.chdir(tmp_path)
    rc = ci.main(_args(event, "--enforced"))
    assert rc == 0


def test_ci_no_changes_exit_zero(tmp_path, monkeypatch, capsys):
    # a push that changes nothing under specs/
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "roster.yml").write_text(_ROSTER, encoding="utf-8")
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("hi\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "init")
    head = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"before": head, "after": head}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = ci.main(_args(event))
    assert rc == 0
    assert "nothing to do" in capsys.readouterr().out


def test_cli_dispatch_unknown_command():
    assert cli_main(["bogus"]) == 2


def test_cli_dispatch_help():
    assert cli_main([]) == 0


def test_cli_dispatch_routes_to_ci(tmp_path, monkeypatch):
    event = _make_repo(tmp_path, "in_review", "approved", approved_by="[elena]")
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["ci", *_args(event), "--enforced"])
    assert rc == 0
