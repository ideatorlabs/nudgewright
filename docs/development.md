# Development

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
