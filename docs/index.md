---
hide:
  - navigation
---

<div class="il-hero" markdown>
<img src="assets/brand/icon-512.png" alt="" width="112" height="112">
<div markdown>
# Nudgewright
<p class="il-tagline">One honest, personal line, and the reasons why</p>
<p class="il-by">An open-source package by <a href="https://ideatorlabs.github.io/">Ideator Labs</a></p>
[Get started](#install){ .md-button .md-button--primary }
[GitHub](https://github.com/ideatorlabs/nudgewright){ .md-button }
</div>
</div>

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
