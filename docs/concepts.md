# Concepts

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
