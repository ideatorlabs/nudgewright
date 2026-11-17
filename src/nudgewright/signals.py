"""The signal catalogue and per-business switches.

A *signal* is one fact the composer may know about a customer, the business or the world: a birthday
this week, a usual order, rain tomorrow. Every signal has a switch a business can set:

``auto``
    The composer decides each time whether the signal is present, relevant and confident enough.
``always``
    Used whenever it is present, even when ``auto`` would hold it back. Guardrails still apply.
``never``
    Never used. It is still reported as skipped so the explanation stays complete.

``status`` tells you what this version of the library does with a signal:

``live``
    The composer reads it from the input and can put it into words.
``planned``
    In the catalogue so switches can be stored now; the composer ignores it for the moment.
``needs_data``
    Needs an input the :class:`~nudgewright.facts.Context` does not model yet.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

MODES: tuple[str, ...] = ("auto", "always", "never")
KINDS: tuple[str, ...] = ("now", "person", "offer")
STATUSES: tuple[str, ...] = ("live", "planned", "needs_data")
LEVELS: dict[str, str] = {
    "L0": "Contact: name, consent, the business's own offers and events",
    "L1": "Visits: bills with a date",
    "L2": "Items: bills with line items and categories",
    "L3": "Catalogue: menu, stock and capacity",
    "L4": "World: weather, local events, school calendars",
}


@dataclass(frozen=True)
class Signal:
    """One entry in the catalogue."""

    key: str
    label: str
    group: str
    description: str
    level: str
    status: str
    kind: str = ""  # now | person | offer, for live signals
    default: str = "auto"
    needs: str = ""  # what input is missing, for status "needs_data"

    def as_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "label": self.label,
            "group": self.group,
            "description": self.description,
            "level": self.level,
            "status": self.status,
            "kind": self.kind,
            "default": self.default,
            "needs": self.needs,
        }


_VISITS = "Visits and spending"
_CALENDAR = "Calendar"
_PLACE = "Place and weather"
_CUSTOMER = "The customer"
_BUSINESS = "The business"

CATALOGUE: tuple[Signal, ...] = (
    # visits and spending
    Signal(
        "stage",
        "Customer stage",
        _VISITS,
        "First-timer or regular, from the visit count.",
        "L1",
        "live",
        "person",
    ),
    Signal(
        "visit_rhythm",
        "Visit rhythm",
        _VISITS,
        "A regular who is past their usual gap. The gap itself is never put into words.",
        "L1",
        "live",
        "person",
    ),
    Signal(
        "days_since", "Days since last visit", _VISITS, "Can decide timing; never stated.", "L1", "planned"
    ),
    Signal(
        "spend_band", "Spend band", _VISITS, "Top, typical or light spender; never stated.", "L1", "planned"
    ),
    Signal(
        "usual_order",
        "Usual order",
        _VISITS,
        "The same item on at least two of the last three bills.",
        "L2",
        "live",
        "offer",
    ),
    Signal(
        "favourite_category",
        "Favourite category",
        _VISITS,
        "Three or more items bought in one category.",
        "L2",
        "live",
        "offer",
    ),
    Signal("refill_due", "Refill due", _VISITS, "An item with a known replacement cycle.", "L2", "planned"),
    Signal(
        "basket_gap", "Not tried yet", _VISITS, "Always buys one thing, never the other.", "L2", "planned"
    ),
    # calendar
    Signal(
        "festival",
        "Festivals",
        _CALENDAR,
        "A festival from your calendar, within its window.",
        "L0",
        "live",
        "now",
    ),
    Signal(
        "birthday", "Birthday", _CALENDAR, "A birthday on file within the next week.", "L0", "live", "now"
    ),
    Signal(
        "first_visit_anniversary",
        "First-visit anniversary",
        _CALENDAR,
        "A year (or more) since their first visit, this week.",
        "L1",
        "live",
        "now",
    ),
    Signal(
        "own_events",
        "Your events",
        _CALENDAR,
        "An event you added, in the next few days.",
        "L0",
        "live",
        "now",
    ),
    Signal("payday", "Payday and month start", _CALENDAR, "Calendar timing only.", "L0", "planned"),
    Signal(
        "weekday_habit",
        "Day-of-week habit",
        _CALENDAR,
        "For example, usually comes on Fridays.",
        "L1",
        "planned",
    ),
    Signal(
        "school_holidays",
        "School holidays",
        _CALENDAR,
        "Your region's school calendar.",
        "L4",
        "needs_data",
        needs="A school calendar for the region",
    ),
    # place and weather
    Signal(
        "weather",
        "Weather tomorrow",
        _PLACE,
        "Likely rain or heat tomorrow, from a forecast you pass in.",
        "L4",
        "live",
        "now",
        default="never",
    ),
    Signal(
        "local_events",
        "Local events",
        _PLACE,
        "A match, concert or race nearby.",
        "L4",
        "needs_data",
        needs="A local events feed",
    ),
    Signal(
        "store_hours", "Opening hours", _PLACE, "Never invite people when you are closed.", "L0", "planned"
    ),
    # the customer
    Signal("language", "Language", _CUSTOMER, "Write in the customer's language.", "L0", "planned"),
    Signal(
        "loyalty",
        "Loyalty standing",
        _CUSTOMER,
        "Close to the next tier. Point counts are never stated.",
        "L1",
        "live",
        "person",
    ),
    # the business
    Signal(
        "offers", "Your offer", _BUSINESS, "Only an offer you set, while it is valid.", "L0", "live", "offer"
    ),
    Signal(
        "new_arrivals",
        "New arrivals",
        _BUSINESS,
        "Items added in the last two weeks.",
        "L3",
        "needs_data",
        needs="A catalogue with dates",
    ),
    Signal(
        "stock", "Stock", _BUSINESS, "Low stock or slow movers.", "L3", "needs_data", needs="Stock levels"
    ),
    Signal(
        "capacity",
        "Quiet hours and free slots",
        _BUSINESS,
        "Bookings or table data.",
        "L3",
        "needs_data",
        needs="Bookings or capacity data",
    ),
)

BY_KEY: dict[str, Signal] = {s.key: s for s in CATALOGUE}
GROUPS: tuple[str, ...] = tuple(dict.fromkeys(s.group for s in CATALOGUE))


def resolve_switches(overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return ``{signal key: mode}`` for every signal: the business's choice, else the default.

    Raises :class:`ValueError` for an unknown signal key or mode, so typos never pass silently.
    """
    overrides = dict(overrides or {})
    bad = sorted(k for k, v in overrides.items() if k not in BY_KEY or v not in MODES)
    if bad:
        raise ValueError(f"unknown signal or mode for: {', '.join(bad)} (modes are {', '.join(MODES)})")
    return {s.key: overrides.get(s.key, s.default) for s in CATALOGUE}


def catalogue(overrides: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    """The catalogue as plain dicts, each with the ``mode`` in effect for this business."""
    modes = resolve_switches(overrides)
    return [{**s.as_dict(), "mode": modes[s.key]} for s in CATALOGUE]
