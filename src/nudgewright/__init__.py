"""Nudgewright: explainable, guard-railed personalised message lines.

Give it the facts a business really has about a customer and the world; it picks at most three
(why now, why this person, what to offer), writes one short line, checks it against fixed guardrails
and tells you exactly what it used and skipped.
"""

from .composer import GOALS, active_festival, compose, compose_many, data_level, gather, pick, write
from .facts import RHYTHMS, Business, Context, Customer, Event, Festival, Loyalty, Offer, Weather
from .guardrails import check
from .loader import context_from_dict, customer_from_dict, load_facts, load_facts_file, load_festivals
from .phrasebook import ENGLISH, PLACEHOLDERS, Phrasebook
from .result import Composed, Finding, Reason
from .rules import DEFAULT_RULES, DEFAULT_SENSITIVE_SECTORS, Rules
from .signals import BY_KEY, CATALOGUE, GROUPS, KINDS, MODES, Signal, catalogue, resolve_switches
from .weather import DayForecast, TTLCache, WeatherClient, classify, urllib_fetcher

__version__ = "0.1.0"

__all__ = [
    "BY_KEY",
    "CATALOGUE",
    "DEFAULT_RULES",
    "DEFAULT_SENSITIVE_SECTORS",
    "ENGLISH",
    "GOALS",
    "GROUPS",
    "KINDS",
    "MODES",
    "PLACEHOLDERS",
    "RHYTHMS",
    "Business",
    "Composed",
    "Context",
    "Customer",
    "DayForecast",
    "Event",
    "Festival",
    "Finding",
    "Loyalty",
    "Offer",
    "Phrasebook",
    "Reason",
    "Rules",
    "Signal",
    "TTLCache",
    "Weather",
    "WeatherClient",
    "__version__",
    "active_festival",
    "catalogue",
    "check",
    "classify",
    "compose",
    "compose_many",
    "context_from_dict",
    "customer_from_dict",
    "data_level",
    "gather",
    "load_facts",
    "load_facts_file",
    "load_festivals",
    "pick",
    "resolve_switches",
    "urllib_fetcher",
    "write",
]
