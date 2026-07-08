import yaml

from hureva.frontmatter import parse_spec
from hureva.init_repo import (
    collect_team,
    main,
    render_defaults,
    render_files,
    render_roster,
    scaffold,
)
from hureva.models import Defaults, Roster


def test_render_substitutes_specs_dir():
    files = render_files("docs/specs")
    wf = files[".github/workflows/spec-review.yml"]
    assert 'paths: ["docs/specs/**"]' in wf
    assert "--specs-dir docs/specs" in wf
    assert "docs/specs/roster.yml" in files
    assert "docs/specs/<feature-slug>/spec.md" in files["CLAUDE.md"]


def test_render_workflow_valid_and_has_github_wiring():
    wf = render_files("specs")[".github/workflows/spec-review.yml"]
    doc = yaml.safe_load(wf)
    assert doc["permissions"]["pull-requests"] == "write"
    steps = doc["jobs"]["spec-review"]["steps"]
    runs = [s.get("run", "") for s in steps]
    assert any("hureva-notify" in r for r in runs)
    assert any("hureva-gate --changed" in r for r in runs)
    assert "GITHUB_TOKEN" in steps[3]["env"]


def test_sample_config_is_valid():
    files = render_files("specs")
    Roster.model_validate(yaml.safe_load(files["specs/roster.yml"]))
    Defaults.model_validate(yaml.safe_load(files["specs/defaults.yml"]))


def test_spec_template_parses():
    tmpl = render_files("specs")["specs/spec.template.md"]
    spec = parse_spec(tmpl.replace("<Feature title>", "My Feature"))
    assert spec.title == "My Feature"


def test_scaffold_writes_then_skips(tmp_path):
    written, skipped = scaffold(tmp_path, "specs", force=False)
    assert ".github/workflows/spec-review.yml" in written
    assert (tmp_path / "specs" / "roster.yml").exists()
    written2, skipped2 = scaffold(tmp_path, "specs", force=False)
    assert written2 == []
    assert ".github/workflows/spec-review.yml" in skipped2
    assert scaffold(tmp_path, "specs", force=True)[0]


def test_main_noninteractive_writes_sample_and_next_steps(tmp_path, capsys):
    # pytest stdin is not a tty -> non-interactive sample path
    rc = main(["--into", str(tmp_path), "--specs-dir", "docs/specs"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "created" in out
    assert "Next steps" in out
    assert "docs/specs/roster.yml" in out
    # roster written as the sample, and valid
    Roster.model_validate(
        yaml.safe_load((tmp_path / "docs/specs/roster.yml").read_text())
    )


# --- interactive builders -------------------------------------------------------

def test_render_roster_and_defaults_are_valid():
    people = [{"key": "chris", "github": "chris"}, {"key": "pat", "github": "pat-ux"}]
    roster = render_roster(people)
    Roster.model_validate(yaml.safe_load(roster))
    assert "chris: { github: chris }" in roster

    defaults = render_defaults("chris", {"approvers": ["pat"], "commenters": [], "viewers": []})
    d = Defaults.model_validate(yaml.safe_load(defaults))
    assert d.owner == "chris"
    assert d.approvers == ["pat"]


def test_collect_team_builds_roster_from_prompts(monkeypatch):
    # you: chris/chris; add teammate elena (approver); then decline
    answers = iter(["chris", "chris", "y", "elena", "elena-pm", "1", "n"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(answers))

    people, owner, roles = collect_team(default_login=None)

    assert owner == "chris"
    assert people == [
        {"key": "chris", "github": "chris"},
        {"key": "elena", "github": "elena-pm"},
    ]
    assert roles["approvers"] == ["elena"]
    # and the rendered files validate
    Roster.model_validate(yaml.safe_load(render_roster(people)))
    Defaults.model_validate(yaml.safe_load(render_defaults(owner, roles)))


def test_collect_team_solo(monkeypatch):
    # you only, decline teammate
    answers = iter(["sam", "sam-gh", "n"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(answers))
    people, owner, roles = collect_team(default_login="sam-gh")
    assert people == [{"key": "sam", "github": "sam-gh"}]
    assert owner == "sam"
    assert roles == {"approvers": [], "commenters": [], "viewers": []}
