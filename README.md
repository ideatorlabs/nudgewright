<p align="center"><img src="https://raw.githubusercontent.com/ideatorlabs/.github/main/assets/avatar.png" width="72" alt="Ideator Labs"></p>
<h1 align="center">Nudgewright</h1>
<p align="center"><b>One short, personal customer message line from facts you really have, and the reasons behind it.</b><br><sub>An open-source package by <a href="https://github.com/ideatorlabs">Ideator Labs</a></sub></p>
<p align="center">
  <a href="https://github.com/ideatorlabs/nudgewright/actions/workflows/ci.yml"><img src="https://github.com/ideatorlabs/nudgewright/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License: Apache-2.0"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+">
</p>

## Why it exists

Small businesses send win-back, birthday and festival messages, and the personal part is either
missing ("Hi, we have an offer!") or made up by a language model that cheerfully promises discounts
nobody approved. Nudgewright sits in between: it writes the one personal line of a message from facts the
business actually holds, never invents the rest, refuses offers the owner didn't set, and tells you
exactly why it said what it said.

## Features

- **Pure library.** No database, no network, no language model, no dependencies.
- **Signal catalogue** with per-business switches: `auto`, `always`, `never`.
- **Five-step pipeline:** gather the signals present, pick at most three (why now > why this person >
  what to offer), write the line, check it, explain it.
- **Guardrails no switch can override:** no offer the owner didn't set; nothing about the customer
  beyond what they ordered; sensitive sectors (clinic, dental, pharmacy, …) get calendar and
  visit-due wording only; one line; a maximum length; missing data is never guessed.
- **Explainable:** every result carries `used` and `skipped` signals with reasons, and `why()`
  returns JSON-ready data.
- **Localisable** phrasebook (English by default). Templates can only see whitelisted fields.
- **Deterministic:** the same input always gives the same line.
- Optional **weather helper** (Open-Meteo, free, no key) with an injectable fetcher and an LRU cache.
- Optional **CLI**: `nudgewright compose facts.json`.

## Install

```bash
pip install nudgewright
# or, from a checkout
uv venv .venv && uv pip install -p .venv -e '.[dev]'
```

> Until the first PyPI release, install straight from GitHub:
> `pip install "nudgewright @ git+https://github.com/ideatorlabs/nudgewright"`


## 60-second quickstart

```python
from datetime import date

from nudgewright import Business, Context, Customer, Festival, compose

ctx = Context(
    business=Business(name="Demo Café", sector="cafe"),
    goal="winback",
    today=date(2026, 12, 23),
    offer="15% off",
    festivals=[Festival("Christmas", date(2026, 12, 25), "🎄")],
)
sam = Customer(
    "cust-003",
    first_name="Sam",
    visits=9,
    rhythm="overdue",
    bills=[["Smash Burger", "Cold Coffee"], ["Smash Burger"]],
)

result = compose(ctx, sam)
print(result.line)  # Happy Christmas! 🎄 It's been a while, so your next Smash Burger is 15% off.
print(result.summary())  # Used: Christmas (festival) · Regular, due for a visit · Usual order: ...
print(result.why())  # JSON-ready dict: line, level, used, skipped, guardrails
```

The line is meant to sit inside your own message template, after your greeting
("Hi Sam, a note from Demo Café: *line*"). Nudgewright never writes the customer's name itself.

## Concepts

```
 Context (business, goal, today, offer, festivals, events, weather, switches)
 Customer (first name, visits, rhythm, bills, categories, birthday, loyalty, private)
        │
        ▼
 1 gather ── signals actually present; guardrail blocks attached (sensitive sector, expired offer)
        │
 2 pick ──── switches: never → skipped · auto → only if confident · always → wins its slot
        │    slots: why now > why this person > what to offer (max 3); owner offer rides with its item
        ▼
 3 write ─── phrasebook templates
        │
 4 check ─── one line · owner offer only · no private detail · sensitive sector · max length
        │    (a failing draft is replaced by a safe line and reported)
        ▼
 5 explain ─ Composed(line, level, used, skipped, guardrails) · why() → dict
```

**Data levels.** `level` reports how much was known: `L0` contact only, `L1` visits, `L2` items and
categories, `L4` world facts (weather) used. With less data the line is shorter and more general:

| Known about the customer | Line |
|---|---|
| Name only | Happy Christmas! 🎄 Here's 15% off on your next visit. |
| + a regular, gone quiet | Happy Christmas! 🎄 It's been a while, so here's 15% off on your next visit. |
| + usually orders a burger | Happy Christmas! 🎄 It's been a while, so your next Smash Burger is 15% off. |

**Goals.** Nudgewright writes for `winback`, `second_visit`, `vip`, `birthday`, `festival` and `custom`.
Any other goal (a review request, a service message) returns an empty line and a `note`: those
should go out in the owner's own words.

**Live signals.**

| Key | Slot | Present when |
|---|---|---|
| `birthday` | now | `birthday_in_days` is 0–7 |
| `festival` | now | a calendar festival for the region is 0–3 days away (0–14 for `festival` goals), or `campaign_festival` is set |
| `own_events` | now | an owner event is 0–3 days away |
| `first_visit_anniversary` | now | a year or more since `first_visit`, within the week |
| `weather` | now | tomorrow's rain chance ≥ 60% or max ≥ 38 °C (default switch: `never`) |
| `visit_rhythm` | person | 2+ visits and `rhythm` is `overdue` or `lapsed` |
| `stage` | person | 2+ visits (a regular), or exactly 1 (not for `festival`/`custom`) |
| `loyalty` | person | close to the next tier (auto needs ≤ 20 points or ≤ 15% of the tier) |
| `usual_order` | offer | an item on 2 of the last 3 bills (auto) |
| `favourite_category` | offer | 3+ items in one category (auto) |
| `offers` | offer | the owner's offer, while valid |

`nudgewright signals` prints the full catalogue, including planned and data-dependent signals.

## Configuration

| Option | Where | Default | Meaning |
|---|---|---|---|
| `switches` | `Context` | catalogue defaults | `{signal key: "auto" \| "always" \| "never"}`; unknown keys raise |
| `max_signals` | `Rules` | 3 | slots in the words (1–3) |
| `max_length` | `Rules` | 160 | characters; longer lines are trimmed on a word with `…` |
| `sensitive_sectors` | `Rules` | clinic, dental, pharmacy, hospital, diagnostics, therapy, medical | sectors limited to calendar and visit-due wording |
| `*_window_days` | `Rules` | 3–14 | how far ahead birthdays, festivals, events and anniversaries count |
| `rain_chance_min`, `heat_temp_min` | `Rules` | 60, 38.0 | when tomorrow's weather is worth a word |
| `usual_order_min_bills`, `favourite_category_min_items` | `Rules` | 2, 3 | confidence for `auto` |
| `phrasebook` | `compose(...)` | `ENGLISH` | all wording and the language-specific patterns |

```python
from nudgewright import Rules, compose

result = compose(ctx, sam, rules=Rules(max_length=120, max_signals=2))
```

## Extending

**Localise.** Replace any template with `dataclasses.replace(ENGLISH, ...)`. Each template may only
use its whitelisted fields (`PLACEHOLDERS`); anything else raises `ValueError` at construction, so a
phrasebook can never reach customer data. Also translate `weekdays`, `months` and the `*_pattern`
regexes that read offer text and check finished lines.

```python
from dataclasses import replace
from nudgewright import ENGLISH

casual = replace(ENGLISH, missed_winback="Long time no see, so {what}.", invite="come say hi soon")
result = compose(ctx, sam, phrasebook=casual)
```

**Add a signal.** Add a `Signal` to `CATALOGUE` (status `live`, a `kind`), produce a `Candidate` for it
in `composer.gather()` with a phrasebook template, and add the template to `PLACEHOLDERS`. Picking,
switches, guardrails and the explanation work without further changes.

**Weather.** The composer never calls the network. Fetch it yourself:

```python
from nudgewright import WeatherClient

weather = WeatherClient().tomorrow("Sample City")  # Weather | None; pass as Context(weather=...)
```

`WeatherClient(fetch=my_fetch)` accepts any `(url, params) -> dict` callable, so you can use your own
HTTP client, a proxy or a fake in tests. Responses are cached for 3 hours (failures for 10 minutes).

**Festivals.** Pass your own calendar: `load_festivals("festivals.json")` reads a list of
`{name, on, emoji, regions}`. `examples/festivals.example.json` is a tiny sample.

## Running the example

```bash
python examples/compose.py                          # a café and a clinic, lines and reasons
nudgewright compose examples/facts.json --text            # the same from a JSON facts file
nudgewright compose examples/facts.json                   # JSON explanations
```

## Testing

```bash
uv venv .venv && uv pip install -p .venv -e '.[dev]'
.venv/bin/pytest --cov
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy
```

Tests never touch the network; the weather client is tested with a fake fetcher and a local
in-process HTTP server.

## Limitations and non-goals

- English wording only out of the box; other languages need a phrasebook.
- The offer reader is heuristic (it recognises "% off", "free …", "points", dates in the text). Unusual
  offer text still produces a correct but plainer line.
- Nudgewright does not decide *who* to message or *when*; it writes the line for a send you already chose.
  Consent, frequency caps and quiet hours belong in your sending system.
- No randomness: the same input always gives the same line. Variety comes from the data.
- No AI writer. A language model can be layered on top, with Nudgewright's guardrail check run on its
  output (`nudgewright.check`).
- Planned signals (refill cycles, new arrivals, stock, capacity, local events) are in the catalogue
  but not used yet.

## Roadmap

- Refill-due and "not tried yet" signals from bill history.
- Opening hours, so no line invites people on a closed day.
- More phrasebooks (contributions welcome).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports and phrasebooks for other languages are very welcome.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
