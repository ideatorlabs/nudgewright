"""Plain input models: what the business really knows.

Everything is optional except identifiers and dates. A missing fact is simply absent: the composer
never fills a gap with a guess, it writes a shorter, more general line instead.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

RHYTHMS: tuple[str, ...] = ("on_track", "due", "overdue", "lapsed")
"""How a customer's visits compare with their own usual gap. Computed by the caller."""


@dataclass(frozen=True)
class Business:
    """The business sending the message."""

    name: str = ""
    sector: str = ""  # e.g. "cafe", "salon", "clinic"; drives the sensitive-sector guardrail
    region: str = ""  # matched against Festival.regions
    city: str = ""  # only used if you fetch weather yourself


@dataclass(frozen=True)
class Offer:
    """An offer the owner set for this send. The composer never mentions any other offer."""

    text: str
    ends_on: date | None = None  # last day it can be used; after this day it is ignored


@dataclass(frozen=True)
class Festival:
    """One entry of a festival calendar the caller supplies."""

    name: str
    on: date
    emoji: str = ""
    regions: tuple[str, ...] = ()  # empty means everywhere

    def applies_to(self, region: str) -> bool:
        if not self.regions:
            return True
        return region.strip().casefold() in {r.strip().casefold() for r in self.regions}


@dataclass(frozen=True)
class Event:
    """An event the owner added (a tasting night, a launch, a sale day)."""

    name: str
    on: date


@dataclass(frozen=True)
class Weather:
    """Tomorrow's forecast for the business's city."""

    rain_chance: int | None = None  # percent, 0..100
    temp_max: float | None = None  # degrees Celsius
    label: str = ""


@dataclass(frozen=True)
class Loyalty:
    """Where a customer stands in a points programme."""

    next_tier: str
    points_to_next: int
    tier_points: int = 0  # points needed for that tier overall; used to judge "nearly there"


@dataclass(frozen=True)
class Customer:
    """Per-customer facts.

    ``bills`` are the item names on each recent bill, newest first. ``categories`` counts items
    bought per category. ``private`` holds anything else you keep about the person (surname,
    phone, notes): it is never put into words, and the guardrail check proves it.
    """

    id: str
    first_name: str = ""
    visits: int = 0
    rhythm: str | None = None
    first_visit: date | None = None
    bills: Sequence[Sequence[str]] = ()
    categories: Mapping[str, int] = field(default_factory=dict)
    birthday_in_days: int | None = None
    loyalty: Loyalty | None = None
    private: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.id).strip():
            raise ValueError("customer id is required")
        if self.visits < 0:
            raise ValueError("visits cannot be negative")
        if self.rhythm is not None and self.rhythm not in RHYTHMS:
            raise ValueError(f"rhythm must be one of {', '.join(RHYTHMS)}")


@dataclass(frozen=True)
class Context:
    """Business-wide facts for one send: the goal, the offer and the world around it.

    ``offer`` may be given as a plain string. ``campaign_festival`` pins the festival a festival
    campaign is about; otherwise the nearest festival from ``festivals`` in its window is used.
    """

    business: Business
    goal: str
    today: date
    offer: Offer | str | None = None
    festivals: Sequence[Festival] = ()
    campaign_festival: Festival | None = None
    events: Sequence[Event] = ()
    weather: Weather | None = None
    switches: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.offer, str):
            object.__setattr__(self, "offer", Offer(self.offer) if self.offer.strip() else None)

    @property
    def the_offer(self) -> Offer | None:
        """The offer as an ``Offer`` (strings are converted on construction)."""
        return self.offer if isinstance(self.offer, Offer) else None
