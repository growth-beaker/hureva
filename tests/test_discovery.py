from hureva.config import Paths
from hureva.discovery import discover_changes


class FakeGit:
    """A GitReader stand-in backed by dicts keyed on (ref, path)."""

    def __init__(self, changed, contents):
        self._changed = changed
        self._contents = contents

    def changed_files(self, before, after):
        return list(self._changed)

    def read_file_at(self, ref, path):
        return self._contents.get((ref, path))


def test_discover_only_specs_under_specs_dir():
    git = FakeGit(
        changed=[
            "specs/widget/spec.md",
            "specs/widget/plan.md",          # not a spec.md
            "specs/roster.yml",              # config, not a spec
            "src/app.py",                    # unrelated
            "docs/specs/gadget/spec.md",     # different specs_dir
        ],
        contents={
            ("b", "specs/widget/spec.md"): "---\nstatus: draft\n---\n",
            ("a", "specs/widget/spec.md"): "---\nstatus: in_review\n---\n",
        },
    )
    changes = discover_changes(Paths("specs"), git, {"before": "b", "after": "a"})
    assert [c.slug for c in changes] == ["widget"]
    assert changes[0].before_text.strip().endswith("---")
    assert "in_review" in changes[0].after_text


def test_discover_honors_custom_specs_dir():
    git = FakeGit(
        changed=["docs/specs/gadget/spec.md", "specs/widget/spec.md"],
        contents={("a", "docs/specs/gadget/spec.md"): "---\nstatus: draft\n---\n"},
    )
    changes = discover_changes(Paths("docs/specs"), git, {"before": "b", "after": "a"})
    assert [c.slug for c in changes] == ["gadget"]


def test_discover_new_file_has_no_before():
    git = FakeGit(
        changed=["specs/widget/spec.md"],
        contents={("a", "specs/widget/spec.md"): "---\nstatus: in_review\n---\n"},
    )
    # before SHA present but file absent there -> read returns None
    changes = discover_changes(Paths("specs"), git, {"before": "b", "after": "a"})
    assert changes[0].before_text is None
