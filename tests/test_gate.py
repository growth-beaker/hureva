import json
import subprocess

import pytest

from hureva.events import Event
from hureva.frontmatter import parse_spec
from hureva.gate import evaluate_gate, main
from hureva.models import Status


def test_gate_not_approved(make_spec):
    spec = parse_spec(make_spec(status="in_review"))
    result = evaluate_gate(spec, "widget")
    assert result.cleared is False
    assert result.event is None


def test_gate_approved_clears_and_emits(make_spec):
    spec = parse_spec(make_spec(status="approved", approvers=["elena"], approved_by=["elena"]))
    result = evaluate_gate(spec, "widget")
    assert result.cleared is True
    assert result.event is Event.cleared_to_build


def test_gate_require_all_approvers_blocks_partial(make_spec):
    spec = parse_spec(make_spec(
        status="approved", approvers=["elena", "sam"], approved_by=["elena"]
    ))
    result = evaluate_gate(spec, "widget", require_all_approvers=True)
    assert result.cleared is False
    assert "sam" in result.reason


def test_gate_require_all_approvers_passes_full(make_spec):
    spec = parse_spec(make_spec(
        status="approved", approvers=["elena", "sam"], approved_by=["elena", "sam"]
    ))
    result = evaluate_gate(spec, "widget", require_all_approvers=True)
    assert result.cleared is True


def _write_spec(tmp_path, text, slug="widget"):
    d = tmp_path / "specs" / slug
    d.mkdir(parents=True)
    (d / "spec.md").write_text(text, encoding="utf-8")


def test_gate_cli_advisory_exit_zero(tmp_path, make_spec, capsys):
    _write_spec(tmp_path, make_spec(status="in_review"))
    rc = main(["widget", "--specs-dir", str(tmp_path / "specs")])
    assert rc == 0
    assert "advisory" in capsys.readouterr().out


def test_gate_cli_enforced_blocks(tmp_path, make_spec):
    _write_spec(tmp_path, make_spec(status="in_review"))
    rc = main(["widget", "--specs-dir", str(tmp_path / "specs"), "--enforced"])
    assert rc == 1


def test_gate_cli_approved_exit_zero(tmp_path, make_spec):
    _write_spec(tmp_path, make_spec(status="approved", approvers=["elena"], approved_by=["elena"]))
    rc = main(["widget", "--specs-dir", str(tmp_path / "specs"), "--enforced"])
    assert rc == 0


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


def test_gate_cli_changed_mode_gates_pushed_spec(tmp_path, make_spec):
    repo = tmp_path
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.com")
    _git(repo, "config", "user.name", "t")
    _write_spec(repo, make_spec(status="draft"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "draft")
    before = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()

    (repo / "specs" / "widget" / "spec.md").write_text(
        make_spec(status="approved", approvers=["elena"], approved_by=["elena"]),
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "approve")
    after = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                           capture_output=True, text=True, check=True).stdout.strip()

    event = repo / "event.json"
    event.write_text(json.dumps({"before": before, "after": after}), encoding="utf-8")

    rc = main([
        "--changed", "--enforced",
        "--specs-dir", str(repo / "specs"),
        "--repo-dir", str(repo),
        "--event-file", str(event),
    ])
    assert rc == 0  # the changed spec is approved


def test_gate_cli_changed_mode_no_specs_exit_zero(tmp_path, capsys):
    repo = tmp_path
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.com")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("hi\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    event = repo / "event.json"
    event.write_text(json.dumps({"before": head, "after": head}), encoding="utf-8")
    rc = main([
        "--changed", "--specs-dir", str(repo / "specs"),
        "--repo-dir", str(repo), "--event-file", str(event),
    ])
    assert rc == 0
    assert "nothing to gate" in capsys.readouterr().out
