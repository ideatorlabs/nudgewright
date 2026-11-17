from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from conftest import XMAS
from nudgewright import (
    ENGLISH,
    GOALS,
    Business,
    Customer,
    Event,
    Loyalty,
    Offer,
    Rules,
    Weather,
    check,
    compose,
)
from nudgewright.guardrails import clean_name, trim
from nudgewright.signals import CATALOGUE

CLINIC = Business("Sample Dental", "dental")
ALWAYS = {s.key: "always" for s in CATALOGUE}


def rules_of(result) -> list[str]:  # type: ignore[no-untyped-def]
    return [g.rule for g in result.guardrails]


# ---- no offer the owner didn't set ---------------------------------------------------------------
def test_no_offer_words_without_an_owner_offer(make_ctx, regular) -> None:  # type: ignore[no-untyped-def]
    for goal in sorted(GOALS):
        line = compose(make_ctx(goal, festivals=[XMAS]), regular).line.lower()
        for word in ("% off", "free", "discount", "points", "₹"):
            assert word not in line


def test_template_that_invents_an_offer_is_replaced(make_ctx) -> None:  # type: ignore[no-untyped-def]
    sneaky = replace(ENGLISH, invite="grab a free coffee soon")
    result = compose(make_ctx("vip"), Customer("c1", visits=3), phrasebook=sneaky)
    assert result.line == ENGLISH.safe_line
    assert rules_of(result) == ["offer_not_set"]
    assert result.guardrails[0].action == "replaced"
    assert result.used == ()
    assert [r.reason for r in result.skipped] == ["dropped: the draft failed a guardrail"]
    assert result.why()["guardrails"][0]["rule"] == "offer_not_set"
    assert "Guardrails: offer_not_set" in result.summary()


def test_offer_set_but_not_picked_still_cannot_appear(make_ctx) -> None:  # type: ignore[no-untyped-def]
    sneaky = replace(ENGLISH, missed="We've missed you, so 15% off awaits.")
    ctx = make_ctx("vip", offer="15% off", festivals=[XMAS])
    result = compose(
        ctx, Customer("c1", visits=4, rhythm="overdue"), rules=Rules(max_signals=2), phrasebook=sneaky
    )
    assert rules_of(result) == ["offer_not_set"]
    assert result.line == ENGLISH.safe_line


def test_owner_words_and_item_names_are_not_mistaken_for_offers(make_ctx) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx("vip", events=[Event("Free jazz evening", date(2026, 12, 24))])
    cust = Customer("c1", bills=[["Gluten-free bread"], ["Gluten-free bread"]])
    result = compose(ctx, cust)
    assert result.guardrails == ()
    assert result.line == "Free jazz evening is tomorrow! Your usual Gluten-free bread is waiting for you."
    offer = compose(make_ctx("custom", offer="Buy 2 get 1 free"), Customer("c1"))
    assert offer.guardrails == ()
    assert offer.line == "Here's Buy 2 get 1 free on your next visit."


# ---- nothing about the customer beyond first name and what they ordered ----------------------------
def test_private_values_never_reach_the_line(make_ctx, regular) -> None:  # type: ignore[no-untyped-def]
    ctx_kw = {"offer": "15% off", "festivals": [XMAS], "weather": Weather(rain_chance=80)}
    for goal in sorted(GOALS):
        for switches in ({}, ALWAYS):
            result = compose(make_ctx(goal, switches=switches, **ctx_kw), regular)
            for value in [*regular.private.values(), regular.id, "9", "6"]:
                assert value not in result.line


def test_counted_facts_are_never_stated(make_ctx) -> None:  # type: ignore[no-untyped-def]
    cust = Customer("c1", visits=12, rhythm="lapsed", loyalty=Loyalty("Gold", 300, 500))
    result = compose(make_ctx("winback", switches={"loyalty": "always"}), cust)
    assert "300" not in result.line and "12" not in result.line
    assert "Gold" in result.line


def test_phrasebook_cannot_reach_customer_data() -> None:
    with pytest.raises(ValueError, match="allowed"):
        replace(ENGLISH, regular="Hi {phone}, {what}.")
    with pytest.raises(ValueError, match="allowed"):
        replace(ENGLISH, regular="{what.__class__}")


@pytest.mark.parametrize(
    ("line", "detail"),
    [
        ("Hi, your number +1 555 0142 is on file.", "private customer value"),
        ("Order ref cust-003 is ready.", "private customer value"),
        ("It's been 34 days since we saw you.", "counted fact"),
        ("Only 120 points to go!", "counted fact"),
    ],
)
def test_check_rejects_private_details(make_ctx, regular, line, detail) -> None:  # type: ignore[no-untyped-def]
    out, findings = check(
        line, ctx=make_ctx(), customer=regular, offer_used=False, rules=Rules(), phrasebook=ENGLISH
    )
    assert out == ENGLISH.safe_line
    private = [f for f in findings if f.rule == "private_detail"]
    assert len(private) == 1 and detail in private[0].detail


# ---- sensitive sectors ----------------------------------------------------------------------------
def test_sensitive_sector_ignores_always_switches(make_ctx, regular) -> None:  # type: ignore[no-untyped-def]
    rich = replace(regular, loyalty=Loyalty("Gold", 5, 500), birthday_in_days=None)
    ctx = make_ctx(
        "winback",
        business=CLINIC,
        offer="20% off",
        weather=Weather(rain_chance=90),
        festivals=[XMAS],
        switches=ALWAYS,
    )
    result = compose(ctx, rich)
    assert result.line == "Happy Christmas! 🎄 It's time for your next visit. Book a time that suits you."
    assert [r.key for r in result.used] == ["festival", "visit_rhythm"]
    blocked = {r.key for r in result.skipped if r.reason.startswith("sensitive sector")}
    assert blocked == {"weather", "loyalty", "usual_order", "favourite_category", "offers"}
    for word in ("Burger", "Fries", "20%", "Gold", "Rain"):
        assert word not in result.line


@pytest.mark.parametrize("sector", ["clinic", "Pharmacy", "dental"])
def test_sensitive_sectors_get_calendar_or_visit_due_only(make_ctx, sector) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx("vip", business=Business("Sample", sector), offer="free check-up")
    assert compose(ctx, Customer("c1", visits=5)).line == "Book a time that suits you."
    assert (
        compose(ctx, Customer("c1", birthday_in_days=1)).line
        == "Happy birthday week! Book a time that suits you."
    )


def test_sensitive_sectors_are_configurable(make_ctx) -> None:  # type: ignore[no-untyped-def]
    vet_rules = Rules(sensitive_sectors=frozenset({"vet"}))
    ctx = make_ctx("vip", business=Business("Sample Vet", "vet"), offer="10% off")
    assert compose(ctx, Customer("c1", visits=4), rules=vet_rules).line == "Book a time that suits you."
    clinic = make_ctx("vip", business=CLINIC, offer="10% off")
    assert "10% off" in compose(clinic, Customer("c1", visits=4), rules=vet_rules).line


def test_check_rejects_items_in_sensitive_sector(make_ctx, regular) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(business=CLINIC)
    out, findings = check(
        "Your usual Smash Burger awaits.",
        ctx=ctx,
        customer=regular,
        offer_used=False,
        rules=Rules(),
        phrasebook=ENGLISH,
    )
    assert out == ENGLISH.sensitive_safe_line
    assert [f.rule for f in findings] == ["sensitive_sector"]


# ---- one line and length ---------------------------------------------------------------------------
def test_line_breaks_are_removed(make_ctx) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx("vip", events=[Event("Tasting\nnight", date(2026, 12, 23))])
    result = compose(ctx, Customer("c1"))
    assert "\n" not in result.line
    assert result.line.startswith("Tasting night is today!")
    assert rules_of(result) == ["one_line"]
    assert result.used  # an adjusted line keeps its signals


def test_long_lines_are_trimmed_on_a_word(make_ctx) -> None:  # type: ignore[no-untyped-def]
    long_offer = Offer("a free dessert and a complimentary welcome drink for the whole table " * 3)
    result = compose(make_ctx("custom", offer=long_offer, festivals=[XMAS]), Customer("c1", visits=4))
    assert len(result.line) <= 160
    assert result.line.endswith("…")
    assert rules_of(result) == ["max_length"]
    short = compose(make_ctx("custom", offer=long_offer), Customer("c1"), rules=Rules(max_length=40))
    assert len(short.line) <= 40


def test_trim_and_clean_helpers() -> None:
    assert trim("short", 10) == "short"
    assert trim("x" * 30, 10) == "x" * 9 + "…"
    assert trim("one two, three", 10) == "one two…"
    assert clean_name("  Cold   Coffee ") == "Cold Coffee"
    assert clean_name("ITEM") == "" and clean_name(None) == ""
    assert len(clean_name("a" * 100, 60)) == 60
