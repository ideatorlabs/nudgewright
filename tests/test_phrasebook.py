from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from conftest import XMAS
from nudgewright import ENGLISH, PLACEHOLDERS, Customer, Phrasebook, compose
from nudgewright.phrasebook import TEMPLATE_FIELDS


def test_every_template_is_declared() -> None:
    assert set(TEMPLATE_FIELDS) == set(PLACEHOLDERS)


def test_localised_phrasebook(make_ctx) -> None:  # type: ignore[no-untyped-def]
    spanish = replace(
        ENGLISH,
        festival_greeting="¡Feliz {festival}! {emoji}",
        missed="Te echamos de menos, así que {what}.",
        item_offer="tu próximo {item} tiene {offer}{until}",
        festival_on="{festival} es el {date}.",
        date_format="{weekday} {day} de {month}",
        weekdays=("lun", "mar", "mié", "jue", "vie", "sáb", "dom"),
        months=("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"),
    )
    cust = Customer("c1", visits=5, rhythm="overdue", bills=[["Café"], ["Café"]])
    result = compose(make_ctx("vip", offer="15% off", festivals=[XMAS]), cust, phrasebook=spanish)
    assert result.line == "¡Feliz Christmas! 🎄 Te echamos de menos, así que tu próximo Café tiene 15% off."
    assert spanish.format_date(date(2026, 12, 25)) == "vie 25 de dic"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"regular": "{first_name}, {what}"}, "allowed"),
        ({"invite": "{"}, "not a valid template"),
        ({"timed_pattern": "("}, "does not compile"),
        ({"weekdays": ("Mon",)}, "weekdays"),
        ({"rain": 3}, "must be a string"),
    ],
)
def test_invalid_phrasebooks_are_rejected(change, message) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match=message):
        Phrasebook(**change)


def test_helpers() -> None:
    assert ENGLISH.render("event", event="Quiz", when="today", extra="ignored") == "Quiz is today!"
    with pytest.raises(KeyError):
        ENGLISH.render("nope")
    with pytest.raises(KeyError):
        ENGLISH.pattern("nope")
    assert ENGLISH.clean_offer("  A free   dessert. ") == "free dessert"
    assert ENGLISH.clean_offer("No discount · double points") == "double points"
    assert ENGLISH.is_no_offer("") and ENGLISH.is_no_offer("None") and not ENGLISH.is_no_offer("10% off")
