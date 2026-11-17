from __future__ import annotations

import json

import pytest

from nudgewright import BY_KEY, CATALOGUE, GROUPS, KINDS, MODES, catalogue, resolve_switches
from nudgewright.signals import STATUSES


def test_catalogue_is_well_formed() -> None:
    keys = [s.key for s in CATALOGUE]
    assert len(keys) == len(set(keys))
    for s in CATALOGUE:
        assert s.status in STATUSES
        assert s.default in MODES
        assert s.level in {"L0", "L1", "L2", "L3", "L4"}
        assert (s.kind in KINDS) == (s.status == "live")
        assert bool(s.needs) == (s.status == "needs_data")
    assert set(GROUPS) == {s.group for s in CATALOGUE}
    assert BY_KEY["weather"].default == "never"


def test_live_signals_cover_every_slot() -> None:
    live = {s.kind for s in CATALOGUE if s.status == "live"}
    assert live == set(KINDS)


def test_resolve_switches_defaults_and_overrides() -> None:
    modes = resolve_switches(None)
    assert set(modes) == set(BY_KEY)
    assert modes["weather"] == "never" and modes["birthday"] == "auto"
    assert resolve_switches({"weather": "always"})["weather"] == "always"


@pytest.mark.parametrize("bad", [{"nope": "auto"}, {"birthday": "sometimes"}])
def test_resolve_switches_rejects_unknown(bad: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="unknown signal or mode"):
        resolve_switches(bad)


def test_catalogue_listing_is_json_and_carries_mode() -> None:
    rows = catalogue({"festival": "never"})
    json.dumps(rows)
    by_key = {r["key"]: r for r in rows}
    assert by_key["festival"]["mode"] == "never"
    assert by_key["festival"]["default"] == "auto"
