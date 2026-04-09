from __future__ import annotations

import posixpath
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
RELATIONSHIP_TAG = f"{{{PACKAGE_REL_NS}}}Relationship"


def _source_part_for_relationships(rels_part: str) -> str | None:
    if rels_part == "_rels/.rels":
        return None

    rels_path = PurePosixPath(rels_part)
    source_name = rels_path.name.removesuffix(".rels")
    parent = rels_path.parent
    if parent.name == "_rels":
        parent = parent.parent
    if parent == PurePosixPath("."):
        return source_name
    return (parent / source_name).as_posix()


def _resolve_relationship_target(rels_part: str, target: str) -> str:
    if target.startswith("/"):
        return posixpath.normpath(target.lstrip("/"))

    source_part = _source_part_for_relationships(rels_part)
    base_dir = "" if source_part is None else posixpath.dirname(source_part)
    return posixpath.normpath(posixpath.join(base_dir, target))


def validate_docx_package(docx_path: Path) -> dict[str, object]:
    errors: list[dict[str, str]] = []
    parts: list[str] = []

    with zipfile.ZipFile(docx_path, "r") as docx_zip:
        parts = sorted(info.filename for info in docx_zip.infolist())
        part_set = set(parts)
        xml_roots: dict[str, ET.Element] = {}

        if "[Content_Types].xml" not in part_set:
            errors.append({"kind": "missing_part", "part": "[Content_Types].xml"})

        for part in parts:
            if not (part.endswith(".xml") or part.endswith(".rels")):
                continue
            try:
                xml_roots[part] = ET.fromstring(docx_zip.read(part))
            except ET.ParseError as exc:
                errors.append(
                    {
                        "kind": "invalid_xml",
                        "part": part,
                        "details": str(exc),
                    }
                )

        for part, root in xml_roots.items():
            if not part.endswith(".rels"):
                continue
            for relationship in root.findall(RELATIONSHIP_TAG):
                if relationship.get("TargetMode") == "External":
                    continue
                target = relationship.get("Target")
                if not target or target.startswith("#"):
                    continue
                resolved_target = _resolve_relationship_target(part, target)
                if not resolved_target or resolved_target.startswith("../"):
                    errors.append(
                        {
                            "kind": "missing_relationship_target",
                            "source": part,
                            "target": target,
                        }
                    )
                    continue
                if resolved_target not in part_set:
                    errors.append(
                        {
                            "kind": "missing_relationship_target",
                            "source": part,
                            "target": target,
                        }
                    )

    return {
        "ok": not errors,
        "errors": errors,
        "parts": parts,
    }


def assert_docx_package_ok(docx_path: Path) -> None:
    report = validate_docx_package(docx_path)
    if not report["ok"]:
        raise ValueError(report["errors"])
