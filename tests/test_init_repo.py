import yaml

from hureva.frontmatter import parse_spec
from hureva.init_repo import main, render_files, scaffold
from hureva.models import Defaults, Roster


def test_render_substitutes_specs_dir():
    files = render_files("docs/specs")
    wf = files[".github/workflows/spec-review.yml"]
    assert 'paths: ["docs/specs/**"]' in wf
    assert "--specs-dir docs/specs" in wf
    assert "docs/specs/roster.yml" in files
    assert "docs/specs/<feature-slug>/spec.md" in files["CLAUDE.md"]


def test_render_workflow_is_valid_yaml_and_two_steps():
    wf = render_files("specs")[".github/workflows/spec-review.yml"]
    doc = yaml.safe_load(wf)
    steps = doc["jobs"]["spec-review"]["steps"]
    runs = [s.get("run", "") for s in steps]
    assert any("hureva-notify" in r for r in runs)
    assert any("hureva-gate --changed" in r for r in runs)
    assert any('pip install "hureva~=1.0"' in r for r in runs)


def test_sample_config_is_valid():
    files = render_files("specs")
    Roster.model_validate(yaml.safe_load(files["specs/roster.yml"]))
    Defaults.model_validate(yaml.safe_load(files["specs/defaults.yml"]))


def test_spec_template_parses():
    tmpl = render_files("specs")["specs/spec.template.md"]
    spec = parse_spec(tmpl.replace("<Feature title>", "My Feature"))
    assert spec.title == "My Feature"
    assert spec.status.value == "draft"


def test_scaffold_writes_then_skips(tmp_path):
    written, skipped = scaffold(tmp_path, "specs", force=False)
    assert ".github/workflows/spec-review.yml" in written
    assert (tmp_path / "specs" / "roster.yml").exists()
    # second run skips everything
    written2, skipped2 = scaffold(tmp_path, "specs", force=False)
    assert written2 == []
    assert ".github/workflows/spec-review.yml" in skipped2
    # force overwrites
    written3, _ = scaffold(tmp_path, "specs", force=True)
    assert written3


def test_main_prints_checklist(tmp_path, capsys):
    rc = main(["--into", str(tmp_path), "--specs-dir", "docs/specs"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "created" in out
    assert "SLACK_BOT_TOKEN" in out          # checklist present
    assert "docs/specs/roster.yml" in out    # checklist uses the chosen path
