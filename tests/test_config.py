import textwrap

import pytest

from hureva.config import Paths, load_defaults, load_roster, seed_frontmatter
from hureva.models import Defaults


def test_paths_derive_from_specs_dir():
    p = Paths("docs/specs")
    assert str(p.roster) == "docs/specs/roster.yml"
    assert str(p.defaults) == "docs/specs/defaults.yml"
    assert str(p.spec("widget")) == "docs/specs/widget/spec.md"
    assert p.slug_for("docs/specs/widget/spec.md") == "widget"


def _write(dirpath, name, content):
    f = dirpath / name
    f.write_text(textwrap.dedent(content), encoding="utf-8")
    return f


def test_load_roster_and_defaults(tmp_path):
    specs = tmp_path / "specs"
    specs.mkdir()
    _write(specs, "roster.yml", """
        people:
          chris: { email: chris@acme.com, slack: "@chris" }
          qa-team: { slack: "#qa" }
    """)
    _write(specs, "defaults.yml", """
        owner: chris
        approvers: [pm, lead-dev]
        commenters: [ux, qa]
        viewers: []
    """)
    roster = load_roster(specs)
    assert roster.get("chris").slack == "@chris"
    defaults = load_defaults(specs)
    assert defaults.owner == "chris"
    assert defaults.approvers == ["pm", "lead-dev"]


def test_seed_frontmatter_inherits_unset_roles():
    defaults = Defaults(owner="chris", approvers=["pm", "lead"], commenters=["ux"], viewers=[])
    seeded = seed_frontmatter(defaults)
    assert seeded == {
        "owner": "chris",
        "approvers": ["pm", "lead"],
        "commenters": ["ux"],
        "viewers": [],
    }


def test_seed_frontmatter_overrides_win():
    defaults = Defaults(owner="chris", approvers=["pm"], commenters=["ux"])
    seeded = seed_frontmatter(defaults, overrides={"approvers": ["elena"], "owner": "sam"})
    assert seeded["approvers"] == ["elena"]
    assert seeded["owner"] == "sam"
    # unset role still inherits
    assert seeded["commenters"] == ["ux"]
