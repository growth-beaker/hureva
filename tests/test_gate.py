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
