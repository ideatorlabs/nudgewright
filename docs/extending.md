# Extending

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
