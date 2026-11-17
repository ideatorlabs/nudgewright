"""End-to-end example: a fictional café and clinic, a few fictional customers, lines and reasons.

Run it with:  python examples/compose.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from nudgewright import Business, Context, Customer, Event, Loyalty, Offer, Weather, compose, load_festivals

HERE = Path(__file__).parent
TODAY = date(2026, 12, 23)  # fixed, so the output is the same every run

CUSTOMERS = [
    Customer("cust-001", first_name="Asha"),  # only a name and consent: L0
    Customer("cust-002", first_name="Ravi", visits=7, rhythm="overdue"),  # a regular who has gone quiet: L1
    Customer(  # a regular with item history: L2
        "cust-003",
        first_name="Sam",
        visits=9,
        rhythm="overdue",
        bills=[["Smash Burger", "Cold Coffee"], ["Smash Burger"], ["Fries"]],
        categories={"Burgers": 6, "Drinks": 3},
        private={"last_name": "Example", "phone": "+1 555 0142"},  # held, never written
    ),
    Customer("cust-004", first_name="Mia", visits=1, bills=[["Latte"]], birthday_in_days=2),
    Customer(
        "cust-005",
        first_name="Noor",
        visits=4,
        rhythm="on_track",
        categories={"Coffee": 5},
        loyalty=Loyalty(next_tier="Gold", points_to_next=15, tier_points=500),
    ),
]


def show(title: str, ctx: Context, customers: list[Customer]) -> list[dict[str, object]]:
    print(f"\n== {title}")
    out = []
    for customer in customers:
        result = compose(ctx, customer)
        print(f"{customer.first_name:>5} [{result.level}] {result.line or '(no line)'}")
        print(f"        why: {result.summary()}")
        out.append(result.why())
    return out


def main() -> list[dict[str, object]]:
    festivals = load_festivals(HERE / "festivals.example.json")
    cafe = Business(name="Demo Café", sector="cafe", city="Sample City")
    results = []

    winback = Context(cafe, "winback", TODAY, offer=Offer("15% off"), festivals=festivals)
    results += show("Café win-back, 15% off, Christmas in two days", winback, CUSTOMERS)

    rainy = Context(
        cafe,
        "vip",
        TODAY,
        offer=Offer("a free dessert", ends_on=date(2026, 12, 24)),
        events=[Event("Live music night", date(2026, 12, 24))],
        weather=Weather(rain_chance=80, temp_max=21),
        switches={"weather": "always", "own_events": "never"},  # the owner turned weather on, events off
    )
    results += show("Café regulars, free dessert till tomorrow, rain forecast", rainy, CUSTOMERS[1:3])

    clinic = Context(
        Business("Sample Dental", "dental"), "winback", TODAY, offer="20% off", festivals=festivals
    )
    results += show("Dental clinic (sensitive sector)", clinic, CUSTOMERS[1:3])

    review = Context(cafe, "review", TODAY)
    results += show("A goal Nudgewright does not write for", review, CUSTOMERS[:1])

    print("\nFull explanation for the last café customer, as JSON:")
    print(json.dumps(results[2], indent=2, ensure_ascii=False))
    return results


if __name__ == "__main__":
    main()
