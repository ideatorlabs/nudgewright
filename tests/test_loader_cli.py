from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from nudgewright import (
    Festival,
    Offer,
    context_from_dict,
    customer_from_dict,
    load_facts,
    load_facts_file,
    load_festivals,
)
from nudgewright.cli import main
from nudgewright.loader import offer_from_value, parse_date

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_load_example_facts() -> None:
    ctx, customers = load_facts_file(EXAMPLES / "facts.json")
    assert ctx.goal == "winback" and ctx.today == date(2026, 12, 23)
    assert ctx.the_offer == Offer("15% off", date(2026, 12, 31))
    assert ctx.weather is not None and ctx.weather.rain_chance == 75
    assert [c.id for c in customers] == ["cust-001", "cust-002", "cust-003"]
    assert customers[2].loyalty is not None and customers[2].private == {"phone": "+1 555 0177"}


def test_load_festivals_from_file_and_list() -> None:
    fests = load_festivals(EXAMPLES / "festivals.example.json")
    assert Festival("Christmas", date(2026, 12, 25), "🎄") in fests
    assert load_festivals([{"name": "Fair", "date": "2027-01-02", "regions": ["North"]}])[0].regions == (
        "North",
    )
    assert load_festivals({"festivals": [{"name": "X", "on": "2027-01-01"}]})[0].name == "X"
    with pytest.raises(ValueError, match="list of objects"):
        load_festivals(["Christmas"])  # type: ignore[list-item]


def test_loader_details_and_errors() -> None:
    assert offer_from_value(None) is None and offer_from_value("  ") is None
    assert offer_from_value({"text": ""}) is None
    assert offer_from_value("10% off") == Offer("10% off")
    assert parse_date(date(2026, 1, 1)) == date(2026, 1, 1)
    with pytest.raises(ValueError, match="ISO date"):
        parse_date("23/12/2026", "today")
    with pytest.raises(ValueError, match="bills"):
        customer_from_dict({"id": "c1", "bills": ["Latte"]})
    with pytest.raises(ValueError, match="expected an object"):
        customer_from_dict({"id": "c1", "categories": ["Coffee"]})
    ctx = context_from_dict(
        {
            "goal": "festival",
            "today": "2026-12-01",
            "campaign_festival": {"name": "Fair", "on": "2026-12-20"},
            "weather": {"temp_max": 40},
        }
    )
    assert ctx.campaign_festival is not None and ctx.weather is not None and ctx.weather.rain_chance is None
    _ctx, people = load_facts(
        {"goal": "vip", "today": "2026-12-01", "customers": [{"id": "a", "birthday_in_days": 2}]}
    )
    assert people[0].birthday_in_days == 2


def test_cli_compose_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["compose", str(EXAMPLES / "facts.json")]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [d["customer_id"] for d in data] == ["cust-001", "cust-002", "cust-003"]
    assert data[1]["line"].startswith("Tasting night is tomorrow!")
    assert all("+1 555" not in d["line"] for d in data)


def test_cli_compose_text_with_festivals(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    facts = json.loads((EXAMPLES / "facts.json").read_text(encoding="utf-8"))
    facts["switches"] = {}
    facts["events"] = []
    facts["festivals"] = []
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(facts), encoding="utf-8")
    assert (
        main(["compose", str(path), "--festivals", str(EXAMPLES / "festivals.example.json"), "--text"]) == 0
    )
    out = capsys.readouterr().out
    assert "cust-001: Happy Christmas!" in out and "Used:" in out


def test_cli_signals(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["signals", "--live"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows and all(r["status"] == "live" for r in rows)


def test_cli_errors(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert main(["compose", str(tmp_path / "missing.json")]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    assert main(["compose", str(bad)]) == 2
    assert "nudgewright:" in capsys.readouterr().err


def test_cli_unsupported_goal_text(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    path = tmp_path / "facts.json"
    path.write_text(
        json.dumps({"goal": "review", "today": "2026-12-01", "customers": [{"id": "a"}]}), "utf-8"
    )
    assert main(["compose", str(path), "--text"]) == 0
    assert "a: (no line)" in capsys.readouterr().out
