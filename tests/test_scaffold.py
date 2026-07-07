import pytest
import yaml

from hureva.frontmatter import parse_spec
from hureva.models import Defaults, Roster
from hureva.scaffold import render_files, scaffold


def test_render_files_writes_specs_dir_into_all_consumers():
    files = render_files(specs_dir="docs/specs")
    # 1. caller `with:` inputs
    caller = files[".github/workflows/spec-review.yml"]
    assert "specs_dir: docs/specs" in caller
    # 2. literal on.push.paths filter (no variable allowed there)
    assert 'paths: ["docs/specs/**"]' in caller
    # 3. CLAUDE.md / new-spec guidance
    assert "docs/specs/<feature-slug>/spec.md" in files["CLAUDE.md"]
    assert "docs/specs" in files[".claude/commands/new-spec.md"]
    # config files land under the chosen specs_dir
    assert "docs/specs/roster.yml" in files
    assert "docs/specs/defaults.yml" in files


def test_caller_references_central_repo_at_ref():
    files = render_files(org="growth-beaker", repo="hureva", lib_ref="v2")
    caller = files[".github/workflows/spec-review.yml"]
    assert "growth-beaker/hureva/.github/workflows/status-gate.yml@v2" in caller
    assert "growth-beaker/hureva/.github/workflows/notify.yml@v2" in caller


def test_sample_config_is_valid():
    files = render_files()
    Roster.model_validate(yaml.safe_load(files["specs/roster.yml"]))
    Defaults.model_validate(yaml.safe_load(files["specs/defaults.yml"]))


def test_spec_template_parses_after_filling_title():
    files = render_files()
    template = files["specs/spec.template.md"]
    filled = template.replace("<Feature title>", "My Feature")
    spec = parse_spec(filled)
    assert spec.title == "My Feature"
    assert spec.status.value == "draft"


def test_scaffold_writes_and_refuses_overwrite(tmp_path):
    written = scaffold(tmp_path, specs_dir="specs")
    assert ".github/workflows/spec-review.yml" in written
    assert (tmp_path / "specs" / "roster.yml").exists()
    # second run without force clashes
    with pytest.raises(FileExistsError):
        scaffold(tmp_path, specs_dir="specs")
    # force overwrites
    scaffold(tmp_path, specs_dir="specs", force=True)


def test_scaffold_custom_specs_dir_paths(tmp_path):
    scaffold(tmp_path, specs_dir="docs/specs")
    assert (tmp_path / "docs" / "specs" / "defaults.yml").exists()
    caller = (tmp_path / ".github/workflows/spec-review.yml").read_text()
    assert 'paths: ["docs/specs/**"]' in caller
