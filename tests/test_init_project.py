from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
import unittest
import uuid
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import docx
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(r"D:\Miniconda\python.exe")
TEST_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
)
TEST_TEMP_ROOT = PROJECT_ROOT / "temp" / "init-project-tests"
TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)


class RepoTemporaryDirectory:
    def __init__(
        self,
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
        ignore_cleanup_errors: bool = False,
    ) -> None:
        root = Path(dir) if dir else TEST_TEMP_ROOT
        root.mkdir(parents=True, exist_ok=True)
        self._ignore_cleanup_errors = ignore_cleanup_errors
        folder_name = f"{prefix or 'tmp'}{uuid.uuid4().hex}{suffix or ''}"
        self.path = root / folder_name
        self.path.mkdir(parents=True, exist_ok=False)
        self.name = str(self.path)

    def __enter__(self) -> str:
        return self.name

    def cleanup(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()


tempfile.TemporaryDirectory = RepoTemporaryDirectory


def write_style_poor_template(path: Path) -> None:
    template_doc = docx.Document()
    template_doc.add_paragraph("课程考核报告")
    template_doc.add_paragraph("姓 名：")
    template_doc.add_paragraph("学 号：")
    template_doc.add_paragraph("完成日期：")
    template_doc.add_heading("课程题目", level=1)
    template_doc.add_heading("1 实验目的", level=2)
    template_doc.add_paragraph("这里是普通正文。")
    template_doc.add_heading("2 实验结果", level=2)
    template_doc.add_paragraph("这里是普通正文。")
    template_doc.save(path)


def strip_list_styles(path: Path) -> None:
    w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    def qn_local(local_name: str) -> str:
        return f"{{{w_ns}}}{local_name}"

    target_names = {
        "List Bullet",
        "List Bullet 2",
        "List Bullet 3",
        "List Number",
        "List Number 2",
        "List Number 3",
        "List Continue",
        "List Continue 2",
        "List Continue 3",
        "List Paragraph",
    }

    with zipfile.ZipFile(path, "r") as source_zip:
        entries = {
            info.filename: source_zip.read(info.filename)
            for info in source_zip.infolist()
        }

    styles_root = ET.fromstring(entries["word/styles.xml"])
    for child in list(styles_root):
        if child.tag == qn_local("style"):
            name_element = child.find(qn_local("name"))
            style_name = (
                name_element.get(qn_local("val")) if name_element is not None else None
            )
            if style_name in target_names:
                styles_root.remove(child)
        elif child.tag == qn_local("latentStyles"):
            for latent in list(child):
                if (
                    latent.tag == qn_local("lsdException")
                    and latent.get(qn_local("name")) in target_names
                ):
                    child.remove(latent)

    entries["word/styles.xml"] = ET.tostring(
        styles_root, encoding="utf-8", xml_declaration=True
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as output_zip:
        for filename, content in entries.items():
            output_zip.writestr(filename, content)


def style_font_settings(style) -> dict[str, object]:
    rpr = style.element.find(qn("w:rPr"))
    rfonts = rpr.find(qn("w:rFonts")) if rpr is not None else None
    size = rpr.find(qn("w:sz")) if rpr is not None else None
    return {
        "ascii": None if rfonts is None else rfonts.get(qn("w:ascii")),
        "hAnsi": None if rfonts is None else rfonts.get(qn("w:hAnsi")),
        "eastAsia": None if rfonts is None else rfonts.get(qn("w:eastAsia")),
        "size": None if size is None else size.get(qn("w:val")),
    }


def run_font_settings(run) -> dict[str, object]:
    rpr = run._r.find(qn("w:rPr"))
    rfonts = rpr.find(qn("w:rFonts")) if rpr is not None else None
    size = rpr.find(qn("w:sz")) if rpr is not None else None
    return {
        "ascii": None if rfonts is None else rfonts.get(qn("w:ascii")),
        "hAnsi": None if rfonts is None else rfonts.get(qn("w:hAnsi")),
        "eastAsia": None if rfonts is None else rfonts.get(qn("w:eastAsia")),
        "size": None if size is None else size.get(qn("w:val")),
    }


class InitProjectTests(unittest.TestCase):
    def test_run_optional_reads_utf8_child_output(self) -> None:
        from scripts.init_project import run_optional

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            scripts_root = project_root / "scripts"
            scripts_root.mkdir(parents=True, exist_ok=True)
            script_path = scripts_root / "emit_utf8.py"
            script_path.write_text(
                (
                    "import sys\n"
                    "sys.stdout.buffer.write('{\"message\":\"姓 名：\"}'.encode('utf-8'))\n"
                ),
                encoding="utf-8",
            )

            result = run_optional("emit_utf8.py", project_root)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["returncode"], 0)
            self.assertEqual(result["stdout"], '{"message":"姓 名："}')
            self.assertEqual(result["stderr"], "")

    def test_init_project_creates_default_templates_and_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
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
            self.assertTrue(
                (project_root / "templates" / "template.sample.docx").exists()
            )
            self.assertTrue(
                (project_root / "templates" / "template.user.docx").exists()
            )
            self.assertTrue((project_root / "out" / "preview.docx").exists())

            init_report = json.loads(
                (project_root / "logs" / "init_report.json").read_text(encoding="utf-8")
            )
            script_names = [item["script"] for item in init_report["script_results"]]
            self.assertIn("scan_template.py", script_names)
            self.assertIn("build_preview.py", script_names)

    def test_init_project_writes_language_preference_to_user_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
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

            user_profile = (project_root / "user" / "user.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- 语言：中文", user_profile)
            self.assertIn("- 语言偏好：zh-CN", user_profile)

    def test_init_project_uses_sanitized_default_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
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
            template_doc = docx.Document(
                project_root / "templates" / "template.user.docx"
            )
            visible = [
                paragraph.text.strip()
                for paragraph in template_doc.paragraphs
                if paragraph.text.strip()
            ]

            self.assertIn("报告题目 / Report Title", visible)
            self.assertIn("姓 名：", visible)
            self.assertIn("学 号：", visible)
            self.assertIn("完成日期：", visible)

    def test_init_project_force_refreshes_default_template_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            first_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(first_result.returncode, 0, msg=first_result.stderr)

            for relative in (
                "templates/template.sample.docx",
                "templates/template.user.docx",
            ):
                stale_doc = docx.Document()
                stale_doc.add_paragraph("stale template")
                stale_doc.save(project_root / relative)

            refresh_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                    "--force",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(refresh_result.returncode, 0, msg=refresh_result.stderr)

            refreshed_doc = docx.Document(
                project_root / "templates" / "template.user.docx"
            )
            visible = [
                paragraph.text.strip()
                for paragraph in refreshed_doc.paragraphs
                if paragraph.text.strip()
            ]
            self.assertIn("报告题目 / Report Title", visible)

    def test_init_project_generates_template_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            source_template = project_root / "voice-template.docx"
            write_style_poor_template(source_template)

            result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                    "--template",
                    str(source_template),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(
                (project_root / "templates" / "template.recommended.docx").exists()
            )
            recommendation = json.loads(
                (
                    project_root / "logs" / "template_style_recommendation.json"
                ).read_text(encoding="utf-8")
            )

            self.assertEqual(
                recommendation["recommended_template"],
                "./templates/template.recommended.docx",
            )
            self.assertIn("正文", recommendation["missing_styles"])
            self.assertIn("正文", recommendation["copied_styles"])
            self.assertTrue(recommendation["pending_acceptance"])

    def test_preview_summary_requires_confirmation_when_recommended_template_pending(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            source_template = project_root / "voice-template.docx"
            write_style_poor_template(source_template)

            result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                    "--template",
                    str(source_template),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            summary = json.loads(
                (project_root / "out" / "preview.summary.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertIn(
                "template style recommendation pending",
                summary["review"]["needs_confirmation"],
            )
            self.assertEqual(
                summary["template_recommendation"]["recommended_template"],
                "./templates/template.recommended.docx",
            )
            self.assertTrue(summary["template_recommendation"]["pending_acceptance"])

    def test_apply_template_recommendation_switches_primary_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            source_template = project_root / "voice-template.docx"
            write_style_poor_template(source_template)

            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                    "--template",
                    str(source_template),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            apply_result = subprocess.run(
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
            self.assertEqual(apply_result.returncode, 0, msg=apply_result.stderr)

            plan = json.loads(
                (project_root / "config" / "template.plan.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                plan["selection"]["primary_template"],
                "./templates/template.recommended.docx",
            )

            user_template = docx.Document(
                project_root / "templates" / "template.user.docx"
            )
            user_style_names = {
                style.name
                for style in user_template.styles
                if getattr(style, "name", None)
            }
            self.assertNotIn("正文", user_style_names)

    def test_private_field_injection_builds_private_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)

            private_source = project_root.parent / "private-fields.json"
            private_source.write_text(
                json.dumps(
                    {"full_name": "Test User", "student_id": "S-001"},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            inject_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "inject_private_fields.py"),
                    "--project-root",
                    str(project_root),
                    "--source",
                    str(private_source),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(inject_result.returncode, 0, msg=inject_result.stderr)

            private_doc = docx.Document(project_root / "out" / "private.docx")
            texts = [paragraph.text for paragraph in private_doc.paragraphs]
            self.assertTrue(any("Test User" in text for text in texts))
            self.assertTrue(any("S-001" in text for text in texts))

    def test_build_report_splits_markdown_into_multiple_paragraphs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "# Summary\n\nFirst paragraph.\n\n## Details\n\nSecond paragraph.",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            texts = [
                paragraph.text.strip()
                for paragraph in redacted_doc.paragraphs
                if paragraph.text.strip()
            ]

            self.assertIn("Summary", texts)
            self.assertIn("First paragraph.", texts)
            self.assertIn("Details", texts)
            self.assertIn("Second paragraph.", texts)

    def test_build_report_prefers_template_native_body_styles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "# 报告题目\n\n## 一级标题\n\n### 二级标题\n\n正文段落示例。",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            rendered = {
                paragraph.text.strip(): paragraph.style.name
                for paragraph in redacted_doc.paragraphs
                if paragraph.text.strip()
            }

            self.assertEqual(rendered["报告题目"], "题目")
            self.assertEqual(rendered["一级标题"], "标题2")
            self.assertEqual(rendered["二级标题"], "标题3")
            self.assertEqual(rendered["正文段落示例。"], "正文")

    def test_build_report_renders_fenced_code_block_as_single_cell_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "## Code Example\n\n```python\nprint('hello')\nprint('world')\n```",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)
            payload = json.loads(build_result.stdout)
            self.assertEqual(payload["code_blocks"]["styled"], 1)
            self.assertEqual(payload["code_blocks"]["highlighted"], 1)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            self.assertEqual(len(redacted_doc.tables), 1)
            table = redacted_doc.tables[0]
            self.assertEqual(len(table.rows), 1)
            self.assertEqual(len(table.columns), 1)
            self.assertEqual(table.cell(0, 0).paragraphs[0].text.strip(), "python")
            cell_text = "\n".join(
                paragraph.text for paragraph in table.cell(0, 0).paragraphs
            )
            self.assertIn("print('hello')", cell_text)
            self.assertIn("print('world')", cell_text)

    def test_build_report_highlights_c_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "## C Example\n\n```c\nint main(void) {\n  return 0;\n}\n```",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)
            payload = json.loads(build_result.stdout)
            self.assertEqual(payload["code_blocks"]["highlighted"], 1)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            table = redacted_doc.tables[0]
            self.assertEqual(table.cell(0, 0).paragraphs[0].text.strip(), "c")

    def test_build_report_highlights_cpp_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "## CPP Example\n\n```cpp\n#include <iostream>\nint main() {\n  std::cout << 1;\n}\n```",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)
            payload = json.loads(build_result.stdout)
            self.assertEqual(payload["code_blocks"]["highlighted"], 1)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            table = redacted_doc.tables[0]
            self.assertEqual(table.cell(0, 0).paragraphs[0].text.strip(), "cpp")

    def test_build_report_highlights_java_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "## Java Example\n\n```java\nclass Demo {\n  int x = 1;\n}\n```",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)
            payload = json.loads(build_result.stdout)
            self.assertEqual(payload["code_blocks"]["highlighted"], 1)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            table = redacted_doc.tables[0]
            self.assertEqual(table.cell(0, 0).paragraphs[0].text.strip(), "java")

    def test_build_report_requires_agent_handoff_for_unsupported_language(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                '## Rust Example\n\n```rust\nfn main() {\n    println!("hi");\n}\n```',
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(build_result.returncode, 0)
            payload = json.loads(build_result.stdout)
            self.assertEqual(payload["code_blocks"]["styled"], 1)
            self.assertEqual(payload["code_blocks"]["highlighted"], 0)
            self.assertEqual(len(payload["code_blocks"]["unsupported"]), 1)
            self.assertEqual(
                payload["code_blocks"]["unsupported"][0]["language"], "rust"
            )
            self.assertIsNone(payload["code_blocks"]["unsupported"][0]["normalized"])
            self.assertEqual(
                payload["code_blocks"]["unsupported"][0]["action"],
                "agent_handoff_required",
            )

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            table = redacted_doc.tables[0]
            self.assertEqual(table.cell(0, 0).paragraphs[0].text.strip(), "rust")

    def test_build_report_applies_code_theme_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "config" / "code-theme.user.json").write_text(
                json.dumps(
                    {
                        "base": "github-light",
                        "roles": {
                            "header_bg": "#EFEFEF",
                            "border": "#111111",
                            "header_fg": "#8A2BE2",
                            "keyword": "#AA0000",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (project_root / "docs" / "report_body.md").write_text(
                "## Code Example\n\n```python\nprint('hello')\n```",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)
            payload = json.loads(build_result.stdout)
            self.assertTrue(payload["code_blocks"]["theme"]["override_used"])
            self.assertEqual(payload["code_blocks"]["theme"]["name"], "github-light")
            self.assertEqual(payload["code_blocks"]["warnings"], [])

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            table = redacted_doc.tables[0]
            self.assertIn("EFEFEF", table.cell(0, 0).paragraphs[0]._p.xml.upper())
            self.assertIn("111111", table.cell(0, 0)._tc.xml.upper())

    def test_build_report_warns_on_invalid_code_theme_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "config" / "code-theme.user.json").write_text(
                json.dumps(
                    {
                        "base": "github-light",
                        "roles": {
                            "keyword": "not-a-hex",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (project_root / "docs" / "report_body.md").write_text(
                "## Code Example\n\n```python\nprint('hello')\n```",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)
            payload = json.loads(build_result.stdout)
            self.assertFalse(payload["code_blocks"]["theme"]["override_used"])
            self.assertTrue(payload["code_blocks"]["warnings"])

    def test_build_report_warns_on_non_object_code_theme_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "config" / "code-theme.user.json").write_text(
                "[]",
                encoding="utf-8",
            )
            (project_root / "docs" / "report_body.md").write_text(
                "## Code Example\n\n```python\nprint('hello')\n```",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)
            payload = json.loads(build_result.stdout)
            self.assertFalse(payload["code_blocks"]["theme"]["override_used"])
            self.assertTrue(payload["code_blocks"]["warnings"])

    def test_build_report_highlights_remaining_supported_languages_and_aliases(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                '## Languages\n\n```json\n{"a": 1}\n```\n\n```sh\necho hi\n```\n\n```yml\nname: demo\n```\n\n```sql\nselect 1;\n```\n\n```js\nconst n = 1;\n```\n\n```ts\nconst n: number = 1;\n```\n\n```c++\nint main() { return 0; }\n```',
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)
            payload = json.loads(build_result.stdout)
            self.assertEqual(payload["code_blocks"]["highlighted"], 7)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            headers = [
                table.cell(0, 0).paragraphs[0].text.strip()
                for table in redacted_doc.tables
            ]
            self.assertIn("json", headers)
            self.assertIn("bash", headers)
            self.assertIn("yaml", headers)
            self.assertIn("sql", headers)
            self.assertIn("javascript", headers)
            self.assertIn("typescript", headers)
            self.assertIn("cpp", headers)

    def test_build_report_renders_styled_plain_code_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "## Code Example\n\n```\nplain line 1\nplain line 2\n```",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            self.assertEqual(len(redacted_doc.tables), 1)
            table = redacted_doc.tables[0]
            cell_paragraphs = [
                paragraph.text.strip() for paragraph in table.cell(0, 0).paragraphs
            ]
            self.assertIn("Code", cell_paragraphs)
            self.assertIn("plain line 1", cell_paragraphs)
            self.assertIn("plain line 2", cell_paragraphs)

    def test_build_report_renders_markdown_lists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "## Items\n\n- First bullet\n- Second bullet\n\n1. First number\n2. Second number\n",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            rendered = [
                (paragraph.text.strip(), paragraph.style.name)
                for paragraph in redacted_doc.paragraphs
                if paragraph.text.strip()
            ]

            self.assertIn(("First bullet", "列表符号"), rendered)
            self.assertIn(("Second bullet", "列表符号"), rendered)
            self.assertIn(("First number", "列表编号"), rendered)
            self.assertIn(("Second number", "列表编号"), rendered)

    def test_build_report_lists_inherit_body_font_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "正文段落示例。\n\n- First bullet\n\n1. First number\n",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            body_style = redacted_doc.styles["正文"]
            expected = style_font_settings(body_style)

            list_runs = [
                paragraph.runs[0]
                for paragraph in redacted_doc.paragraphs
                if paragraph.text.strip() in {"First bullet", "First number"}
            ]

            self.assertEqual(len(list_runs), 2)
            for run in list_runs:
                self.assertEqual(run_font_settings(run), expected)

    def test_build_report_preserves_visible_list_markers_without_list_styles(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            source_template = project_root / "voice-template.docx"
            write_style_poor_template(source_template)
            strip_list_styles(source_template)

            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                    "--template",
                    str(source_template),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "## Items\n\n- First bullet\n- Second bullet\n\n1. First number\n2. Second number\n",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            rendered_texts = [
                paragraph.text.strip()
                for paragraph in redacted_doc.paragraphs
                if paragraph.text.strip()
            ]

            self.assertIn("- First bullet", rendered_texts)
            self.assertIn("- Second bullet", rendered_texts)
            self.assertIn("1. First number", rendered_texts)
            self.assertIn("2. Second number", rendered_texts)

    def test_build_report_renders_simple_pipe_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "## Metrics\n\n| Name | Value |\n| --- | --- |\n| Alpha | 1 |\n| Beta | 2 |\n",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            self.assertEqual(len(redacted_doc.tables), 1)
            table = redacted_doc.tables[0]
            rows = [[cell.text for cell in row.cells] for row in table.rows]
            self.assertEqual(rows, [["Name", "Value"], ["Alpha", "1"], ["Beta", "2"]])

    def test_build_report_inserts_existing_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            image_path = project_root / "docs" / "images" / "arch.png"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(TEST_PNG_BYTES)

            (project_root / "docs" / "report_body.md").write_text(
                "## Figures\n\n![Architecture](images/arch.png)\n",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)
            payload = json.loads(build_result.stdout)
            self.assertEqual(payload["images"]["failed"], [])
            self.assertEqual(len(payload["images"]["inserted"]), 1)
            self.assertEqual(
                payload["images"]["inserted"][0]["path"], "images/arch.png"
            )

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            self.assertTrue(
                any(
                    "<w:drawing" in paragraph._p.xml
                    for paragraph in redacted_doc.paragraphs
                )
            )

    def test_build_report_renders_centered_figure_with_caption_below(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            image_path = project_root / "docs" / "images" / "arch.png"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(TEST_PNG_BYTES)

            (project_root / "docs" / "report_body.md").write_text(
                "## Figures\n\n![Architecture](images/arch.png)\n",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            image_indexes = [
                index
                for index, paragraph in enumerate(redacted_doc.paragraphs)
                if "<w:drawing" in paragraph._p.xml
            ]
            self.assertEqual(len(image_indexes), 1)

            image_paragraph = redacted_doc.paragraphs[image_indexes[0]]
            self.assertEqual(image_paragraph.alignment, WD_ALIGN_PARAGRAPH.CENTER)
            self.assertIn("wp:inline", image_paragraph._p.xml)
            self.assertNotIn("wp:anchor", image_paragraph._p.xml)
            self.assertNotIn("wrapTopAndBottom", image_paragraph._p.xml)

            caption_paragraph = redacted_doc.paragraphs[image_indexes[0] + 1]
            self.assertEqual(caption_paragraph.style.name, "图题")
            self.assertTrue(caption_paragraph.text.strip().startswith("图1"))

            with zipfile.ZipFile(
                project_root / "out" / "redacted.docx", "r"
            ) as docx_zip:
                document_xml = docx_zip.read("word/document.xml").decode("utf-8")
            self.assertIn("<wp:inline", document_xml)
            self.assertNotIn("<wp:anchor", document_xml)

    def test_build_report_renders_centered_table_with_caption_and_cell_formatting(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "## Metrics\n\n| Name | Value |\n| --- | --- |\n| Alpha | 1 |\n| Beta | 2 |\n",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            self.assertEqual(len(redacted_doc.tables), 1)
            table = redacted_doc.tables[0]
            self.assertEqual(table.alignment, WD_TABLE_ALIGNMENT.CENTER)

            caption_element = table._tbl.getprevious()
            self.assertIsNotNone(caption_element)
            self.assertIn("表1", caption_element.xpath("string()"))

            caption_texts = [
                (paragraph.text.strip(), paragraph.style.name)
                for paragraph in redacted_doc.paragraphs
                if paragraph.text.strip()
            ]
            self.assertIn(("表1 Metrics", "表题"), caption_texts)

            cell_paragraph = table.cell(0, 0).paragraphs[0]
            self.assertEqual(cell_paragraph.alignment, WD_ALIGN_PARAGRAPH.CENTER)
            self.assertEqual(
                table.cell(0, 0).vertical_alignment,
                WD_CELL_VERTICAL_ALIGNMENT.CENTER,
            )
            self.assertIsNotNone(cell_paragraph.paragraph_format.first_line_indent)
            self.assertEqual(cell_paragraph.paragraph_format.first_line_indent.pt, 0.0)
            self.assertEqual(cell_paragraph.paragraph_format.line_spacing, 1.5)

            cell_run = cell_paragraph.runs[0]
            self.assertEqual(cell_run.font.name, "宋体")
            self.assertIsNotNone(cell_run.font.size)
            self.assertEqual(cell_run.font.size.pt, 10.5)
            self.assertEqual(run_font_settings(cell_run)["eastAsia"], "宋体")

    def test_build_report_strips_section_number_from_table_caption(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "## 3 实验环境与参数\n\n| 参数 | 数值 |\n| --- | --- |\n| 采样率 | 16000 Hz |\n",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            caption_texts = [
                paragraph.text.strip()
                for paragraph in redacted_doc.paragraphs
                if paragraph.style.name == "表题" and paragraph.text.strip()
            ]

            self.assertIn("表1 实验环境与参数", caption_texts)
            self.assertNotIn("表1 3 实验环境与参数", caption_texts)

    def test_build_report_applies_reference_style_in_reference_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "## 参考文献\n\n[1] 作者. 题名[J]. 期刊名, 2024, 1(1): 1-10.\n\n[2] 作者. 书名[M]. 北京: 出版社, 2023.\n",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            rendered = {
                paragraph.text.strip(): paragraph.style.name
                for paragraph in redacted_doc.paragraphs
                if paragraph.text.strip().startswith("[")
            }

            self.assertEqual(
                rendered["[1] 作者. 题名[J]. 期刊名, 2024, 1(1): 1-10."],
                "参考文献",
            )
            self.assertEqual(
                rendered["[2] 作者. 书名[M]. 北京: 出版社, 2023."],
                "参考文献",
            )

    def test_build_report_applies_reference_style_in_numbered_reference_section(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "## 二、参考文献\n\n[1] 作者. 题名[J]. 期刊名, 2024, 1(1): 1-10.\n",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            rendered = {
                paragraph.text.strip(): paragraph.style.name
                for paragraph in redacted_doc.paragraphs
                if paragraph.text.strip().startswith("[")
            }
            self.assertEqual(
                rendered["[1] 作者. 题名[J]. 期刊名, 2024, 1(1): 1-10."],
                "参考文献",
            )

    def test_build_report_applies_reference_style_to_numbered_reference_entries(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "## 参考文献\n\n1. Author. Title[J]. Journal, 2024, 1(1): 1-10.\n2. Author. Book[M]. Beijing: Press, 2023.\n",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            rendered = {
                paragraph.text.strip(): paragraph.style.name
                for paragraph in redacted_doc.paragraphs
                if paragraph.text.strip().startswith(("Author. Title", "Author. Book"))
            }
            self.assertEqual(
                rendered["Author. Title[J]. Journal, 2024, 1(1): 1-10."],
                "参考文献",
            )
            self.assertEqual(
                rendered["Author. Book[M]. Beijing: Press, 2023."],
                "参考文献",
            )

    def test_build_report_reports_failed_image_insertions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            (project_root / "docs" / "report_body.md").write_text(
                "## Figures\n\n![Missing](images/missing.png)\n",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(build_result.returncode, 0)
            payload = json.loads(build_result.stdout)
            self.assertEqual(
                payload["redacted"], str(project_root / "out" / "redacted.docx")
            )
            self.assertEqual(payload["images"]["inserted"], [])
            self.assertEqual(len(payload["images"]["failed"]), 1)
            self.assertEqual(
                payload["images"]["failed"][0]["path"], "images/missing.png"
            )

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            rendered = [
                paragraph.text.strip()
                for paragraph in redacted_doc.paragraphs
                if paragraph.text.strip()
            ]
            self.assertTrue(
                any(
                    text.startswith(
                        "[Image Insert Failed] Missing (images/missing.png):"
                    )
                    for text in rendered
                )
            )

    def test_build_report_reports_corrupt_image_insertions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            init_result = subprocess.run(
                [
                    str(PYTHON),
                    str(PROJECT_ROOT / "scripts" / "init_project.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

            image_path = project_root / "docs" / "images" / "bad.png"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(b"not-a-real-png")

            (project_root / "docs" / "report_body.md").write_text(
                "## Figures\n\n![Broken](images/bad.png)\n",
                encoding="utf-8",
            )

            build_result = subprocess.run(
                [
                    str(PYTHON),
                    str(project_root / "scripts" / "build_report.py"),
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(build_result.returncode, 0)
            payload = json.loads(build_result.stdout)
            self.assertEqual(payload["images"]["inserted"], [])
            self.assertEqual(len(payload["images"]["failed"]), 1)
            self.assertEqual(payload["images"]["failed"][0]["path"], "images/bad.png")
            self.assertNotEqual(
                payload["images"]["failed"][0]["reason"], "file not found"
            )

            redacted_doc = docx.Document(project_root / "out" / "redacted.docx")
            rendered = [
                paragraph.text.strip()
                for paragraph in redacted_doc.paragraphs
                if paragraph.text.strip()
            ]
            self.assertTrue(
                any(
                    text.startswith("[Image Insert Failed] Broken (images/bad.png):")
                    for text in rendered
                )
            )


if __name__ == "__main__":
    unittest.main()
