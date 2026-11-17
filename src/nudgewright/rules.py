"""Tunable thresholds. Guardrails themselves are not switchable; these only set their limits."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_SENSITIVE_SECTORS: frozenset[str] = frozenset(
    {"clinic", "dental", "pharmacy", "hospital", "diagnostics", "therapy", "medical"}
)


@dataclass(frozen=True)
class Rules:
    """Limits and windows the composer works within."""

    max_signals: int = 3  # slots in the words: why now, why this person, what to offer
    max_length: int = 160  # characters, including the trailing ellipsis when trimmed
    sensitive_sectors: frozenset[str] = DEFAULT_SENSITIVE_SECTORS
    birthday_window_days: int = 7
    festival_window_days: int = 3
    festival_goal_window_days: int = 14  # a festival campaign is often sent well ahead
    campaign_festival_max_days: int = 60
    event_window_days: int = 3
    anniversary_window_days: int = 7
    rain_chance_min: int = 60
    heat_temp_min: float = 38.0
    recent_bills: int = 3
    usual_order_min_bills: int = 2
    favourite_category_min_items: int = 3
    near_tier_points: int = 20
    near_tier_share: float = 0.15
    item_name_max: int = 60

    def __post_init__(self) -> None:
        if not 1 <= self.max_signals <= 3:
            raise ValueError("max_signals must be 1, 2 or 3")
        if self.max_length < 20:
            raise ValueError("max_length must be at least 20")
        object.__setattr__(self, "sensitive_sectors", frozenset(s.casefold() for s in self.sensitive_sectors))

    def is_sensitive(self, sector: str) -> bool:
        return sector.strip().casefold() in self.sensitive_sectors


DEFAULT_RULES = Rules()
