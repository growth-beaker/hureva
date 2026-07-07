import pytest
from pydantic import ValidationError

from hureva.models import Defaults, Person, Roster, SpecFrontmatter, Status


def test_person_requires_a_channel():
    with pytest.raises(ValidationError):
        Person()
    assert Person(email="a@b.com").email == "a@b.com"
    assert Person(slack="#x").slack == "#x"


def test_person_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        Person(email="a@b.com", phone="555")


def test_spec_parses_and_enum_status(make_spec):
    spec = SpecFrontmatter.model_validate(
        {"title": "t", "status": "approved", "owner": "chris"}
    )
    assert spec.status is Status.approved
    assert spec.approvers == []


def test_approved_by_must_be_subset_of_approvers():
    with pytest.raises(ValidationError):
        SpecFrontmatter(
            title="t", status="approved", owner="c",
            approvers=["a"], approved_by=["a", "b"],
        )
    # subset is fine
    ok = SpecFrontmatter(
        title="t", status="approved", owner="c",
        approvers=["a", "b"], approved_by=["a"],
    )
    assert ok.approved_by == ["a"]


def test_spec_allows_unknown_future_fields():
    spec = SpecFrontmatter(
        title="t", status="draft", owner="c", prototype="https://x/y"
    )
    # extra="allow" keeps it round-trippable without breaking older readers
    assert spec.model_dump().get("prototype") == "https://x/y"


def test_all_reviewers_dedupes_and_orders():
    spec = SpecFrontmatter(
        title="t", status="in_review", owner="c",
        approvers=["a", "b"], commenters=["b", "d"], viewers=["a", "e"],
    )
    assert spec.all_reviewers() == ["a", "b", "d", "e"]


def test_defaults_owner_optional():
    d = Defaults(approvers=["pm"], commenters=["ux"])
    assert d.owner is None
    assert d.approvers == ["pm"]


def test_roster_contains_and_get():
    r = Roster(people={"x": Person(slack="#x")})
    assert "x" in r
    assert r.get("y") is None
