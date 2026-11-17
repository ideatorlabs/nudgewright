"""The pipeline: gather, pick, write, check, explain.

1. **gather** every signal the input really contains, each with a confidence and, where a guardrail
   applies, the reason it is blocked.
2. **pick** at most one signal per slot (why now, why this person, what to offer), at most
   ``Rules.max_signals`` slots, honouring each business's ``auto | always | never`` switches.
   The owner's offer rides in the offer slot next to the item it applies to.
3. **write** the line from the phrasebook.
4. **check** it against the guardrails.
5. **explain**: every signal ends up in ``used`` or ``skipped`` with a reason.

Less data means a shorter, more general line. Nothing missing is ever guessed.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from .facts import Context, Customer, Festival
from .guardrails import CONTENT_RULES, check, clean_name
from .phrasebook import ENGLISH, Phrasebook
from .result import Composed, Reason
from .rules import DEFAULT_RULES, Rules
from .signals import KINDS, resolve_switches

GOALS: frozenset[str] = frozenset({"winback", "second_visit", "vip", "birthday", "festival", "custom"})
"""Marketing goals the composer writes for. Any other goal gets no line (use the owner's words)."""

SENSITIVE_REASON = "sensitive sector: calendar and visit-due wording only"
_KIND_RANK = {kind: i for i, kind in enumerate(KINDS)}


@dataclass
class Candidate:
    """A signal found in the input, before picking."""

    key: str
    kind: str
    label: str
    phrase: str = ""  # phrasebook template for now/person signals
    params: dict[str, str] = field(default_factory=dict)
    strength: int = 0  # within its kind, higher wins
    item: str = ""  # for item/category signals: the name to put into words
    confident: bool = True  # "auto" only uses confident signals
    doubt: str = ""  # why it is not confident
    blocked: str = ""  # a guardrail reason; no switch overrides it


# ---- helpers ----------------------------------------------------------------------------------
def active_festival(ctx: Context, rules: Rules = DEFAULT_RULES) -> tuple[Festival, int] | None:
    """The festival this send is about, with days until it, or None.

    A festival campaign may pin its festival up to ``campaign_festival_max_days`` ahead. Otherwise the
    nearest festival for the business's region within the window is used.
    """
    if ctx.goal == "festival" and ctx.campaign_festival is not None:
        days = (ctx.campaign_festival.on - ctx.today).days
        if 0 <= days <= rules.campaign_festival_max_days:
            return ctx.campaign_festival, days
    window = rules.festival_goal_window_days if ctx.goal == "festival" else rules.festival_window_days
    near = [
        ((f.on - ctx.today).days, f.name, f)
        for f in ctx.festivals
        if f.name.strip() and f.applies_to(ctx.business.region) and 0 <= (f.on - ctx.today).days <= window
    ]
    if not near:
        return None
    days, _name, fest = min(near, key=lambda t: (t[0], t[1]))
    return fest, days


def _anniversary_in(first: date, today: date) -> int | None:
    if first.year >= today.year:
        return None
    try:
        this_year = first.replace(year=today.year)
    except ValueError:  # 29 February in a common year
        this_year = date(today.year, 3, 1)
    return (this_year - today).days


def _usual_item(customer: Customer, rules: Rules) -> tuple[str, int]:
    counts: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    display: dict[str, str] = {}
    for idx, bill in enumerate(list(customer.bills)[: rules.recent_bills]):
        on_bill: set[str] = set()  # the same item twice on one bill counts once
        for name in (clean_name(n, rules.item_name_max) for n in bill):
            fold = name.casefold()
            if not name or fold in on_bill:
                continue
            on_bill.add(fold)
            counts[fold] = counts.get(fold, 0) + 1
            first_seen.setdefault(fold, idx)
            display.setdefault(fold, name)
    if not counts:
        return "", 0
    best = min(counts, key=lambda k: (-counts[k], first_seen[k], k))
    return display[best], counts[best]


def _favourite_category(customer: Customer, rules: Rules) -> tuple[str, int]:
    cats: dict[str, tuple[str, int]] = {}
    for raw, n in customer.categories.items():
        name = clean_name(raw, rules.item_name_max)
        if name and int(n) > 0:
            prev = cats.get(name.casefold(), (name, 0))
            cats[name.casefold()] = (prev[0], prev[1] + int(n))
    if not cats:
        return "", 0
    best = min(cats, key=lambda k: (-cats[k][1], k))
    return cats[best]


# ---- 1. gather --------------------------------------------------------------------------------
def gather(
    ctx: Context, customer: Customer, *, rules: Rules = DEFAULT_RULES, phrasebook: Phrasebook = ENGLISH
) -> list[Candidate]:
    """Every signal present for this customer, before switches and ranking."""
    pb = phrasebook
    sensitive = rules.is_sensitive(ctx.business.sector)
    blocked = SENSITIVE_REASON if sensitive else ""
    out: list[Candidate] = []

    # why now
    bday = customer.birthday_in_days
    if bday is not None and 0 <= bday <= rules.birthday_window_days:
        phrase = "birthday_goal" if ctx.goal == "birthday" else "birthday_week"
        out.append(Candidate("birthday", "now", "Birthday this week", phrase, strength=30))
    fest = active_festival(ctx, rules)
    if fest:
        festival, days = fest
        if ctx.goal == "festival" and days > 1:
            params = {"festival": festival.name, "date": pb.format_date(festival.on)}
            out.append(Candidate("festival", "now", f"{festival.name} (festival)", "festival_on", params, 20))
        else:
            params = {"festival": festival.name, "emoji": festival.emoji}
            out.append(
                Candidate("festival", "now", f"{festival.name} (festival)", "festival_greeting", params, 20)
            )
    events = sorted(
        (e for e in ctx.events if e.name.strip() and 0 <= (e.on - ctx.today).days <= rules.event_window_days),
        key=lambda e: (e.on, e.name),
    )
    if events:
        ev = events[0]
        days = (ev.on - ctx.today).days
        when = pb.today if days == 0 else pb.tomorrow if days == 1 else pb.this_week
        out.append(
            Candidate(
                "own_events", "now", f"Your event: {ev.name}", "event", {"event": ev.name, "when": when}, 20
            )
        )
    if customer.first_visit:
        until = _anniversary_in(customer.first_visit, ctx.today)
        if until is not None and 0 <= until <= rules.anniversary_window_days:
            out.append(
                Candidate(
                    "first_visit_anniversary",
                    "now",
                    "A year since their first visit",
                    "anniversary",
                    strength=10,
                )
            )
    wx = ctx.weather
    if wx is not None:
        rain = (wx.rain_chance or 0) >= rules.rain_chance_min
        heat = (wx.temp_max or 0) >= rules.heat_temp_min
        if rain or heat:
            label = "Rain likely tomorrow (forecast)" if rain else "Heat likely tomorrow (forecast)"
            out.append(
                Candidate("weather", "now", label, "rain" if rain else "heat", strength=0, blocked=blocked)
            )

    # why this person
    if customer.visits >= 2 and customer.rhythm in ("overdue", "lapsed"):
        phrase = "visit_due" if sensitive else "missed_winback" if ctx.goal == "winback" else "missed"
        out.append(Candidate("visit_rhythm", "person", "Regular, due for a visit", phrase, strength=30))
    elif customer.visits >= 2:
        out.append(Candidate("stage", "person", "A regular", "regular", strength=20, blocked=blocked))
    elif customer.visits == 1 and ctx.goal not in ("festival", "custom"):
        out.append(
            Candidate(
                "stage",
                "person",
                "One visit so far",
                "one_visit",
                strength=10,
                confident=customer.rhythm != "lapsed",
                doubt="their one visit was long ago",
                blocked=blocked,
            )
        )
    loyalty = customer.loyalty
    if loyalty and loyalty.next_tier.strip() and loyalty.points_to_next > 0:
        near = loyalty.points_to_next <= max(
            rules.near_tier_points, int(loyalty.tier_points * rules.near_tier_share)
        )
        out.append(
            Candidate(
                "loyalty",
                "person",
                f"Nearly at {loyalty.next_tier} ({loyalty.points_to_next} points to go)",
                "near_tier",
                {"tier": loyalty.next_tier},
                strength=25,
                confident=near,
                doubt=f"{loyalty.points_to_next} points from {loyalty.next_tier}, not close yet",
                blocked=blocked,
            )
        )

    # what to offer
    item, seen = _usual_item(customer, rules)
    if item:
        out.append(
            Candidate(
                "usual_order",
                "offer",
                f"Usual order: {item}",
                item=item,
                strength=30,
                confident=seen >= rules.usual_order_min_bills,
                doubt=f"not on {rules.usual_order_min_bills} of their last {rules.recent_bills} bills",
                blocked=blocked,
            )
        )
    cat, count = _favourite_category(customer, rules)
    if cat:
        out.append(
            Candidate(
                "favourite_category",
                "offer",
                f"Favourite category: {cat}",
                item=cat,
                strength=20,
                confident=count >= rules.favourite_category_min_items,
                doubt=f"fewer than {rules.favourite_category_min_items} items in it",
                blocked=blocked,
            )
        )
    offer = ctx.the_offer
    if offer and offer.text.strip():
        reason = blocked
        if offer.ends_on and offer.ends_on < ctx.today:
            reason = f"the offer ended on {offer.ends_on.isoformat()}"
        out.append(
            Candidate("offers", "offer", f"Offer: {offer.text.strip()} (set by the owner)", blocked=reason)
        )
    return out


# ---- 2. pick ----------------------------------------------------------------------------------
def pick(
    found: Iterable[Candidate], switches: dict[str, str], rules: Rules = DEFAULT_RULES
) -> tuple[list[tuple[Candidate, str]], list[Reason]]:
    """Choose what goes into the words. Returns ``(used, skipped)``; ``used`` holds (candidate, mode)."""
    skipped: list[Reason] = []
    eligible: list[tuple[int, Candidate, str]] = []

    def skip(c: Candidate, mode: str, reason: str) -> None:
        skipped.append(Reason(c.key, c.label, c.kind, mode, reason))

    for index, c in enumerate(found):
        mode = switches.get(c.key, "auto")
        if c.blocked:
            skip(c, mode, c.blocked)
        elif mode == "never":
            skip(c, mode, "switched to never")
        elif mode == "auto" and not c.confident:
            skip(c, mode, c.doubt or "not confident enough")
        else:
            eligible.append((index, c, mode))

    owner_offer = [(c, m) for _i, c, m in eligible if c.key == "offers"]
    ranked = sorted(
        ((i, c, m) for i, c, m in eligible if c.key != "offers"),
        key=lambda t: (_KIND_RANK[t[1].kind], t[2] != "always", -t[1].strength, t[0]),
    )
    chosen: dict[str, tuple[Candidate, str]] = {}
    for _i, c, mode in ranked:
        if c.kind in chosen:
            skip(c, mode, f"a stronger '{c.kind}' signal was picked")
        elif len(chosen) >= rules.max_signals:
            skip(c, mode, f"only {rules.max_signals} signals fit in one line")
        else:
            chosen[c.kind] = (c, mode)
    used = [chosen[k] for k in KINDS if k in chosen]
    for c, mode in owner_offer:
        if "offer" in chosen or len(chosen) < rules.max_signals:
            used.append((c, mode))  # shares the offer slot with the item it is on
        else:
            skip(c, mode, f"only {rules.max_signals} signals fit in one line")
    return used, skipped


# ---- 3. write ---------------------------------------------------------------------------------
def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _until(ctx: Context, rules: Rules, pb: Phrasebook) -> str:
    """When the offer can be used, if it is limited: its end date, or the festival it is for."""
    offer = ctx.the_offer
    if offer and offer.ends_on:
        return pb.render("until", date=pb.format_date(offer.ends_on))
    if ctx.goal == "festival":
        fest = active_festival(ctx, rules)
        if fest:
            return pb.today if fest[1] == 0 else pb.render("for_festival", festival=fest[0].name)
    return ""


def _offer_words(pb: Phrasebook, offer: str, item: str, until: str) -> str:
    text = pb.clean_offer(offer)
    timed = bool(pb.pattern("timed_pattern").search(text))
    when = "" if timed else f" {until or pb.next_visit}"
    until_part = f" {until}" if until and not timed else ""
    if pb.is_no_offer(text):
        return pb.render("usual_waiting", item=item) if item else pb.invite
    free = bool(pb.pattern("free_pattern").search(text))
    if free:
        text = text[:1].lower() + text[1:]
    if item and pb.pattern("scoped_pattern").search(text):
        return pb.render("item_plus_free" if free else "item_plus_offer", item=item, offer=text, when=when)
    if free:
        return pb.render("free_offer", offer=text, when=when)
    if pb.pattern("points_pattern").search(text):
        text = text[:1].lower() + text[1:]
        if item:
            return pb.render("item_points", item=item, offer=text, until=until_part)
        return pb.render("points_offer", offer=text, when=when)
    if item:
        return pb.render("item_offer", item=item, offer=text, until=until_part)
    return pb.render("plain_offer", offer=text, when=when)


def write(
    ctx: Context,
    used: Iterable[Candidate],
    *,
    rules: Rules = DEFAULT_RULES,
    phrasebook: Phrasebook = ENGLISH,
) -> str:
    """The line for the chosen signals: an optional why-now sentence, then one sentence."""
    pb = phrasebook
    used = list(used)
    by_kind = {c.kind: c for c in used if c.key != "offers"}
    offer = ctx.the_offer
    offer_text = offer.text if offer and any(c.key == "offers" for c in used) else ""
    until = _until(ctx, rules, pb)
    thing = by_kind.get("offer")

    if rules.is_sensitive(ctx.business.sector):
        what = pb.sensitive_invite
    elif thing and thing.key == "favourite_category":
        category, text = thing.item.lower(), pb.clean_offer(offer_text)
        if pb.is_no_offer(text):
            what = pb.render("category_plenty", category=category)
        elif pb.pattern("scoped_pattern").search(text) or pb.pattern("points_pattern").search(text):
            what = _offer_words(pb, text, "", until)
        else:
            what = pb.render(
                "category_offer", offer=text, category=category, until=f" {until}" if until else ""
            )
    else:
        what = _offer_words(pb, offer_text, thing.item if thing else "", until)

    parts: list[str] = []
    now = by_kind.get("now")
    if now and now.phrase:
        parts.append(pb.render(now.phrase, **now.params))
    person = by_kind.get("person")
    template = person.phrase if person else "no_person"
    params = person.params if person else {}
    parts.append(pb.render(template, what=what, What=_cap(what), **params))
    return " ".join(p for p in parts if p)


# ---- 4 and 5. check and explain ---------------------------------------------------------------
def data_level(customer: Customer, used: Iterable[Candidate] = ()) -> str:
    """How much the composer knew about this customer: L0 contact … L4 world."""
    if any(c.key == "weather" for c in used):
        return "L4"
    if customer.bills or customer.categories:
        return "L2"
    if customer.visits > 0:
        return "L1"
    return "L0"


def compose(
    ctx: Context,
    customer: Customer,
    *,
    rules: Rules | None = None,
    phrasebook: Phrasebook | None = None,
) -> Composed:
    """Write one customer's line for ``ctx.goal`` and explain it. Deterministic for the same input."""
    rules = rules or DEFAULT_RULES
    pb = phrasebook or ENGLISH
    switches = resolve_switches(ctx.switches)
    if ctx.goal not in GOALS:
        return Composed(
            customer_id=customer.id,
            goal=ctx.goal,
            line="",
            level=data_level(customer),
            note=f"no line for goal {ctx.goal!r}: the composer only writes for {', '.join(sorted(GOALS))}",
        )
    picked, skipped = pick(gather(ctx, customer, rules=rules, phrasebook=pb), switches, rules)
    chosen = [c for c, _m in picked]
    draft = write(ctx, chosen, rules=rules, phrasebook=pb)
    line, findings = check(
        draft,
        ctx=ctx,
        customer=customer,
        offer_used=any(c.key == "offers" for c in chosen),
        rules=rules,
        phrasebook=pb,
    )
    used = [Reason(c.key, c.label, c.kind, m) for c, m in picked]
    if any(f.rule in CONTENT_RULES for f in findings):
        skipped += [
            Reason(r.key, r.label, r.kind, r.mode, "dropped: the draft failed a guardrail") for r in used
        ]
        used, chosen = [], []
    return Composed(
        customer_id=customer.id,
        goal=ctx.goal,
        line=line,
        level=data_level(customer, chosen),
        used=tuple(used),
        skipped=tuple(skipped),
        guardrails=findings,
    )


def compose_many(
    ctx: Context,
    customers: Iterable[Customer],
    *,
    rules: Rules | None = None,
    phrasebook: Phrasebook | None = None,
) -> dict[str, Composed]:
    """``{customer id: Composed}`` for many customers sharing one context."""
    return {c.id: compose(ctx, c, rules=rules, phrasebook=phrasebook) for c in customers}
