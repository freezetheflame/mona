"""
Outputs — Multiple output strategies for Mona.

Modes:
  pulse  : Write a signal file + optional tool call (for Agent consumption)
  buffer : Append to a growing log file (Agent polls on demand)
  batch  : Periodically emit a collapsed summary
  stdout : Passthrough raw output
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any, Optional


class PulseOutput:
    """Write pulse signal files for Agent consumption.

    Each pulse is a JSON file in pulse_dir with a structured event.
    The Agent can watch this directory for new files, or Mona can
    trigger an immediate tool call (future).
    """

    def __init__(self, pulse_dir: str):
        self.pulse_dir = Path(pulse_dir)
        self.pulse_dir.mkdir(parents=True, exist_ok=True)

    def emit(self, event: dict[str, Any]) -> str:
        """Write a pulse signal file. Returns the file path."""
        ts = time.strftime("%Y%m%d-%H%M%S")
        filename = f"pulse-{ts}-{event.get('type', 'event')}.json"
        filepath = self.pulse_dir / filename
        with open(filepath, "w") as f:
            json.dump(event, f, indent=2, default=str)
        return str(filepath)

    def clean(self, max_age_hours: int = 24) -> int:
        """Remove old pulse files. Returns count removed."""
        now = time.time()
        removed = 0
        for f in self.pulse_dir.glob("pulse-*.json"):
            if now - f.stat().st_mtime > max_age_hours * 3600:
                f.unlink()
                removed += 1
        return removed


class BufferOutput:
    """Append output to a rolling file. Agent reads on demand."""

    def __init__(self, buffer_file: str, max_size: int = 1024 * 100):
        self.buffer_file = Path(buffer_file)
        self.max_size = max_size
        self.buffer_file.parent.mkdir(parents=True, exist_ok=True)

    def write(self, text: str) -> None:
        with open(self.buffer_file, "a") as f:
            f.write(text)
        self._trim()

    def _trim(self) -> None:
        """Trim buffer if it exceeds max_size."""
        if self.buffer_file.stat().st_size > self.max_size:
            with open(self.buffer_file) as f:
                content = f.read()
            # Keep the last half
            half = self.max_size // 2
            with open(self.buffer_file, "w") as f:
                f.write(content[-half:])

    def read(self) -> str:
        if self.buffer_file.exists():
            return self.buffer_file.read_text()
        return ""


class BatchOutput:
    """Periodically emit collapsed summary via callback."""

    def __init__(self, interval: int = 60, callback: Optional[callable] = None):
        self.interval = interval
        self.callback = callback
        self._last_emit: float = 0

    def tick(self, summary: str, force: bool = False) -> Optional[str]:
        """Return summary string if it's time to emit."""
        now = time.time()
        if force or (now - self._last_emit >= self.interval):
            self._last_emit = now
            if self.callback:
                self.callback(summary)
            return summary
        return None


class StdoutOutput:
    """Passthrough output to stdout."""

    @staticmethod
    def write(text: str) -> None:
        print(text, end="", flush=True)


def create_output(config: dict[str, Any]) -> tuple[Any, str]:
    """Factory: create output handler based on config."""
    mode = config.get("output", {}).get("mode", "pulse")
    if mode == "pulse":
        pulse_dir = config.get("output", {}).get(
            "pulse_dir", str(Path.home() / ".mona" / "pulses")
        )
        return PulseOutput(pulse_dir), mode
    elif mode == "buffer":
        buffer_file = config.get("output", {}).get("buffer_file", "/tmp/mona-last-output.txt")
        return BufferOutput(buffer_file), mode
    elif mode == "batch":
        interval = config.get("output", {}).get("batch_interval", 60)
        return BatchOutput(interval=interval), mode
    else:
        return StdoutOutput(), mode
