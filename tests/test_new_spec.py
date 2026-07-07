import subprocess
import textwrap

import pytest

from hureva.frontmatter import parse_spec
from hureva.new_spec import create_spec, render_spec, main

_DEFAULTS = textwrap.dedent("""
    owner: chris
    approvers: [elena]
    commenters: [sam]
    viewers: [qa-team]
""")


def test_render_spec_seeds_and_parses():
    seeded = {"owner": "chris", "approvers": ["elena"], "commenters": ["sam"], "viewers": []}
    text = render_spec("Widget", seeded)
    spec = parse_spec(text)
    assert spec.title == "Widget"
    assert spec.status.value == "draft"
    assert spec.owner == "chris"
    assert spec.approvers == ["elena"]
    assert spec.approved_by == []


def _init_repo(tmp_path):
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "defaults.yml").write_text(_DEFAULTS, encoding="utf-8")
    for args in (
        ("init",),
        ("config", "user.email", "t@t.com"),
        ("config", "user.name", "t"),
        ("add", "-A"),
        ("commit", "-m", "init"),
    ):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True,
                       capture_output=True, text=True)


def test_create_spec_seeds_from_defaults_and_branches(tmp_path):
    _init_repo(tmp_path)
    path = create_spec("widget", "Widget", specs_dir="specs", repo_dir=str(tmp_path))
    assert path.exists()
    spec = parse_spec(path.read_text())
    # seeded from defaults.yml
    assert spec.owner == "chris"
    assert spec.approvers == ["elena"]
    # branch created
    branch = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert branch == "spec/widget"


def test_create_spec_overrides_win(tmp_path):
    _init_repo(tmp_path)
    path = create_spec(
        "gadget", "Gadget", specs_dir="specs", repo_dir=str(tmp_path),
        overrides={"approvers": ["sam"], "owner": "elena"}, make_branch=False,
    )
    spec = parse_spec(path.read_text())
    assert spec.owner == "elena"
    assert spec.approvers == ["sam"]
    # unset role still inherits from defaults
    assert spec.commenters == ["sam"]


def test_create_spec_refuses_existing(tmp_path):
    _init_repo(tmp_path)
    create_spec("widget", "Widget", specs_dir="specs", repo_dir=str(tmp_path), make_branch=False)
    with pytest.raises(FileExistsError):
        create_spec("widget", "Widget", specs_dir="specs", repo_dir=str(tmp_path), make_branch=False)


def test_new_spec_cli(tmp_path):
    _init_repo(tmp_path)
    rc = main([
        "widget", "--title", "Widget", "--specs-dir", "specs",
        "--repo-dir", str(tmp_path), "--no-branch", "--approvers", "elena,sam",
    ])
    assert rc == 0
    spec = parse_spec((tmp_path / "specs" / "widget" / "spec.md").read_text())
    assert spec.approvers == ["elena", "sam"]
