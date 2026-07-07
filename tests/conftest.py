import textwrap

import pytest

from hureva.models import Person, Roster


@pytest.fixture
def roster() -> Roster:
    return Roster(
        people={
            "chris": Person(email="chris@acme.com", slack="@chris"),
            "elena": Person(email="elena@acme.com", slack="@elena"),
            "sam": Person(email="sam@acme.com"),  # email only
            "qa-team": Person(slack="#qa"),  # slack only, group
        }
    )


def spec_text(**over) -> str:
    fields = {
        "title": "Widget",
        "status": "in_review",
        "owner": "chris",
        "approvers": ["elena"],
        "commenters": ["sam"],
        "viewers": ["qa-team"],
        "approved_by": [],
        "version": "1.0",
    }
    fields.update(over)
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            rendered = "[" + ", ".join(value) + "]"
        else:
            rendered = value
        lines.append(f"{key}: {rendered}")
    lines.append("---")
    lines.append("")
    lines.append("# Body")
    return "\n".join(lines) + "\n"


@pytest.fixture
def make_spec():
    return spec_text
