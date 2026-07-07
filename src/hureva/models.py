"""Pydantic models for the spec-review data model (§4).

These are the runtime contract. The spec's frontmatter (§4.2), the central
roster (§4.3), and the default review assignment (§4.4) are each a model here.
Everything the Actions do is expressed in terms of these types.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Status(str, Enum):
    """Spec lifecycle states (§5). String-valued so YAML round-trips cleanly."""

    draft = "draft"
    in_review = "in_review"
    approved = "approved"
    implemented = "implemented"
    archived = "archived"


# The role fields on a spec, in permission order. Used by routing and by the
# defaults-seeding logic so both stay in lockstep with the schema.
ROLE_FIELDS: tuple[str, ...] = ("approvers", "commenters", "viewers")


class Person(BaseModel):
    """A roster entry (§4.3). At least one channel is required.

    People are referenced everywhere by their roster *key*, never inline — this
    model is only the contact handles that key resolves to.
    """

    model_config = ConfigDict(extra="forbid")

    email: str | None = None
    slack: str | None = None

    @model_validator(mode="after")
    def _at_least_one_channel(self) -> Person:
        if not self.email and not self.slack:
            raise ValueError("person must have at least one of: email, slack")
        return self


class Roster(BaseModel):
    """Central team roster (§4.3): the only place channels are defined."""

    model_config = ConfigDict(extra="forbid")

    people: dict[str, Person] = Field(default_factory=dict)

    def get(self, key: str) -> Person | None:
        return self.people.get(key)

    def __contains__(self, key: str) -> bool:
        return key in self.people


class Defaults(BaseModel):
    """Default review assignment (§4.4), seeded into new specs at creation.

    A seed, not a runtime fallback: after a spec is created its own frontmatter
    is the only thing consulted (§2 principle 2). ``owner`` is optional here
    because a spec may set its own.
    """

    model_config = ConfigDict(extra="forbid")

    owner: str | None = None
    approvers: list[str] = Field(default_factory=list)
    commenters: list[str] = Field(default_factory=list)
    viewers: list[str] = Field(default_factory=list)


class SpecFrontmatter(BaseModel):
    """The complete spec frontmatter contract (§4.2).

    Status, role-based access, and the sign-off trail. All people are roster
    keys (name-only). Validation is deliberately lenient about *unknown* future
    fields (``extra="allow"``) so a newer schema doesn't break an older reader,
    but strict about the fields it does own.
    """

    # coerce_numbers_to_str: authors commonly write `version: 1.0`, which YAML
    # loads as a float; the schema wants a semver-ish string, so coerce it.
    model_config = ConfigDict(
        extra="allow", use_enum_values=False, coerce_numbers_to_str=True
    )

    title: str
    status: Status
    owner: str
    approvers: list[str] = Field(default_factory=list)
    commenters: list[str] = Field(default_factory=list)
    viewers: list[str] = Field(default_factory=list)
    approved_by: list[str] = Field(default_factory=list)
    approved_at: date | None = None
    version: str = "1.0"

    @model_validator(mode="after")
    def _approved_by_subset_of_approvers(self) -> SpecFrontmatter:
        # §6.2: approved_by should be a subset of approvers. We enforce this as a
        # data-integrity invariant; enforced-quorum semantics (approved_by ⊇
        # approvers) are a separate, later gate check (§6.2), not modeled here.
        stray = set(self.approved_by) - set(self.approvers)
        if stray:
            raise ValueError(
                "approved_by contains people not listed as approvers: "
                + ", ".join(sorted(stray))
            )
        return self

    def role_members(self, role: str) -> list[str]:
        """Return the person keys for a role field ('approvers'/'commenters'/…)."""
        return list(getattr(self, role))

    def all_reviewers(self) -> list[str]:
        """approvers + commenters + viewers, de-duplicated, order preserved."""
        seen: dict[str, None] = {}
        for role in ROLE_FIELDS:
            for person in getattr(self, role):
                seen.setdefault(person, None)
        return list(seen)
