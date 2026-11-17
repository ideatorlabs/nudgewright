"""Checks every finished line must pass. None of these can be switched off.

* One line: line breaks and runs of spaces are collapsed.
* No offer the owner didn't set: offer words may only come from the owner's own offer text.
* Nothing about the customer beyond their first name and what they ordered: private values, the
  customer id and counted facts ("34 days", "120 points") are rejected.
* Sensitive sectors: no item or category names at all.
* Maximum length: trimmed on a word boundary with an ellipsis.

A draft that breaks one of the content rules is replaced by the phrasebook's safe line, and the
finding is reported, so a bad template or odd data can never reach a customer.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from .facts import Context, Customer
from .phrasebook import Phrasebook
from .result import Finding
from .rules import Rules

CONTENT_RULES: frozenset[str] = frozenset({"offer_not_set", "private_detail", "sensitive_sector"})
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean_name(value: object, limit: int = 60) -> str:
    """A tidy item or category name, or "" when it is empty or a placeholder."""
    name = " ".join(str(value or "").split())[:limit].strip()
    return "" if name.casefold() in ("", "item", "items", "misc", "n/a") else name


def customer_terms(customer: Customer, limit: int = 60) -> list[str]:
    """Every item and category name on file for the customer."""
    terms = [clean_name(n, limit) for bill in customer.bills for n in bill]
    terms += [clean_name(c, limit) for c in customer.categories]
    return [t for t in dict.fromkeys(terms) if t]


def owner_terms(ctx: Context, customer: Customer) -> list[str]:
    """Names the owner or calendar supplied, which may legitimately appear in a line."""
    terms = [ctx.business.name]
    terms += [f.name for f in ctx.festivals]
    if ctx.campaign_festival:
        terms.append(ctx.campaign_festival.name)
    terms += [e.name for e in ctx.events]
    if customer.loyalty:
        terms.append(customer.loyalty.next_tier)
    return [t for t in terms if t and t.strip()]


def _mask(text: str, terms: Iterable[str]) -> str:
    for term in sorted({t.strip() for t in terms if len(t.strip()) >= 2}, key=len, reverse=True):
        text = re.sub(re.escape(term), " ", text, flags=re.IGNORECASE)
    return text


def _contains(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.IGNORECASE))


def trim(line: str, max_length: int) -> str:
    """Cut to ``max_length`` characters on a word boundary, ending with an ellipsis."""
    if len(line) <= max_length:
        return line
    cut = line[: max_length - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(",;:-– ") + "…"


def check(
    line: str,
    *,
    ctx: Context,
    customer: Customer,
    offer_used: bool,
    rules: Rules,
    phrasebook: Phrasebook,
) -> tuple[str, tuple[Finding, ...]]:
    """Return the line as it may be sent, and what the check changed."""
    findings: list[Finding] = []
    if "\n" in line or "\r" in line:
        findings.append(Finding("one_line", "line breaks removed", "adjusted"))
    flat = " ".join(_CONTROL.sub(" ", line).split())

    sensitive = rules.is_sensitive(ctx.business.sector)
    items = customer_terms(customer, rules.item_name_max)
    allowed = owner_terms(ctx, customer)
    offer = ctx.the_offer
    if offer_used and offer:
        allowed += [offer.text, phrasebook.clean_offer(offer.text)]
    masked = _mask(flat, allowed if sensitive else allowed + items)

    violations: list[Finding] = []
    marker = phrasebook.pattern("offer_marker_pattern").search(masked)
    if marker:
        violations.append(
            Finding("offer_not_set", f"offer wording {marker.group(0)!r} without an owner offer", "replaced")
        )
    secrets = [str(v) for v in customer.private.values() if len(str(v).strip()) >= 3]
    if len(customer.id) >= 4:
        secrets.append(customer.id)
    leaked = [s for s in secrets if _contains(masked, s.strip())]
    counted = phrasebook.pattern("private_pattern").search(masked)
    if leaked:
        violations.append(Finding("private_detail", "a private customer value appeared", "replaced"))
    elif counted:
        violations.append(
            Finding("private_detail", f"a counted fact {counted.group(0)!r} appeared", "replaced")
        )
    if sensitive and any(_contains(masked, t) for t in items):
        violations.append(Finding("sensitive_sector", "an item or category was named", "replaced"))

    if violations:
        findings += violations
        flat = phrasebook.sensitive_safe_line if sensitive else phrasebook.safe_line

    if len(flat) > rules.max_length:
        findings.append(Finding("max_length", f"trimmed to {rules.max_length} characters", "adjusted"))
        flat = trim(flat, rules.max_length)
    return flat, tuple(findings)
