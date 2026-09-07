#!/usr/bin/env python3
"""Repository CLI. Bootstrap ships the standalone backend implementation."""
from pathlib import Path
import runpy

runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "backend/sandbox/browser_runtime_repair.py"),
    run_name="__main__",
)
