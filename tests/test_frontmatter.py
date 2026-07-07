import pytest

from hureva.frontmatter import (
    FrontmatterError,
    parse_spec,
    parse_status,
    split_frontmatter,
)


def test_split_frontmatter_basic():
    text = "---\ntitle: t\nstatus: draft\n---\n# Body\ncontent\n"
    raw, body = split_frontmatter(text)
    assert "title: t" in raw
    assert body.startswith("# Body")


def test_split_handles_leading_bom():
    text = "﻿---\nstatus: draft\n---\nbody\n"
    raw, body = split_frontmatter(text)
    assert "status: draft" in raw


def test_split_no_fence_raises():
    with pytest.raises(FrontmatterError):
        split_frontmatter("no frontmatter here")


def test_split_unclosed_fence_raises():
    with pytest.raises(FrontmatterError):
        split_frontmatter("---\nstatus: draft\nbody\n")


def test_parse_spec_full(make_spec):
    spec = parse_spec(make_spec(status="approved", approvers=["elena"], approved_by=["elena"]))
    assert spec.owner == "chris"
    assert spec.status.value == "approved"


def test_parse_status_lenient():
    assert parse_status("---\nstatus: in_review\n---\nx") == "in_review"
    assert parse_status(None) is None
    assert parse_status("") is None
    # malformed still doesn't raise
    assert parse_status("not a doc") is None
    # frontmatter present but no status
    assert parse_status("---\ntitle: t\n---\n") is None


def test_parse_status_ignores_invalid_schema():
    # A before-version that wouldn't validate as a full spec still yields status.
    text = "---\nstatus: approved\napproved_by: [x]\napprovers: []\n---\n"
    # full parse would fail the subset rule; lenient status read must not
    assert parse_status(text) == "approved"
