from __future__ import annotations

import base64
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(r"D:\Miniconda\python.exe")
TEST_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
)


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
                "# 一级标题\n\n## 二级标题\n\n### 三级标题\n\n正文段落示例。",
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

            self.assertEqual(rendered["一级标题"], "标题2")
            self.assertEqual(rendered["二级标题"], "标题3")
            self.assertEqual(rendered["三级标题"], "标题4")
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

            self.assertIn(("First bullet", "List Bullet"), rendered)
            self.assertIn(("Second bullet", "List Bullet"), rendered)
            self.assertIn(("First number", "List Number"), rendered)
            self.assertIn(("Second number", "List Number"), rendered)

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
            self.assertIn("wrapTopAndBottom", image_paragraph._p.xml)
            simple_pos = image_paragraph._p.findall(".//" + qn("wp:simplePos"))[0]
            position_h = image_paragraph._p.findall(".//" + qn("wp:positionH"))[0]
            position_v = image_paragraph._p.findall(".//" + qn("wp:positionV"))[0]

            self.assertEqual(simple_pos.attrib, {"x": "0", "y": "0"})
            self.assertEqual(position_h.attrib, {"relativeFrom": "margin"})
            self.assertEqual(position_v.attrib, {"relativeFrom": "paragraph"})

            caption_paragraph = redacted_doc.paragraphs[image_indexes[0] + 1]
            self.assertEqual(caption_paragraph.style.name, "图题")
            self.assertTrue(caption_paragraph.text.strip().startswith("图1"))

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
            self.assertIsNotNone(cell_paragraph.paragraph_format.first_line_indent)
            self.assertEqual(cell_paragraph.paragraph_format.first_line_indent.pt, 0.0)
            self.assertEqual(cell_paragraph.paragraph_format.line_spacing, 1.5)

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
