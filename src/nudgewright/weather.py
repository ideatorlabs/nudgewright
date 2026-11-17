"""Optional forecast helper built on Open-Meteo (free, no API key).

The composer never calls the network. If you want the ``weather`` signal, fetch tomorrow's forecast
with ``WeatherClient`` (or any source you like) and pass it as ``Context.weather``.

The HTTP call is injectable: pass ``fetch=`` any callable ``(url, params) -> parsed JSON``. Results
are kept in a small in-process LRU cache with a time-to-live. Every failure returns an empty result;
nothing here raises on network trouble.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .facts import Weather

Fetcher = Callable[[str, Mapping[str, Any]], Any]

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def urllib_fetcher(timeout: float = 6.0, user_agent: str = "nudgewright") -> Fetcher:
    """A standard-library GET that returns parsed JSON."""

    def fetch(url: str, params: Mapping[str, Any]) -> Any:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        request = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": user_agent})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    return fetch


class TTLCache:
    """A tiny LRU cache whose entries also expire after ``ttl`` seconds."""

    def __init__(self, maxsize: int = 256, clock: Callable[[], float] = time.monotonic) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be at least 1")
        self.maxsize = maxsize
        self._clock = clock
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> tuple[bool, Any]:
        """``(hit, value)``; expired entries count as misses and are dropped."""
        entry = self._data.get(key)
        if entry is None:
            return False, None
        expires, value = entry
        if self._clock() >= expires:
            del self._data[key]
            return False, None
        self._data.move_to_end(key)
        return True, value

    def put(self, key: str, value: Any, ttl: float) -> Any:
        self._data[key] = (self._clock() + ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self.maxsize:
            self._data.popitem(last=False)
        return value

    def __len__(self) -> int:
        return len(self._data)


def classify(code: int) -> tuple[str, str]:
    """WMO weather code to ``(label, bucket)``; bucket is ``good``, ``dull`` or ``wet``."""
    if code == 0:
        return "clear", "good"
    if code in (1, 2, 3):
        return "partly cloudy", "good"
    if code in (45, 48):
        return "foggy", "dull"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rainy", "wet"
    if code in (71, 73, 75, 77, 85, 86):
        return "snowy", "wet"
    if code in (95, 96, 99):
        return "stormy", "wet"
    return "mixed", "dull"


@dataclass(frozen=True)
class DayForecast:
    day: str  # ISO date
    label: str
    bucket: str
    temp_max: float | None
    rain_chance: int | None

    def as_weather(self) -> Weather:
        return Weather(rain_chance=self.rain_chance, temp_max=self.temp_max, label=self.label)


def _at(values: Any, i: int) -> Any:
    return values[i] if isinstance(values, list) and i < len(values) else None


class WeatherClient:
    """Geocode a city and read its daily forecast, with caching."""

    def __init__(
        self,
        fetch: Fetcher | None = None,
        *,
        cache_size: int = 256,
        ttl: float = 3 * 3600,
        geocode_ttl: float = 30 * 24 * 3600,
        failure_ttl: float = 600,
        clock: Callable[[], float] = time.monotonic,
        geocode_url: str = GEOCODE_URL,
        forecast_url: str = FORECAST_URL,
    ) -> None:
        self._fetch = fetch or urllib_fetcher()
        self.cache = TTLCache(cache_size, clock)
        self.ttl, self.geocode_ttl, self.failure_ttl = ttl, geocode_ttl, failure_ttl
        self.geocode_url, self.forecast_url = geocode_url, forecast_url

    def geocode(self, city: str) -> tuple[float, float] | None:
        city = (city or "").strip()
        if not city:
            return None
        key = f"geo:{city.casefold()}"
        hit, value = self.cache.get(key)
        if hit:
            return value  # type: ignore[no-any-return]
        try:
            data = self._fetch(self.geocode_url, {"name": city, "count": 1})
            results = (data or {}).get("results") or []
            found = (float(results[0]["latitude"]), float(results[0]["longitude"])) if results else None
        except Exception:
            return self.cache.put(key, None, self.failure_ttl)  # type: ignore[no-any-return]
        return self.cache.put(key, found, self.geocode_ttl if found else self.failure_ttl)  # type: ignore[no-any-return]

    def forecast(self, city: str, days: int = 2) -> list[DayForecast]:
        """Daily forecast, today first. Empty on any failure."""
        days = max(1, min(int(days), 14))
        key = f"wx:{(city or '').strip().casefold()}:{days}"
        hit, value = self.cache.get(key)
        if hit:
            return value  # type: ignore[no-any-return]
        loc = self.geocode(city)
        if not loc:
            return []
        params = {
            "latitude": loc[0],
            "longitude": loc[1],
            "timezone": "auto",
            "forecast_days": days,
            "daily": "weather_code,temperature_2m_max,precipitation_probability_max",
        }
        try:
            daily = (self._fetch(self.forecast_url, params) or {}).get("daily") or {}
            out = []
            for i, day in enumerate(daily.get("time") or []):
                label, bucket = classify(int(_at(daily.get("weather_code"), i) or 0))
                temp, rain = (
                    _at(daily.get("temperature_2m_max"), i),
                    _at(daily.get("precipitation_probability_max"), i),
                )
                out.append(
                    DayForecast(
                        day=str(day),
                        label=label,
                        bucket=bucket,
                        temp_max=None if temp is None else float(temp),
                        rain_chance=None if rain is None else int(rain),
                    )
                )
        except Exception:
            return self.cache.put(key, [], self.failure_ttl)  # type: ignore[no-any-return]
        return self.cache.put(key, out, self.ttl)  # type: ignore[no-any-return]

    def tomorrow(self, city: str) -> Weather | None:
        """Tomorrow's forecast as a ``Weather``, or None."""
        days = self.forecast(city, days=2)
        return days[1].as_weather() if len(days) > 1 else None
