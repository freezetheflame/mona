"""
Engine — Core monitor: spawns a process, watches output, fires triggers.
"""

from __future__ import annotations
import os
import signal
import subprocess
import sys
import time
from typing import Any, Optional

from mona.config import load_config
from mona.triggers import TriggerEngine, TriggerMatch
from mona.summarizer import Summarizer
from mona.outputs import create_output, PulseOutput, BufferOutput, BatchOutput, StdoutOutput


class Monitor:
    """Wrap a command and monitor its output."""

    def __init__(self, command: str, config_path: Optional[str] = None):
        self.command = command
        self.config = load_config(config_path)
        self.trigger_engine = TriggerEngine(self.config["triggers"])
        self.summarizer = Summarizer(self.config.get("summarizer", {}))
        self.output_handler, self.output_mode = create_output(self.config)
        self._process: Optional[subprocess.Popen] = None
        self._start_time: float = 0
        self._pulse_count: int = 0

    def run(self) -> int:
        """Run the command and monitor output. Returns exit code."""
        self._start_time = time.time()

        print(f"mona: Monitoring [{self.command}]", file=sys.stderr)
        print(f"mona: Output mode: {self.output_mode}", file=sys.stderr)

        self._process = subprocess.Popen(
            self.command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # line-buffered
            preexec_fn=lambda: signal.signal(signal.SIGPIPE, signal.SIG_DFL),
        )

        assert self._process.stdout is not None

        # Read output line by line
        try:
            for line in self._process.stdout:
                self._handle_line(line)
        except KeyboardInterrupt:
            self._terminate()
            return 130

        exit_code = self._process.wait()
        self._finalize(exit_code)
        return exit_code

    def _handle_line(self, line: str) -> None:
        """Process a single line of stdout."""
        # Feed to summarizer
        self.summarizer.feed(line)

        # Passthrough to stdout unless in buffer/batch mode
        if self.output_mode == "stdout":
            print(line, end="", flush=True)
        elif isinstance(self.output_handler, BufferOutput):
            self.output_handler.write(line)
        elif isinstance(self.output_handler, StdoutOutput):
            print(line, end="", flush=True)

        # Check triggers
        match = self.trigger_engine.evaluate(line)
        if match:
            self._fire_trigger(match, line)

        # Batch mode: periodic summary
        if isinstance(self.output_handler, BatchOutput):
            summary = self.summarizer.summary()
            self.output_handler.tick(summary)

    def _fire_trigger(self, match: TriggerMatch, line: str) -> None:
        """Handle a trigger match by creating a pulse event."""
        self._pulse_count += 1
        elapsed = time.time() - self._start_time

        event = {
            "event": "trigger",
            "type": match.trigger_type,
            "name": match.trigger_name,
            "match": match.matched_text,
            "summary": self.summarizer.summary(),
            "context_lines": self.summarizer.get_context(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "elapsed_seconds": round(elapsed, 1),
            "pulse_number": self._pulse_count,
        }

        if isinstance(self.output_handler, PulseOutput):
            path = self.output_handler.emit(event)
            print(
                f"\nmona: ⚡ pulse #{self._pulse_count} [{match.trigger_type}] "
                f"→ {path}",
                file=sys.stderr,
            )
        else:
            # Print pulse info to stderr even in other modes
            print(
                f"\nmona: ⚡ trigger [{match.trigger_type}] "
                f"\"{match.matched_text}\"",
                file=sys.stderr,
            )

    def _terminate(self) -> None:
        """Gracefully terminate the process."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def _finalize(self, exit_code: int) -> None:
        """Emit final summary."""
        elapsed = time.time() - self._start_time
        summary = self.summarizer.summary()

        event = {
            "event": "complete",
            "exit_code": exit_code,
            "summary": summary,
            "total_pulses": self._pulse_count,
            "elapsed_seconds": round(elapsed, 1),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        if isinstance(self.output_handler, PulseOutput):
            path = self.output_handler.emit(event)
            print(f"\nmona: ✅ Done (exit={exit_code}) → {path}", file=sys.stderr)
        else:
            print(f"\nmona: ✅ Done (exit={exit_code}) {summary}", file=sys.stderr)
