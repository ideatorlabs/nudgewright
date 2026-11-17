"""Replaceable wording.

All words the composer can write live in a ``Phrasebook``. To localise, build your own with
``dataclasses.replace`` (or subclass) and pass it to ``compose``.

Templates use ``str.format`` fields. Each template may only use the fields listed in
``PLACEHOLDERS``; anything else is rejected when the phrasebook is created. That is how a custom
phrasebook is kept away from customer data: the composer simply never hands it more than these
fields.

Fields named ``when`` and ``until`` arrive with a leading space (``" on your next visit"``) or empty,
so templates can append them directly: ``"here's {offer}{when}"``.

The ``*_pattern`` fields are case-insensitive regular expressions used to read the owner's offer
text and to check finished lines. They are language-specific, so they live here too.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from datetime import date
from functools import lru_cache
from string import Formatter

_WHAT = frozenset({"what", "What"})

PLACEHOLDERS: dict[str, frozenset[str]] = {
    # why now: a short sentence placed first
    "birthday_week": frozenset(),
    "birthday_goal": frozenset(),
    "festival_greeting": frozenset({"festival", "emoji"}),
    "festival_on": frozenset({"festival", "date"}),
    "event": frozenset({"event", "when"}),
    "anniversary": frozenset(),
    "rain": frozenset(),
    "heat": frozenset(),
    # why this person: wraps the offer words ({what}, or {What} capitalised)
    "visit_due": _WHAT,
    "missed": _WHAT,
    "missed_winback": _WHAT,
    "regular": _WHAT,
    "one_visit": _WHAT,
    "near_tier": _WHAT | {"tier"},
    "no_person": _WHAT,
    # what to offer
    "invite": frozenset(),
    "sensitive_invite": frozenset(),
    "usual_waiting": frozenset({"item"}),
    "item_plus_offer": frozenset({"item", "offer", "when"}),
    "item_plus_free": frozenset({"item", "offer", "when"}),
    "free_offer": frozenset({"offer", "when"}),
    "item_points": frozenset({"item", "offer", "until"}),
    "points_offer": frozenset({"offer", "when"}),
    "item_offer": frozenset({"item", "offer", "until"}),
    "plain_offer": frozenset({"offer", "when"}),
    "category_plenty": frozenset({"category"}),
    "category_offer": frozenset({"offer", "category", "until"}),
    # validity and time words
    "next_visit": frozenset(),
    "until": frozenset({"date"}),
    "for_festival": frozenset({"festival"}),
    "today": frozenset(),
    "tomorrow": frozenset(),
    "this_week": frozenset(),
    "date_format": frozenset({"weekday", "day", "month"}),
    # used when a guardrail rejects a draft
    "safe_line": frozenset(),
    "sensitive_safe_line": frozenset(),
}

_PATTERNS = (
    "no_offer_pattern",
    "no_offer_prefix_pattern",
    "article_free_pattern",
    "free_pattern",
    "scoped_pattern",
    "points_pattern",
    "timed_pattern",
    "offer_marker_pattern",
    "private_pattern",
)


@lru_cache(maxsize=128)
def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


@dataclass(frozen=True)
class Phrasebook:
    """English (default) wording. Replace any field to change or translate it."""

    birthday_week: str = "Happy birthday week!"
    birthday_goal: str = "Happy birthday!"
    festival_greeting: str = "Happy {festival}! {emoji}"
    festival_on: str = "{festival} is on {date}."
    event: str = "{event} is {when}!"
    anniversary: str = "It's been a year since your first visit with us!"
    rain: str = "Rain's likely tomorrow."
    heat: str = "It's going to be a hot one tomorrow."

    visit_due: str = "It's time for your next visit. {What}."
    missed: str = "We've missed you, so {what}."
    missed_winback: str = "It's been a while, so {what}."
    regular: str = "As one of our regulars, {what}."
    one_visit: str = "Thanks for visiting us! {What}."
    near_tier: str = "You're nearly at {tier}, so {what}."
    no_person: str = "{What}."

    invite: str = "we'd love to see you soon"
    sensitive_invite: str = "book a time that suits you"
    usual_waiting: str = "your usual {item} is waiting for you"
    item_plus_offer: str = "your usual {item} is waiting, plus {offer}{when}"
    item_plus_free: str = "your usual {item} is waiting, plus a {offer}{when}"
    free_offer: str = "here's a {offer}{when}"
    item_points: str = "your next {item} earns {offer}{until}"
    points_offer: str = "you'll earn {offer}{when}"
    item_offer: str = "your next {item} is {offer}{until}"
    plain_offer: str = "here's {offer}{when}"
    category_plenty: str = "there's plenty of {category} waiting for you"
    category_offer: str = "here's {offer} on {category}{until}"

    next_visit: str = "on your next visit"
    until: str = "till {date}"
    for_festival: str = "for {festival}"
    today: str = "today"
    tomorrow: str = "tomorrow"
    this_week: str = "this week"
    date_format: str = "{weekday} {day} {month}"
    weekdays: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    months: tuple[str, ...] = (
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    )

    safe_line: str = "We'd love to see you soon."
    sensitive_safe_line: str = "Book a time that suits you."

    # reading the owner's offer text
    no_offer_pattern: str = r"^(no discount|none|n/?a|-)$"
    no_offer_prefix_pattern: str = r"^no discount\s*[·:,-]\s*"
    article_free_pattern: str = r"^an?\s+(?=free\b)"
    free_pattern: str = r"^free\b"
    scoped_pattern: str = r"^free\b|\boff\s+(?:on\s+)?\S"
    points_pattern: str = r"\bpoints?\b"
    timed_pattern: str = (
        r"\b(mon|tue|tues|wed|wednes|thu|thur|thurs|fri|sat|satur|sun)(day)?\b"
        r"|\b(till|until|today|tonight|weekend|this week)\b"
        r"|\d\s*(am|pm)\b"
        r"|\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    )
    # checking finished lines
    offer_marker_pattern: str = (
        r"\d+\s*%|\bfree\b|\bdiscounts?\b|\boff\b|\bcashback\b|\bcoupons?\b|\bpromo\b"
        r"|\bvouchers?\b|\bbogo\b|[₹$€£]\s*\d|\bbonus\b|\bpoints?\b"
    )
    private_pattern: str = r"\b\d+\s*(?:days?|weeks?|months?|years? old|visits?|points?|times|orders?)\b"

    def __post_init__(self) -> None:
        for name, allowed in PLACEHOLDERS.items():
            template = getattr(self, name)
            if not isinstance(template, str):
                raise ValueError(f"phrasebook field {name!r} must be a string")
            try:
                parsed = list(Formatter().parse(template))
            except ValueError as exc:
                raise ValueError(f"phrasebook field {name!r} is not a valid template: {exc}") from exc
            for _text, field_name, _spec, _conv in parsed:
                if field_name is not None and field_name not in allowed:
                    names = ", ".join(sorted(allowed)) or "none"
                    raise ValueError(f"phrasebook field {name!r} uses {{{field_name}}}; allowed: {names}")
        for name in _PATTERNS:
            try:
                _rx(getattr(self, name))
            except re.error as exc:
                raise ValueError(f"phrasebook pattern {name!r} does not compile: {exc}") from exc
        if len(self.weekdays) != 7 or len(self.months) != 12:
            raise ValueError("weekdays needs 7 names and months needs 12")

    # -- helpers used by the composer ---------------------------------------------------------
    def render(self, name: str, **values: str) -> str:
        """Fill template ``name`` with ``values`` (extra values are ignored)."""
        if name not in PLACEHOLDERS:
            raise KeyError(name)
        template: str = getattr(self, name)
        return template.format(**{k: v for k, v in values.items() if k in PLACEHOLDERS[name]}).strip()

    def format_date(self, day: date) -> str:
        return self.date_format.format(
            weekday=self.weekdays[day.weekday()], day=str(day.day), month=self.months[day.month - 1]
        )

    def pattern(self, name: str) -> re.Pattern[str]:
        if name not in _PATTERNS:
            raise KeyError(name)
        return _rx(getattr(self, name))

    def clean_offer(self, text: str) -> str:
        """The offer as words for a sentence: no leading "No discount ·", "a free x" becomes "free x"."""
        text = " ".join((text or "").split()).strip().rstrip(".")
        text = self.pattern("no_offer_prefix_pattern").sub("", text)
        return self.pattern("article_free_pattern").sub("", text)

    def is_no_offer(self, text: str) -> bool:
        return not text or bool(self.pattern("no_offer_pattern").search(text))


ENGLISH = Phrasebook()

TEMPLATE_FIELDS: tuple[str, ...] = tuple(f.name for f in fields(Phrasebook) if f.name in PLACEHOLDERS)
