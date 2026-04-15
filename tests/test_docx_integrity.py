from __future__ import annotations

import contextlib
import importlib
import io
import json
import re
import shutil
import subprocess
import sys
import unittest
import uuid
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest import mock

from scripts._docx_integrity import validate_docx_package


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(r"D:\Miniconda\python.exe")
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def qn(local_name: str) -> str:
    return f"{{{W_NS}}}{local_name}"


def rewrite_docx(path: Path, mutator) -> None:
    with zipfile.ZipFile(path, "r") as source_zip:
        entries = {
            info.filename: source_zip.read(info.filename)
            for info in source_zip.infolist()
        }

    mutator(entries)

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as output_zip:
        for filename, content in entries.items():
            output_zip.writestr(filename, content)


class DocxIntegrityTests(unittest.TestCase):
    def create_project(self) -> Path:
        sandbox_root = PROJECT_ROOT / "temp" / "docx-integrity-tests"
        sandbox_root.mkdir(parents=True, exist_ok=True)
        project_root = sandbox_root / uuid.uuid4().hex
        project_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(project_root, ignore_errors=True))
        result = subprocess.run(
            [
                str(PYTHON),
                str(PROJECT_ROOT / "scripts" / "init_project.py"),
                "--project-root",
                str(project_root),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return project_root

    def copy_docx(self, source: Path, name: str) -> Path:
        target = source.parent / name
        shutil.copy2(source, target)
        return target

    def test_validate_docx_package_rejects_invalid_xml_part(self) -> None:
        project_root = self.create_project()
        docx_path = self.copy_docx(
            project_root / "templates" / "template.user.docx",
            "invalid-xml.docx",
        )

        def break_styles(entries: dict[str, bytes]) -> None:
            entries["word/styles.xml"] = b"<w:styles>"

        rewrite_docx(docx_path, break_styles)

        report = validate_docx_package(docx_path)

        self.assertFalse(report["ok"])
        self.assertTrue(
            any(
                error["kind"] == "invalid_xml"
                and error["part"] == "word/styles.xml"
                for error in report["errors"]
            )
        )

    def test_validate_docx_package_rejects_missing_relationship_target(self) -> None:
        project_root = self.create_project()
        docx_path = self.copy_docx(
            project_root / "templates" / "template.user.docx",
            "missing-target.docx",
        )

        def add_missing_relationship(entries: dict[str, bytes]) -> None:
            rels_root = ET.fromstring(entries["word/_rels/document.xml.rels"])
            relationship = ET.SubElement(
                rels_root,
                f"{{{PACKAGE_REL_NS}}}Relationship",
            )
            relationship.set("Id", "rId999")
            relationship.set(
                "Type",
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
            )
            relationship.set("Target", "media/image999.png")
            entries["word/_rels/document.xml.rels"] = ET.tostring(
                rels_root,
                encoding="utf-8",
                xml_declaration=True,
            )

        rewrite_docx(docx_path, add_missing_relationship)

        report = validate_docx_package(docx_path)

        self.assertFalse(report["ok"])
        self.assertTrue(
            any(
                error["kind"] == "missing_relationship_target"
                and error["source"] == "word/_rels/document.xml.rels"
                and error["target"] == "media/image999.png"
                for error in report["errors"]
            )
        )

    def test_validate_docx_package_requires_content_types_part(self) -> None:
        project_root = self.create_project()
        docx_path = self.copy_docx(
            project_root / "templates" / "template.user.docx",
            "missing-content-types.docx",
        )

        def drop_content_types(entries: dict[str, bytes]) -> None:
            entries.pop("[Content_Types].xml", None)

        rewrite_docx(docx_path, drop_content_types)

        report = validate_docx_package(docx_path)

        self.assertFalse(report["ok"])
        self.assertIn(
            {"kind": "missing_part", "part": "[Content_Types].xml"},
            report["errors"],
        )

    def test_validate_docx_package_rejects_missing_style_dependency_target(self) -> None:
        project_root = self.create_project()
        docx_path = self.copy_docx(
            project_root / "templates" / "template.user.docx",
            "missing-style-dependency.docx",
        )

        def break_style_dependency(entries: dict[str, bytes]) -> None:
            styles_root = ET.fromstring(entries["word/styles.xml"])
            for style in styles_root.findall(qn("style")):
                name = style.find(qn("name"))
                if name is None or name.get(qn("val")) != "题目":
                    continue
                based_on = style.find(qn("basedOn"))
                if based_on is None:
                    based_on = ET.SubElement(style, qn("basedOn"))
                based_on.set(qn("val"), "missing-normal-style")
                break
            entries["word/styles.xml"] = ET.tostring(
                styles_root,
                encoding="utf-8",
                xml_declaration=True,
            )

        rewrite_docx(docx_path, break_style_dependency)

        report = validate_docx_package(docx_path)

        self.assertFalse(report["ok"])
        self.assertIn(
            {
                "kind": "missing_style_reference",
                "part": "word/styles.xml",
                "style_id": "题目",
                "attribute": "basedOn",
                "target": "missing-normal-style",
            },
            report["errors"],
        )

    def test_validate_docx_package_rejects_undefined_ignorable_prefix(self) -> None:
        project_root = self.create_project()
        docx_path = self.copy_docx(
            project_root / "templates" / "template.user.docx",
            "undefined-ignorable-prefix.docx",
        )

        def break_ignorable_prefix(entries: dict[str, bytes]) -> None:
            styles_xml = entries["word/styles.xml"].decode("utf-8")
            styles_xml, replacements = re.subn(
                r'Ignorable="([^"]+)"',
                lambda match: f'Ignorable="{match.group(1)} w99"',
                styles_xml,
                count=1,
            )
            self.assertEqual(replacements, 1)
            entries["word/styles.xml"] = styles_xml.encode("utf-8")

        rewrite_docx(docx_path, break_ignorable_prefix)

        report = validate_docx_package(docx_path)

        self.assertFalse(report["ok"])
        self.assertIn(
            {
                "kind": "undefined_ignorable_prefix",
                "part": "word/styles.xml",
                "prefix": "w99",
            },
            report["errors"],
        )

    def test_validate_docx_package_accepts_clean_repo_generated_docx(self) -> None:
        project_root = self.create_project()
        docx_path = project_root / "templates" / "template.user.docx"

        report = validate_docx_package(docx_path)

        self.assertTrue(report["ok"])
        self.assertEqual(report["errors"], [])

    def test_build_report_runs_docx_integrity_gate(self) -> None:
        project_root = self.create_project()
        failure_report = {
            "ok": False,
            "errors": [
                {
                    "kind": "missing_relationship_target",
                    "source": "word/_rels/document.xml.rels",
                    "target": "media/image9.png",
                }
            ],
            "parts": [],
        }

        build_report = importlib.import_module("scripts.build_report")
        self.addCleanup(importlib.reload, build_report)
        with mock.patch(
            "scripts._docx_integrity.validate_docx_package",
            return_value=failure_report,
        ) as mock_validate:
            build_report = importlib.reload(build_report)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout), mock.patch.object(
                sys,
                "argv",
                ["build_report.py", "--project-root", str(project_root)],
            ):
                exit_code = build_report.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 2)
        mock_validate.assert_called_once_with(project_root / "out" / "redacted.docx")
        self.assertEqual(payload["redacted"], str(project_root / "out" / "redacted.docx"))
        self.assertEqual(payload["integrity"], failure_report)

    def test_render_and_preview_import_shared_docx_xml_helpers(self) -> None:
        shared_docx_xml = importlib.import_module("scripts._docx_xml")
        report_render = importlib.import_module("scripts._report_render")
        build_preview = importlib.import_module("scripts.build_preview")

        self.assertIs(report_render.clear_paragraph, shared_docx_xml.clear_paragraph)
        self.assertIs(
            report_render.insert_paragraph_after,
            shared_docx_xml.insert_paragraph_after,
        )
        self.assertIs(
            report_render.insert_paragraph_before,
            shared_docx_xml.insert_paragraph_before,
        )
        self.assertIs(report_render.word_qn, shared_docx_xml.word_qn)
        self.assertIs(build_preview.clear_paragraph, shared_docx_xml.clear_paragraph)
        self.assertIs(
            build_preview.insert_paragraph_after,
            shared_docx_xml.insert_paragraph_after,
        )
        self.assertIs(
            build_preview.insert_paragraph_before,
            shared_docx_xml.insert_paragraph_before,
        )

    def test_repo_generated_preview_docx_passes_integrity_gate(self) -> None:
        project_root = self.create_project()
        result = subprocess.run(
            [
                str(PYTHON),
                str(project_root / "scripts" / "build_preview.py"),
                "--project-root",
                str(project_root),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        report = validate_docx_package(project_root / "out" / "preview.docx")

        self.assertTrue(report["ok"], msg=report["errors"])
        self.assertEqual(report["errors"], [])

    def test_voice_template_redacted_docx_passes_integrity_validation(self) -> None:
        project_root = PROJECT_ROOT / "temp" / "voice-real-project"
        recommend = subprocess.run(
            [
                str(PYTHON),
                str(PROJECT_ROOT / "scripts" / "recommend_template_styles.py"),
                "--project-root",
                str(project_root),
                "--apply",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(recommend.returncode, 0, msg=recommend.stderr)

        result = subprocess.run(
            [
                str(PYTHON),
                str(PROJECT_ROOT / "scripts" / "build_report.py"),
                "--project-root",
                str(project_root),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 2, msg=result.stderr or result.stdout)

        report = validate_docx_package(project_root / "out" / "redacted.docx")

        self.assertTrue(report["ok"], msg=report["errors"])
        self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()
