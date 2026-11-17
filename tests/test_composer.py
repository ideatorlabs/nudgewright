from __future__ import annotations

import json
from datetime import date

import pytest

from conftest import TODAY, XMAS
from nudgewright import (
    GOALS,
    Business,
    Context,
    Customer,
    Event,
    Festival,
    Loyalty,
    Offer,
    Rules,
    Weather,
    active_festival,
    compose,
    compose_many,
)

ALONE = Customer("cust-001", first_name="Asha")


def used_keys(result) -> list[str]:  # type: ignore[no-untyped-def]
    return [r.key for r in result.used]


def skipped(result) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return {r.key: r.reason for r in result.skipped}


# ---- goals and fallbacks ------------------------------------------------------------------------
@pytest.mark.parametrize("goal", sorted(GOALS))
def test_every_supported_goal_writes_a_line(make_ctx, regular, goal) -> None:  # type: ignore[no-untyped-def]
    result = compose(make_ctx(goal, offer="15% off", festivals=[XMAS]), regular)
    assert result.line and result.goal == goal and not result.note


@pytest.mark.parametrize("goal", ["review", "feedback", "recovery", ""])
def test_other_goals_return_no_line(make_ctx, regular, goal) -> None:  # type: ignore[no-untyped-def]
    result = compose(make_ctx(goal, offer="15% off"), regular)
    assert result.line == ""
    assert "no line for goal" in result.note
    assert result.summary() == result.note
    assert result.level == "L2"


def test_empty_data_gives_the_general_line(make_ctx) -> None:  # type: ignore[no-untyped-def]
    result = compose(make_ctx(), ALONE)
    assert result.line == "We'd love to see you soon."
    assert result.used == () and result.skipped == () and result.level == "L0"
    assert result.summary() == "Used: nothing specific."


def test_less_data_means_a_shorter_line(make_ctx) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(offer="15% off", festivals=[XMAS])
    l0 = compose(ctx, ALONE)
    l1 = compose(ctx, Customer("c2", visits=6, rhythm="overdue"))
    l2 = compose(ctx, Customer("c3", visits=6, rhythm="overdue", bills=[["Smash Burger"], ["Smash Burger"]]))
    assert [r.level for r in (l0, l1, l2)] == ["L0", "L1", "L2"]
    assert len(l0.line) < len(l1.line)
    assert "Smash Burger" in l2.line and "Smash Burger" not in l1.line


def test_nothing_missing_is_invented(make_ctx) -> None:  # type: ignore[no-untyped-def]
    result = compose(make_ctx("vip"), Customer("c9", visits=3))
    assert result.line == "As one of our regulars, we'd love to see you soon."
    for word in ("off", "free", "%", "usual", "birthday"):
        assert word not in result.line.lower()


# ---- priority, slots and the limit of three ------------------------------------------------------
def full_context(make_ctx, **kw):  # type: ignore[no-untyped-def]
    return make_ctx(
        offer="15% off",
        festivals=[XMAS],
        events=[Event("Tasting night", date(2026, 12, 24))],
        weather=Weather(rain_chance=90),
        switches={"weather": "auto"},
        **kw,
    )


def test_priority_now_then_person_then_offer(make_ctx) -> None:  # type: ignore[no-untyped-def]
    busy = Customer(
        "c1",
        visits=8,
        rhythm="overdue",
        birthday_in_days=1,
        bills=[["Latte"], ["Latte"]],
        categories={"Coffee": 9},
        loyalty=Loyalty("Gold", 5, 500),
        first_visit=date(2024, 12, 24),
    )
    result = compose(full_context(make_ctx), busy)
    assert [r.kind for r in result.used] == ["now", "person", "offer", "offer"]
    assert used_keys(result) == ["birthday", "visit_rhythm", "usual_order", "offers"]
    assert len({r.kind for r in result.used}) <= 3
    reasons = skipped(result)
    for key in ("festival", "own_events", "first_visit_anniversary", "weather"):
        assert reasons[key] == "a stronger 'now' signal was picked"
    assert reasons["loyalty"] == "a stronger 'person' signal was picked"
    assert reasons["favourite_category"] == "a stronger 'offer' signal was picked"
    assert result.line.startswith("Happy birthday week! It's been a while, so your next Latte is 15% off")


@pytest.mark.parametrize(
    ("limit", "kinds"), [(1, ["now"]), (2, ["now", "person"]), (3, ["now", "person", "offer"])]
)
def test_max_signals_limits_the_slots(make_ctx, regular, limit, kinds) -> None:  # type: ignore[no-untyped-def]
    result = compose(full_context(make_ctx), regular, rules=Rules(max_signals=limit))
    assert list(dict.fromkeys(r.kind for r in result.used)) == kinds
    if limit < 3:
        assert skipped(result)["offers"] == f"only {limit} signals fit in one line"
        assert "15%" not in result.line


def test_owner_offer_takes_the_offer_slot_alone(make_ctx) -> None:  # type: ignore[no-untyped-def]
    result = compose(make_ctx(offer="15% off"), Customer("c1", visits=4))
    assert used_keys(result) == ["stage", "offers"]
    assert result.line == "As one of our regulars, here's 15% off on your next visit."


# ---- switches ------------------------------------------------------------------------------------
def test_never_skips_and_keeps_out_of_words(make_ctx, regular) -> None:  # type: ignore[no-untyped-def]
    result = compose(
        make_ctx(festivals=[XMAS], switches={"festival": "never", "usual_order": "never"}), regular
    )
    assert "Christmas" not in result.line and "Smash Burger" not in result.line
    assert skipped(result)["festival"] == "switched to never"
    assert skipped(result)["usual_order"] == "switched to never"
    assert {r.mode for r in result.skipped if r.key == "festival"} == {"never"}
    assert "Burgers" in result.line.title()  # the favourite category steps in


def test_auto_skips_low_confidence_and_always_uses_it(make_ctx) -> None:  # type: ignore[no-untyped-def]
    once = Customer("c1", visits=3, bills=[["Latte"], ["Bagel"]], categories={"Coffee": 1})
    auto = compose(make_ctx("vip"), once)
    assert skipped(auto)["usual_order"] == "not on 2 of their last 3 bills"
    assert skipped(auto)["favourite_category"] == "fewer than 3 items in it"
    forced = compose(make_ctx("vip", switches={"usual_order": "always"}), once)
    assert "usual_order" in used_keys(forced)
    assert [r.mode for r in forced.used if r.key == "usual_order"] == ["always"]
    assert "Latte" in forced.line


def test_always_wins_its_slot_over_a_stronger_auto(make_ctx) -> None:  # type: ignore[no-untyped-def]
    cust = Customer("c1", birthday_in_days=0)
    ctx = make_ctx(weather=Weather(temp_max=41), switches={"weather": "always"})
    result = compose(ctx, cust)
    assert used_keys(result) == ["weather"]
    assert result.line.startswith("It's going to be a hot one tomorrow.")
    assert result.level == "L4"
    assert skipped(result)["birthday"] == "a stronger 'now' signal was picked"


def test_weather_defaults_to_never(make_ctx) -> None:  # type: ignore[no-untyped-def]
    result = compose(make_ctx(weather=Weather(rain_chance=95)), ALONE)
    assert skipped(result) == {"weather": "switched to never"}
    on = compose(make_ctx(weather=Weather(rain_chance=95), switches={"weather": "auto"}), ALONE)
    assert on.line == "Rain's likely tomorrow. We'd love to see you soon."
    calm = compose(
        make_ctx(weather=Weather(rain_chance=10, temp_max=25), switches={"weather": "auto"}), ALONE
    )
    assert calm.used == () and calm.skipped == ()


def test_invalid_switch_raises(make_ctx) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError):
        compose(make_ctx(switches={"festival": "maybe"}), ALONE)


# ---- signals in detail ---------------------------------------------------------------------------
def test_birthday_wording_depends_on_goal(make_ctx) -> None:  # type: ignore[no-untyped-def]
    cust = Customer("c1", birthday_in_days=3)
    assert compose(make_ctx("birthday"), cust).line == "Happy birthday! We'd love to see you soon."
    assert compose(make_ctx("vip"), cust).line.startswith("Happy birthday week!")
    assert compose(make_ctx("vip"), Customer("c1", birthday_in_days=9)).used == ()


def test_festival_windows_and_wording(make_ctx) -> None:  # type: ignore[no-untyped-def]
    far = Festival("New Year", date(2027, 1, 1), "🎉")  # 9 days out
    assert compose(make_ctx("vip", festivals=[far]), ALONE).used == ()
    on = compose(make_ctx("festival", festivals=[far], offer="10% off"), ALONE)
    assert on.line == "New Year is on Fri 1 Jan. Here's 10% off for New Year."
    today = compose(
        make_ctx("festival", festivals=[Festival("Christmas", TODAY, "🎄")], offer="10% off"), ALONE
    )
    assert today.line == "Happy Christmas! 🎄 Here's 10% off today."
    assert compose(make_ctx("vip", festivals=[XMAS]), ALONE).line.startswith("Happy Christmas! 🎄")


def test_campaign_festival_is_pinned_within_sixty_days(make_ctx) -> None:  # type: ignore[no-untyped-def]
    later = Festival("Spring Fair", date(2027, 1, 30))
    result = compose(make_ctx("festival", festivals=[XMAS], campaign_festival=later), ALONE)
    assert result.line.startswith("Spring Fair is on Sat 30 Jan.")
    past = Festival("Old Fair", date(2026, 12, 1))
    ctx = make_ctx("festival", festivals=[XMAS], campaign_festival=past)
    assert active_festival(ctx) == (XMAS, 2)
    assert active_festival(make_ctx("festival", campaign_festival=past)) is None


def test_festival_regions(make_ctx) -> None:  # type: ignore[no-untyped-def]
    local = Festival("Harbour Day", date(2026, 12, 24), regions=("North Coast",))
    elsewhere = compose(make_ctx("vip", festivals=[local]), ALONE)
    assert elsewhere.used == ()
    biz = Business("Demo Café", "cafe", region="north coast")
    assert "Harbour Day" in compose(make_ctx("vip", festivals=[local], business=biz), ALONE).line


@pytest.mark.parametrize(("offset", "word"), [(0, "today"), (1, "tomorrow"), (3, "this week")])
def test_own_event_wording(make_ctx, offset, word) -> None:  # type: ignore[no-untyped-def]
    ev = Event("Tasting night", date(2026, 12, 23 + offset))
    assert compose(make_ctx("vip", events=[ev]), ALONE).line.startswith(f"Tasting night is {word}!")


def test_event_outside_window_is_ignored(make_ctx) -> None:  # type: ignore[no-untyped-def]
    ev = Event("Tasting night", date(2026, 12, 30))
    assert compose(make_ctx("vip", events=[ev]), ALONE).used == ()


def test_first_visit_anniversary(make_ctx) -> None:  # type: ignore[no-untyped-def]
    cust = Customer("c1", visits=1, first_visit=date(2025, 12, 27))
    result = compose(make_ctx("second_visit"), cust)
    assert result.line.startswith("It's been a year since your first visit with us!")
    assert (
        compose(make_ctx("second_visit"), Customer("c1", visits=1, first_visit=date(2026, 12, 24)))
        .used[0]
        .key
        == "stage"
    )
    leap = Customer("c1", first_visit=date(2024, 2, 29))
    feb = make_ctx("vip", today=date(2027, 2, 26))
    assert compose(feb, leap).used[0].key == "first_visit_anniversary"


def test_loyalty_near_and_far(make_ctx) -> None:  # type: ignore[no-untyped-def]
    near = compose(make_ctx("vip"), Customer("c1", loyalty=Loyalty("Gold", 15, 500)))
    assert near.line == "You're nearly at Gold, so we'd love to see you soon."
    far = compose(make_ctx("vip"), Customer("c1", loyalty=Loyalty("Gold", 300, 500)))
    assert skipped(far)["loyalty"] == "300 points from Gold, not close yet"
    assert "300" not in far.line
    done = compose(make_ctx("vip"), Customer("c1", loyalty=Loyalty("Gold", 0, 500)))
    assert done.used == () and done.skipped == ()


def test_one_visit_customers(make_ctx) -> None:  # type: ignore[no-untyped-def]
    fresh = compose(make_ctx("second_visit"), Customer("c1", visits=1, rhythm="due"))
    assert fresh.line == "Thanks for visiting us! We'd love to see you soon."
    stale = compose(make_ctx("second_visit"), Customer("c1", visits=1, rhythm="lapsed"))
    assert skipped(stale)["stage"] == "their one visit was long ago"
    assert compose(make_ctx("festival"), Customer("c1", visits=1)).used == ()


def test_winback_and_missed_wording(make_ctx) -> None:  # type: ignore[no-untyped-def]
    cust = Customer("c1", visits=4, rhythm="lapsed")
    assert compose(make_ctx("winback"), cust).line.startswith("It's been a while")
    assert compose(make_ctx("vip"), cust).line.startswith("We've missed you")


def test_usual_item_counts_bills_not_lines(make_ctx) -> None:  # type: ignore[no-untyped-def]
    cust = Customer("c1", bills=[["Latte", "latte", "Item", ""], ["Mocha"], ["Mocha"], ["Latte"]])
    result = compose(make_ctx("vip"), cust)
    assert "Mocha" in result.line  # only the last three bills count, and duplicates count once
    recent = Customer("c1", bills=[["Tea"], ["Scone", "Tea"], ["Scone"]])
    assert "Tea" in compose(make_ctx("vip"), recent).line  # a tie goes to the most recently bought
    same_bill = Customer("c1", bills=[["Tea", "Scone"], ["Scone", "Tea"]])
    assert "Scone" in compose(make_ctx("vip"), same_bill).line  # then alphabetical, so it stays stable


# ---- offer wording -------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("offer", "bills", "expected"),
    [
        ("No discount", [], "We'd love to see you soon."),
        ("No discount", [["Latte"], ["Latte"]], "Your usual Latte is waiting for you."),
        ("No discount · double points", [], "You'll earn double points on your next visit."),
        ("double points", [["Latte"], ["Latte"]], "Your next Latte earns double points."),
        ("A free dessert", [], "Here's a free dessert on your next visit."),
        (
            "Free dessert",
            [["Latte"], ["Latte"]],
            "Your usual Latte is waiting, plus a free dessert on your next visit.",
        ),
        (
            "₹200 off drinks",
            [["Latte"], ["Latte"]],
            "Your usual Latte is waiting, plus ₹200 off drinks on your next visit.",
        ),
        ("15% off", [["Latte"], ["Latte"]], "Your next Latte is 15% off."),
        ("15% off.", [], "Here's 15% off on your next visit."),
        ("20% off, Fri to Sun", [], "Here's 20% off, Fri to Sun."),
    ],
)
def test_offer_wording(make_ctx, offer, bills, expected) -> None:  # type: ignore[no-untyped-def]
    assert compose(make_ctx("custom", offer=offer), Customer("c1", bills=bills)).line == expected


def test_offer_end_date_replaces_next_visit(make_ctx) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx("custom", offer=Offer("15% off", ends_on=date(2026, 12, 27)))
    assert compose(ctx, ALONE).line == "Here's 15% off till Sun 27 Dec."
    item = Customer("c1", bills=[["Latte"], ["Latte"]])
    assert compose(ctx, item).line == "Your next Latte is 15% off till Sun 27 Dec."


def test_expired_offer_is_never_mentioned(make_ctx) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx("custom", offer=Offer("15% off", ends_on=date(2026, 12, 1)))
    result = compose(ctx, ALONE)
    assert "15%" not in result.line
    assert skipped(result)["offers"] == "the offer ended on 2026-12-01"


@pytest.mark.parametrize(
    ("offer", "expected"),
    [
        ("", "There's plenty of coffee waiting for you."),
        ("15% off", "Here's 15% off on coffee."),
        ("double points", "You'll earn double points on your next visit."),
        ("₹50 off pastries", "Here's ₹50 off pastries on your next visit."),
    ],
)
def test_category_wording(make_ctx, offer, expected) -> None:  # type: ignore[no-untyped-def]
    cust = Customer("c1", categories={"Coffee": 4, "Tea": 4, "Item": 9})
    assert compose(make_ctx("custom", offer=offer), cust).line == expected


def test_category_offer_until(make_ctx) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx("custom", offer=Offer("15% off", ends_on=date(2026, 12, 24)))
    assert (
        compose(ctx, Customer("c1", categories={"Coffee": 4})).line
        == "Here's 15% off on coffee till Thu 24 Dec."
    )


# ---- determinism and explanation -----------------------------------------------------------------
def test_same_input_same_output(make_ctx, regular) -> None:  # type: ignore[no-untyped-def]
    ctx = full_context(make_ctx)
    first = compose(ctx, regular)
    assert all(compose(ctx, regular) == first for _ in range(5))
    swapped = Customer(
        "cust-003", visits=9, rhythm="overdue", bills=regular.bills, categories={"B": 3, "A": 3}
    )
    assert compose(ctx, swapped).why() == compose(ctx, swapped).why()


def test_compose_many(make_ctx, regular) -> None:  # type: ignore[no-untyped-def]
    out = compose_many(make_ctx(offer="15% off"), [ALONE, regular])
    assert list(out) == ["cust-001", "cust-003"]
    assert out["cust-003"] == compose(make_ctx(offer="15% off"), regular)


def test_why_is_json_and_complete(make_ctx, regular) -> None:  # type: ignore[no-untyped-def]
    result = compose(make_ctx(offer="15% off", festivals=[XMAS]), regular)
    data = json.loads(json.dumps(result.why()))
    assert set(data) == {"customer_id", "goal", "line", "level", "used", "skipped", "guardrails", "note"}
    assert data["line"] == result.line
    assert data["used"][0] == {
        "key": "festival",
        "label": "Christmas (festival)",
        "kind": "now",
        "mode": "auto",
    }
    assert data["skipped"][0]["reason"]
    text = result.summary()
    assert text.startswith("Used: Christmas (festival)") and "Skipped:" in text


def test_context_and_model_validation() -> None:
    assert Context(Business(), "vip", TODAY, offer="  ").offer is None
    assert Context(Business(), "vip", TODAY, offer="10% off").the_offer == Offer("10% off")
    with pytest.raises(ValueError):
        Customer(" ")
    with pytest.raises(ValueError):
        Customer("c1", visits=-1)
    with pytest.raises(ValueError):
        Customer("c1", rhythm="sometimes")
    with pytest.raises(ValueError):
        Rules(max_signals=4)
    with pytest.raises(ValueError):
        Rules(max_length=5)
    assert Rules(sensitive_sectors=frozenset({"Vet"})).is_sensitive(" vet ")
