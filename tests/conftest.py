from __future__ import annotations

from datetime import date

import pytest

from nudgewright import Business, Context, Customer, Festival

TODAY = date(2026, 12, 23)
XMAS = Festival("Christmas", date(2026, 12, 25), "🎄")


@pytest.fixture
def cafe() -> Business:
    return Business(name="Demo Café", sector="cafe")


@pytest.fixture
def make_ctx(cafe: Business):
    def make(goal: str = "winback", **kw: object) -> Context:
        kw.setdefault("business", cafe)
        kw.setdefault("today", TODAY)
        return Context(goal=goal, **kw)  # type: ignore[arg-type]

    return make


@pytest.fixture
def regular() -> Customer:
    return Customer(
        "cust-003",
        first_name="Sam",
        visits=9,
        rhythm="overdue",
        bills=[["Smash Burger", "Cold Coffee"], ["Smash Burger"], ["Fries"]],
        categories={"Burgers": 6},
        private={"last_name": "Example", "phone": "+1 555 0142", "email": "sam@example.com"},
    )
