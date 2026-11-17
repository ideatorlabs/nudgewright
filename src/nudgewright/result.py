"""The composer's output: the line plus the reasons behind it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Reason:
    """A signal that was used or skipped, and why."""

    key: str
    label: str
    kind: str
    mode: str
    reason: str = ""

    def as_dict(self) -> dict[str, str]:
        out = {"key": self.key, "label": self.label, "kind": self.kind, "mode": self.mode}
        if self.reason:
            out["reason"] = self.reason
        return out


@dataclass(frozen=True)
class Finding:
    """Something the guardrail check changed or rejected."""

    rule: str
    detail: str
    action: str  # "adjusted" (line kept, cleaned or trimmed) or "replaced" (safe line used)

    def as_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "detail": self.detail, "action": self.action}


@dataclass(frozen=True)
class Composed:
    """One customer's line and its explanation.

    ``line`` is empty when the goal is not one the composer writes for; ``note`` then says why.
    """

    customer_id: str
    goal: str
    line: str
    level: str = "L0"
    used: tuple[Reason, ...] = ()
    skipped: tuple[Reason, ...] = ()
    guardrails: tuple[Finding, ...] = ()
    note: str = ""

    def why(self) -> dict[str, Any]:
        """A JSON-serialisable explanation of this line."""
        return {
            "customer_id": self.customer_id,
            "goal": self.goal,
            "line": self.line,
            "level": self.level,
            "used": [r.as_dict() for r in self.used],
            "skipped": [r.as_dict() for r in self.skipped],
            "guardrails": [g.as_dict() for g in self.guardrails],
            "note": self.note,
        }

    def summary(self) -> str:
        """One human-readable sentence: what was used, then what was skipped and why."""
        if self.note and not self.line:
            return self.note
        used = " · ".join(r.label for r in self.used) or "nothing specific"
        text = f"Used: {used}"
        if self.skipped:
            text += ". Skipped: " + " · ".join(f"{r.label} ({r.reason})" for r in self.skipped)
        if self.guardrails:
            text += ". Guardrails: " + " · ".join(f"{g.rule} ({g.detail})" for g in self.guardrails)
        return text + "."
