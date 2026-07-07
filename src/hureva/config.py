"""Load per-tenant config and derive paths from ``specs_dir`` (§4.1, §13.5).

Every path derives from a single ``specs_dir`` argument — nothing hard-codes
``specs`` (decision 16). This keeps the path as per-tenant *data*, which is the
seam that lets a future hosted control plane honor a different path per tenant
with no code change (§13.5).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import Defaults, Roster, ROLE_FIELDS


class Paths:
    """Derives every spec-review path from ``specs_dir``."""

    def __init__(self, specs_dir: str | Path):
        self.specs_dir = Path(specs_dir)

    @property
    def roster(self) -> Path:
        return self.specs_dir / "roster.yml"

    @property
    def defaults(self) -> Path:
        return self.specs_dir / "defaults.yml"

    def feature_dir(self, slug: str) -> Path:
        return self.specs_dir / slug

    def spec(self, slug: str) -> Path:
        return self.feature_dir(slug) / "spec.md"

    def slug_for(self, spec_path: str | Path) -> str:
        """Recover the feature slug from a ``<specs_dir>/<slug>/spec.md`` path."""
        return Path(spec_path).parent.name


def _load_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return data or {}


def load_roster(specs_dir: str | Path) -> Roster:
    """Load and validate ``<specs_dir>/roster.yml`` into a :class:`Roster`."""
    return Roster.model_validate(_load_yaml(Paths(specs_dir).roster))


def load_defaults(specs_dir: str | Path) -> Defaults:
    """Load and validate ``<specs_dir>/defaults.yml`` into :class:`Defaults`."""
    return Defaults.model_validate(_load_yaml(Paths(specs_dir).defaults))


def seed_frontmatter(defaults: Defaults, overrides: dict | None = None) -> dict:
    """Seed a new spec's role fields from ``defaults`` (§4.4).

    Precedence: any role explicitly set in ``overrides`` wins; unset roles
    inherit from ``defaults``. Returns a plain dict of frontmatter fields to be
    written at creation. This is a *seed* — it is never consulted again at
    runtime (§2 principle 2, decision 9).
    """
    overrides = overrides or {}
    seeded: dict = {}

    if "owner" in overrides:
        seeded["owner"] = overrides["owner"]
    elif defaults.owner is not None:
        seeded["owner"] = defaults.owner

    for role in ROLE_FIELDS:
        if role in overrides:
            seeded[role] = list(overrides[role])
        else:
            seeded[role] = list(getattr(defaults, role))

    return seeded
