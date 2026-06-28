"""
Config — Load and validate mona.yaml configuration.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


DEFAULT_CONFIG: dict[str, Any] = {
    "triggers": {
        "urgent": [
            {"pattern": "ERROR|FATAL|CRASH|Exception|Traceback|segfault", "action": "pulse"},
            {"pattern": "BUILD FAILED|TEST FAILED|FAILED", "action": "pulse"},
        ],
        "milestone": [
            {"pattern": "BUILD SUCCESS|SUCCESS|All tests passed|100%", "action": "pulse"},
            {"pattern": "Deployment complete|Upload complete", "action": "pulse"},
        ],
        "progress": [
            {"pattern": r"^(\d+)/(\d+)", "action": "pulse", "interval": 30},
        ],
    },
    "output": {
        "mode": "pulse",
        "pulse_dir": str(Path.home() / ".mona" / "pulses"),
        "buffer_file": "/tmp/mona-last-output.txt",
        "batch_interval": 60,
    },
    "summarizer": {
        "deduplicate": True,
        "fold_progress_bars": True,
        "max_context_lines": 10,
    },
}


def load_config(path: Optional[str] = None) -> dict[str, Any]:
    """Load config from YAML file, merging with defaults."""
    config = DEFAULT_CONFIG.copy()

    if path is None:
        # Search default locations
        candidates = [
            "mona.yaml",
            "mona.yml",
            os.path.expanduser("~/.mona/config.yaml"),
            os.path.expanduser("~/.mona/config.yml"),
        ]
        for c in candidates:
            if os.path.exists(c):
                path = c
                break

    if path and os.path.exists(path):
        with open(path) as f:
            if yaml is None:
                raise ImportError("PyYAML is required. pip install pyyaml")
            user_config = yaml.safe_load(f) or {}
            _deep_merge(config, user_config)

    return config


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override into base."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
