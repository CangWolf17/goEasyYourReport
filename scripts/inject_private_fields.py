from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._shared import emit_json, import_docx, load_json, project_path


def load_private_values(source: str | None) -> dict[str, str]:
    raw = source or os.getenv("REPORT_PRIVATE_SOURCE")
    if not raw:
        return {}
    source_path = Path(raw).expanduser().resolve()
    if not source_path.exists():
        return {}
    return json.loads(source_path.read_text(encoding="utf-8"))


def build_field_values(
    binding: dict[str, object], private_values: dict[str, str]
) -> dict[str, str]:
    values: dict[str, str] = {}
    fields = binding.get("fields", [])
    if not isinstance(fields, list):
        return values
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = field["name"]
        if field.get("source") == "system_date":
            fmt = field.get("format", "%Y-%m-%d")
            values[name] = datetime.now().strftime(fmt)
        elif name in private_values:
            values[name] = str(private_values[name])
    return values


def replace_after_label(text: str, label: str, replacement: str) -> str:
    if label not in text:
        return text
    prefix, _, _ = text.partition(label)
    return f"{prefix}{label}{replacement}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inject private values into a redacted DOCX output."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--binding", default="config/field.binding.json")
    parser.add_argument("--input", default="out/redacted.docx")
    parser.add_argument("--output", default="out/private.docx")
    parser.add_argument(
        "--source", help="Path to a private JSON source outside the project."
    )
    args = parser.parse_args()

    binding = load_json(project_path(args.project_root, args.binding))
    input_path = project_path(args.project_root, args.input)
    output_path = project_path(args.project_root, args.output)
    if not input_path.exists():
        raise SystemExit(f"Redacted input not found: {input_path}")

    private_values = load_private_values(args.source)
    values = build_field_values(binding, private_values)
    shutil.copy2(input_path, output_path)

    docx = import_docx()
    doc = docx.Document(output_path)
    resolved = []
    missing = []
    for bind in binding.get("bindings", []):
        field = bind["field"]
        anchor = bind.get("anchor_text", "")
        value = values.get(field)
        if not value:
            missing.append(field)
            continue
        updated = False
        for paragraph in doc.paragraphs:
            if anchor and anchor in paragraph.text:
                paragraph.text = replace_after_label(paragraph.text, anchor, value)
                updated = True
                resolved.append(field)
                break
        if not updated:
            missing.append(field)
    doc.save(output_path)

    emit_json(
        {
            "private_output": str(output_path),
            "resolved": resolved,
            "missing": missing,
        }
    )
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
