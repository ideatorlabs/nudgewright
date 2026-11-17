# Configuration

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
