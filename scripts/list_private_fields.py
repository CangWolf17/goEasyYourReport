from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._shared import dump_json, emit_json, load_json, project_path


def resolve_private_source(args: argparse.Namespace) -> Path | None:
    raw = args.source or os.getenv("REPORT_PRIVATE_SOURCE")
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def compute_availability(
    fields: list[dict[str, object]], secret_payload: dict[str, object]
) -> dict[str, str]:
    availability: dict[str, str] = {}
    for field in fields:
        name = str(field["name"])
        source = field.get("source")
        if source == "system_date":
            availability[name] = "computed"
        elif name in secret_payload:
            availability[name] = "present"
        else:
            availability[name] = (
                "missing" if field.get("required", False) else "optional"
            )
    return availability


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List private field names and availability without revealing values."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--binding", default="config/field.binding.json")
    parser.add_argument(
        "--source",
        help="Path to a private JSON file outside the agent-visible project.",
    )
    parser.add_argument(
        "--write-back",
        action="store_true",
        help="Write computed availability back to the binding file.",
    )
    args = parser.parse_args()

    binding_path = project_path(args.project_root, args.binding)
    binding = load_json(binding_path)

    source_path = resolve_private_source(args)
    secret_payload: dict[str, object] = {}
    if source_path and source_path.exists():
        secret_payload = json.loads(source_path.read_text(encoding="utf-8"))

    fields = binding.get("fields", [])
    availability = compute_availability(fields, secret_payload)
    result = {
        "fields": [field["name"] for field in fields],
        "availability": availability,
    }

    if args.write_back:
        binding["availability"] = availability
        dump_json(binding_path, binding)

    emit_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
