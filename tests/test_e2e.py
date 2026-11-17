"""End to end: the example script, the CLI as a process, and every README code sample."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import nudgewright.weather as weather_module

ROOT = Path(__file__).resolve().parent.parent


def test_example_runs_for_real() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "compose.py")], capture_output=True, text=True, check=True
    )
    out = proc.stdout
    assert "Happy Christmas! 🎄 It's been a while, so your next Smash Burger is 15% off." in out
    assert "Rain's likely tomorrow." in out
    assert "It's time for your next visit. Book a time that suits you." in out
    assert "(no line)" in out
    assert "+1 555 0142" not in out and "Example" not in out.replace("Example Region", "")


def test_example_main_returns_explanations() -> None:
    sys.path.insert(0, str(ROOT / "examples"))
    try:
        import compose as example  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    results = example.main()
    json.dumps(results)
    assert len(results) == 10
    assert {r["level"] for r in results} >= {"L0", "L1", "L2", "L4"}


def test_cli_as_a_process() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "nudgewright", "compose", str(ROOT / "examples" / "facts.json")],
        capture_output=True,
        text=True,
        check=True,
    )
    assert len(json.loads(proc.stdout)) == 3


def _readme_blocks() -> list[str]:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    return re.findall(r"```python\n(.*?)```", text, flags=re.S)


def test_readme_samples_run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fake_fetcher(*_a: object, **_k: object):  # type: ignore[no-untyped-def]
        def fetch(url: str, params: object) -> object:
            if "geocoding" in url:
                return {"results": [{"latitude": 1.0, "longitude": 2.0}]}
            return {
                "daily": {
                    "time": ["d0", "d1"],
                    "weather_code": [0, 61],
                    "precipitation_probability_max": [0, 70],
                }
            }

        return fetch

    monkeypatch.setattr(weather_module, "urllib_fetcher", fake_fetcher)  # README weather sample stays offline
    blocks = _readme_blocks()
    assert len(blocks) >= 4
    namespace: dict[str, object] = {}
    for block in blocks:
        exec(compile(block, "README.md", "exec"), namespace)
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "Happy Christmas! 🎄 It's been a while, so your next Smash Burger is 15% off."
    assert out[1].startswith("Used: Christmas (festival) · Regular, due for a visit · Usual order:")
    assert namespace["weather"] is not None
    assert namespace["result"].line.startswith("Happy Christmas! 🎄 Long time no see")  # type: ignore[attr-defined]
