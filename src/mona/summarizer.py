"""
Summarizer — Smart line dedup, progress folding, and context extraction.
"""

from __future__ import annotations
import re
from typing import Any


class Summarizer:
    """Collapses noisy output into structured summaries."""

    def __init__(self, config: dict[str, Any]):
        self.deduplicate = config.get("deduplicate", True)
        self.fold_progress_bars = config.get("fold_progress_bars", True)
        self.max_context_lines = config.get("max_context_lines", 10)

        self._recent_lines: list[str] = []
        self._line_counts: dict[str, int] = {}
        self._last_line: str = ""
        self._phase: str = "starting"
        self._progress: dict[str, Any] = {}

    def feed(self, line: str) -> None:
        """Process a single line of output."""
        line = line.rstrip("\n\r")
        if not line:
            return

        # Deduplicate consecutive identical lines
        if self.deduplicate and line == self._last_line:
            self._line_counts[line] = self._line_counts.get(line, 1) + 1
            return

        # Track line frequency (for final summary)
        if line != self._last_line:
            self._line_counts[self._last_line] = 0  # reset old
        self._line_counts[line] = self._line_counts.get(line, 0) + 1
        self._last_line = line

        # Detect phase changes
        self._detect_phase(line)

        # Track progress
        self._track_progress(line)

        # Keep recent lines for context
        self._recent_lines.append(line)
        if len(self._recent_lines) > self.max_context_lines * 2:
            self._recent_lines = self._recent_lines[-self.max_context_lines :]

    def _detect_phase(self, line: str) -> None:
        """Try to detect what phase the process is in."""
        lower = line.lower()
        for keyword, phase in [
            ("compil", "compiling"),
            ("build", "building"),
            ("test", "testing"),
            ("lint", "linting"),
            ("deploy", "deploying"),
            ("install", "installing"),
            ("download", "downloading"),
            ("linking", "linking"),
            ("generat", "generating"),
        ]:
            if keyword in lower:
                self._phase = phase
                break

    def _track_progress(self, line: str) -> None:
        """Try to extract progress from lines like '3/10' or '30%'."""
        # Match patterns like "3/10" or "30%"
        m = re.search(r"(\d+)\s*/\s*(\d+)", line)
        if m:
            self._progress = {"current": int(m.group(1)), "total": int(m.group(2))}

        m = re.search(r"(\d+)%\s*(?:complete|done|finished)?", line)
        if m:
            pct = int(m.group(1))
            if self._progress:
                self._progress["percent"] = pct
            else:
                self._progress = {"percent": pct, "current": pct, "total": 100}

    def get_context(self, extra_lines: list[str] | None = None) -> list[str]:
        """Get the most relevant context lines."""
        ctx: list[str] = []
        if self._recent_lines:
            # Show the last few unique lines before the trigger
            seen: set[str] = set()
            for line in reversed(self._recent_lines[-6:]):
                if line not in seen:
                    ctx.insert(0, line)
                    seen.add(line)
        if extra_lines:
            ctx.extend(extra_lines)
        return ctx

    def summary(self) -> str:
        """Generate a concise summary of the output so far."""
        parts: list[str] = []

        if self._phase:
            parts.append(f"阶段: {self._phase}")

        if self._progress:
            cur = self._progress.get("current", 0)
            total = self._progress.get("total", 0)
            pct = self._progress.get("percent")
            if total > 0:
                pct = pct or int(cur / total * 100)
                parts.append(f"进度: {cur}/{total} ({pct}%)")

        # Count errors/warnings
        error_count = sum(1 for l in self._recent_lines if "error" in l.lower())
        warn_count = sum(1 for l in self._recent_lines if "warning" in l.lower())
        if error_count:
            parts.append(f"错误: {error_count}")
        if warn_count:
            parts.append(f"警告: {warn_count}")

        return " | ".join(parts) if parts else "运行中..."

    def repeated_lines(self) -> list[tuple[str, int]]:
        """Return lines that appeared multiple times."""
        return [(l, c) for l, c in self._line_counts.items() if c > 1]
