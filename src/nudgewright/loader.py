"""Build input models from plain dicts or JSON files (what the CLI reads).

Facts file shape::

    {
      "business":  {"name": "Demo Café", "sector": "cafe", "region": "", "city": ""},
      "goal":      "winback",
      "today":     "2026-12-23",
      "offer":     {"text": "15% off", "ends_on": "2026-12-31"}   # or a plain string, or omitted
      "festivals": [{"name": "Christmas", "on": "2026-12-25", "emoji": "", "regions": []}],
      "campaign_festival": {...},                               # optional, same shape
      "events":    [{"name": "Tasting night", "on": "2026-12-24"}],
      "weather":   {"rain_chance": 70, "temp_max": 24},
      "switches":  {"weather": "auto"},
      "customers": [{"id": "c1", "first_name": "Asha", "visits": 5, "rhythm": "overdue",
                     "bills": [["Latte", "Bagel"], ["Latte"]], "categories": {"Coffee": 4}}]
    }
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from .facts import Business, Context, Customer, Event, Festival, Loyalty, Offer, Weather


def parse_date(value: Any, field: str = "date") -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError as exc:
        raise ValueError(f"{field}: expected an ISO date (YYYY-MM-DD), got {value!r}") from exc


def _opt_date(value: Any, field: str) -> date | None:
    return None if value in (None, "") else parse_date(value, field)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field}: expected an object")
    return value


def festival_from_dict(data: Mapping[str, Any]) -> Festival:
    return Festival(
        name=str(data.get("name") or "").strip(),
        on=parse_date(data.get("on") or data.get("date"), "festival date"),
        emoji=str(data.get("emoji") or ""),
        regions=tuple(str(r) for r in data.get("regions") or ()),
    )


def load_festivals(source: str | Path | Sequence[Mapping[str, Any]] | Mapping[str, Any]) -> list[Festival]:
    """A festival calendar from a JSON file path, a list of dicts, or ``{"festivals": [...]}``."""
    data: Any = (
        json.loads(Path(source).read_text(encoding="utf-8")) if isinstance(source, (str, Path)) else source
    )
    if isinstance(data, Mapping):
        data = data.get("festivals") or []
    if not isinstance(data, Sequence) or not all(isinstance(f, Mapping) for f in data):
        raise ValueError("festivals: expected a list of objects")
    return [festival_from_dict(f) for f in data]


def offer_from_value(value: Any) -> Offer | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        return Offer(value) if value.strip() else None
    data = _mapping(value, "offer")
    text = str(data.get("text") or "").strip()
    return Offer(text, _opt_date(data.get("ends_on"), "offer.ends_on")) if text else None


def customer_from_dict(data: Mapping[str, Any]) -> Customer:
    loyalty = _mapping(data.get("loyalty"), "loyalty")
    bills = data.get("bills") or []
    if not isinstance(bills, list) or not all(isinstance(b, list) for b in bills):
        raise ValueError("bills: expected a list of lists of item names")
    return Customer(
        id=str(data.get("id") or ""),
        first_name=str(data.get("first_name") or ""),
        visits=int(data.get("visits") or 0),
        rhythm=data.get("rhythm") or None,
        first_visit=_opt_date(data.get("first_visit"), "first_visit"),
        bills=tuple(tuple(str(n) for n in bill) for bill in bills),
        categories={str(k): int(v) for k, v in _mapping(data.get("categories"), "categories").items()},
        birthday_in_days=None if data.get("birthday_in_days") is None else int(data["birthday_in_days"]),
        loyalty=Loyalty(
            next_tier=str(loyalty.get("next_tier") or ""),
            points_to_next=int(loyalty.get("points_to_next") or 0),
            tier_points=int(loyalty.get("tier_points") or 0),
        )
        if loyalty
        else None,
        private={str(k): str(v) for k, v in _mapping(data.get("private"), "private").items()},
    )


def context_from_dict(data: Mapping[str, Any]) -> Context:
    biz = _mapping(data.get("business"), "business")
    weather = _mapping(data.get("weather"), "weather")
    campaign = data.get("campaign_festival")
    return Context(
        business=Business(
            name=str(biz.get("name") or ""),
            sector=str(biz.get("sector") or ""),
            region=str(biz.get("region") or ""),
            city=str(biz.get("city") or ""),
        ),
        goal=str(data.get("goal") or ""),
        today=parse_date(data.get("today"), "today"),
        offer=offer_from_value(data.get("offer")),
        festivals=load_festivals(data.get("festivals") or []),
        campaign_festival=festival_from_dict(campaign) if campaign else None,
        events=[
            Event(str(e.get("name") or ""), parse_date(e.get("on"), "event date"))
            for e in data.get("events") or []
        ],
        weather=Weather(
            rain_chance=None if weather.get("rain_chance") is None else int(weather["rain_chance"]),
            temp_max=None if weather.get("temp_max") is None else float(weather["temp_max"]),
            label=str(weather.get("label") or ""),
        )
        if weather
        else None,
        switches={str(k): str(v) for k, v in _mapping(data.get("switches"), "switches").items()},
    )


def load_facts(data: Mapping[str, Any]) -> tuple[Context, list[Customer]]:
    """``(context, customers)`` from one facts dict."""
    return context_from_dict(data), [customer_from_dict(c) for c in data.get("customers") or []]


def load_facts_file(path: str | Path) -> tuple[Context, list[Customer]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("facts file must contain a JSON object")
    return load_facts(data)
