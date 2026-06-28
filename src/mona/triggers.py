"""
Triggers — Pattern matching engine for output monitoring.
"""

from __future__ import annotations
import re
import time
from typing import Any, Optional


class TriggerMatch:
    """Result of a trigger evaluation."""

    def __init__(
        self,
        trigger_type: str,
        trigger_name: str,
        pattern: str,
        matched_text: str,
        groups: tuple[str, ...],
        action: str,
    ):
        self.trigger_type = trigger_type
        self.trigger_name = trigger_name
        self.pattern = pattern
        self.matched_text = matched_text
        self.groups = groups
        self.action = action

    def to_dict(self) -> dict:
        return {
            "type": self.trigger_type,
            "name": self.trigger_name,
            "pattern": self.pattern,
            "match": self.matched_text,
            "action": self.action,
        }


class TriggerEngine:
    """Manages trigger rules and evaluates lines against them."""

    def __init__(self, trigger_config: dict[str, Any]):
        self.rules: list[_Rule] = []
        self._rate_limits: dict[str, float] = {}

        for trigger_type, triggers in trigger_config.items():
            for i, t in enumerate(triggers):
                name = t.get("name", f"{trigger_type}_{i}")
                interval = t.get("interval", 0)
                self.rules.append(
                    _Rule(
                        name=name,
                        trigger_type=trigger_type,
                        pattern=t["pattern"],
                        action=t.get("action", "pulse"),
                        interval=interval,
                    )
                )

    def evaluate(self, line: str) -> Optional[TriggerMatch]:
        """Check a single line against all trigger rules."""
        for rule in self.rules:
            # Rate limiting
            if rule.interval > 0:
                last = self._rate_limits.get(rule.name, 0)
                if time.time() - last < rule.interval:
                    continue

            m = re.search(rule.pattern, line)
            if m:
                self._rate_limits[rule.name] = time.time()
                return TriggerMatch(
                    trigger_type=rule.trigger_type,
                    trigger_name=rule.name,
                    pattern=rule.pattern,
                    matched_text=m.group(0),
                    groups=m.groups(),
                    action=rule.action,
                )
        return None


class _Rule:
    """Internal trigger rule."""

    def __init__(
        self,
        name: str,
        trigger_type: str,
        pattern: str,
        action: str,
        interval: int = 0,
    ):
        self.name = name
        self.trigger_type = trigger_type
        self.pattern = pattern
        self.action = action
        self.interval = interval
