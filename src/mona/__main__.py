"""
__main__ — CLI entry point: `mona run "command"` or `python -m mona run "command"`.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Any

from mona.version import __version__


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mona",
        description="Mona — AI Agent Monitor: 事件驱动的智能命令监控器",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # `mona run`
    run_p = sub.add_parser("run", help="Run a command under monitoring")
    run_p.add_argument("command", help="Command to run and monitor")
    run_p.add_argument("--config", "-c", help="Path to config file (default: mona.yaml)")
    run_p.add_argument(
        "--mode",
        choices=["pulse", "buffer", "batch", "stdout"],
        help="Output mode (overrides config)",
    )

    # `mona version`
    sub.add_parser("version", help="Show version")

    args = parser.parse_args()

    if args.command == "version":
        print(f"mona v{__version__}")
        return

    if args.command == "run":
        _run(args)


def _run(args: argparse.Namespace) -> None:
    """Execute the run command."""
    from mona.engine import Monitor

    monitor = Monitor(args.command, config_path=args.config)

    # Override output mode if specified on CLI
    if args.mode:
        from mona.config import load_config
        from mona.outputs import create_output
        cfg = load_config(args.config)
        cfg["output"]["mode"] = args.mode
        new_output, new_mode = create_output(cfg)
        monitor.output_handler = new_output
        monitor.output_mode = new_mode

    try:
        exit_code = monitor.run()
    except KeyboardInterrupt:
        exit_code = 130

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
