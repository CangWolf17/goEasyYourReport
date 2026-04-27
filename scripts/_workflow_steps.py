from __future__ import annotations

from pathlib import Path

from scripts._shared import run_python_script


def run_script_step(script_path: Path, *args: str) -> dict[str, object]:
    return run_python_script(script_path, *args)
