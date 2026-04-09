from __future__ import annotations

import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
RELATIONSHIP_TAG = f"{{{PACKAGE_REL_NS}}}Relationship"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
STYLE_REFERENCE_ATTRIBUTES = ("basedOn", "next", "link")
XMLNS_DECLARATION_PATTERN = re.compile(
    rb"""\sxmlns(?::(?P<prefix>[A-Za-z_][\w.\-]*))?=(?P<quote>["']).*?(?P=quote)"""
)


def qn(local_name: str) -> str:
    return f"{{{W_NS}}}{local_name}"


def _attribute_value(element: ET.Element, local_name: str) -> str | None:
    return element.get(qn(local_name)) or element.get(local_name)


def _style_id(style_element: ET.Element) -> str | None:
    return _attribute_value(style_element, "styleId")


def _validate_style_references(
    part: str, root: ET.Element, errors: list[dict[str, str]]
) -> None:
    if part != "word/styles.xml":
        return

    style_ids = {
        style_id
        for style in root.findall(qn("style"))
        for style_id in [_style_id(style)]
        if style_id
    }

    for style in root.findall(qn("style")):
        style_id = _style_id(style)
        if not style_id:
            continue
        for attribute in STYLE_REFERENCE_ATTRIBUTES:
            dependency = style.find(qn(attribute))
            if dependency is None:
                continue
            target = _attribute_value(dependency, "val")
            if not target or target in style_ids:
                continue
            errors.append(
                {
                    "kind": "missing_style_reference",
                    "part": part,
                    "style_id": style_id,
                    "attribute": attribute,
                    "target": target,
                }
            )


def _declared_prefixes(xml_bytes: bytes) -> set[str]:
    prefixes = set()
    for match in XMLNS_DECLARATION_PATTERN.finditer(xml_bytes):
        prefix = match.group("prefix")
        prefixes.add("" if prefix is None else prefix.decode("utf-8"))
    return prefixes


def _validate_markup_compatibility(
    part: str,
    root: ET.Element,
    xml_bytes: bytes,
    errors: list[dict[str, str]],
) -> None:
    ignorable = root.get(f"{{{MC_NS}}}Ignorable")
    if not ignorable:
        return

    declared_prefixes = _declared_prefixes(xml_bytes)
    for prefix in ignorable.split():
        if prefix in declared_prefixes:
            continue
        errors.append(
            {
                "kind": "undefined_ignorable_prefix",
                "part": part,
                "prefix": prefix,
            }
        )


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
        xml_bytes_by_part: dict[str, bytes] = {}

        if "[Content_Types].xml" not in part_set:
            errors.append({"kind": "missing_part", "part": "[Content_Types].xml"})

        for part in parts:
            if not (part.endswith(".xml") or part.endswith(".rels")):
                continue
            try:
                xml_bytes = docx_zip.read(part)
                xml_roots[part] = ET.fromstring(xml_bytes)
                xml_bytes_by_part[part] = xml_bytes
            except ET.ParseError as exc:
                errors.append(
                    {
                        "kind": "invalid_xml",
                        "part": part,
                        "details": str(exc),
                    }
                )

        for part, root in xml_roots.items():
            _validate_markup_compatibility(part, root, xml_bytes_by_part[part], errors)
            _validate_style_references(part, root, errors)

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
