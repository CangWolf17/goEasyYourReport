from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._shared import emit_json, load_json, project_path


def clear_dir(path: Path) -> list[str]:
    if not path.exists():
        return []
    removed = []
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        removed.append(str(child))
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean recyclable project directories."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--temp", action="store_true")
    parser.add_argument("--logs", action="store_true")
    args = parser.parse_args()

    workflow = load_json(project_path(args.project_root, "workflow.json"))
    removed = []
    if args.temp:
        removed.extend(
            clear_dir(
                project_path(
                    args.project_root, workflow["paths"]["temp"].replace("./", "")
                )
            )
        )
    if args.logs:
        removed.extend(
            clear_dir(
                project_path(
                    args.project_root, workflow["paths"]["logs"].replace("./", "")
                )
            )
        )

    emit_json({"removed": removed})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
