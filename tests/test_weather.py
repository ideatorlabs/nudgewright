from __future__ import annotations

import json
import threading
from collections.abc import Iterator, Mapping
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from nudgewright import TTLCache, Weather, WeatherClient, classify, urllib_fetcher

GEO = {"results": [{"latitude": 12.5, "longitude": 77.25}]}
DAILY = {
    "daily": {
        "time": ["2026-12-23", "2026-12-24"],
        "weather_code": [0, 63],
        "temperature_2m_max": [24.5, 21.0],
        "precipitation_probability_max": [5, 80],
    }
}


class FakeFetch:
    def __init__(self, geo: Any = GEO, daily: Any = DAILY, fail: str = "") -> None:
        self.geo, self.daily, self.fail = geo, daily, fail
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, url: str, params: Mapping[str, Any]) -> Any:
        self.calls.append((url, dict(params)))
        if self.fail and self.fail in url:
            raise OSError("offline")
        return self.geo if "geocoding" in url else self.daily


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_tomorrow_and_caching() -> None:
    fetch = FakeFetch()
    client = WeatherClient(fetch)
    assert client.tomorrow("Sample City") == Weather(rain_chance=80, temp_max=21.0, label="rainy")
    assert client.tomorrow("sample city ") == Weather(rain_chance=80, temp_max=21.0, label="rainy")
    assert len(fetch.calls) == 2  # one geocode, one forecast; the second call is served from cache
    params = fetch.calls[1][1]
    assert params["latitude"] == 12.5 and params["forecast_days"] == 2
    days = client.forecast("Sample City", days=99)
    assert days[0].bucket == "good" and fetch.calls[-1][1]["forecast_days"] == 14


def test_failures_return_empty_and_expire() -> None:
    clock = Clock()
    fetch = FakeFetch(fail="forecast")
    client = WeatherClient(fetch, clock=clock, failure_ttl=60)
    assert client.tomorrow("Sample City") is None
    assert client.tomorrow("Sample City") is None
    assert len(fetch.calls) == 2  # failure cached
    clock.now += 61
    fetch.fail = ""
    assert client.tomorrow("Sample City") is not None


def test_geocode_failures_and_empty_city() -> None:
    assert WeatherClient(FakeFetch(fail="geocoding")).geocode("Nowhere") is None
    assert WeatherClient(FakeFetch(geo={"results": []})).tomorrow("Nowhere") is None
    assert WeatherClient(FakeFetch()).geocode("  ") is None
    one_day = {"daily": {"time": ["2026-12-23"], "weather_code": [95]}}
    client = WeatherClient(FakeFetch(daily=one_day))
    assert client.tomorrow("Sample City") is None
    assert client.forecast("Sample City", days=1)[0].temp_max is None


def test_ttl_cache_lru_and_expiry() -> None:
    clock = Clock()
    cache = TTLCache(maxsize=2, clock=clock)
    cache.put("a", 1, ttl=10)
    cache.put("b", 2, ttl=10)
    assert cache.get("a") == (True, 1)  # "a" is now most recent
    cache.put("c", 3, ttl=10)
    assert cache.get("b") == (False, None) and len(cache) == 2
    clock.now += 11
    assert cache.get("a") == (False, None)
    with pytest.raises(ValueError):
        TTLCache(0)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0, ("clear", "good")),
        (2, ("partly cloudy", "good")),
        (45, ("foggy", "dull")),
        (61, ("rainy", "wet")),
        (73, ("snowy", "wet")),
        (95, ("stormy", "wet")),
        (7, ("mixed", "dull")),
    ],
)
def test_classify(code: int, expected: tuple[str, str]) -> None:
    assert classify(code) == expected


@pytest.fixture
def local_server() -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            body = json.dumps({"path": self.path, "agent": self.headers.get("User-Agent")}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_urllib_fetcher_against_a_local_server(local_server: str) -> None:
    data = urllib_fetcher(timeout=5)(f"{local_server}/v1/search", {"name": "Sample City", "skip": None})
    assert data["path"] == "/v1/search?name=Sample+City"
    assert data["agent"] == "nudgewright"
