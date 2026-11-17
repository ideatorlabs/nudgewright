# Contributing to Nudgewright

Thanks for helping. Small, focused pull requests are easiest to review.

## Setup

```bash
uv venv .venv
uv pip install -p .venv -e '.[dev]'
```

## Checks

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/pytest --cov
```

CI runs the same checks on Python 3.10 to 3.13.

## Pull requests

- Open an issue first for larger changes (new signals, new guardrails, API changes).
- Add or update tests; coverage must stay at or above 90%.
- Tests must never call the network or a paid API. Fake HTTP with an injected fetcher.
- Guardrails are not switchable by design. A change that weakens one needs a strong case.
- Use fictional names and businesses in tests and examples.
- Update `CHANGELOG.md` under "Unreleased".

No CLA or DCO sign-off is required. By contributing you agree that your work is licensed under
Apache-2.0.
