from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import docx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"


class ConfirmationPackageTests(unittest.TestCase):
    def test_dependency_files_exist(self) -> None:
        self.assertTrue((PROJECT_ROOT / "pyproject.toml").exists())
        self.assertTrue((PROJECT_ROOT / "requirements.txt").exists())
        self.assertIn("Pygments", (PROJECT_ROOT / "pyproject.toml").read_text())
        self.assertIn("Pygments", (PROJECT_ROOT / "requirements.txt").read_text())

    def test_root_readme_exists_with_repo_specific_content(self) -> None:
        readme_path = PROJECT_ROOT / "README.md"
        self.assertTrue(readme_path.exists())
        readme = readme_path.read_text(encoding="utf-8")
        self.assertIn("uv", readme)
        self.assertIn("build_report.py", readme)
        self.assertIn("preview", readme)

    def test_root_license_is_mit(self) -> None:
        license_path = PROJECT_ROOT / "LICENSE"
        self.assertTrue(license_path.exists())
        license_text = license_path.read_text(encoding="utf-8")
        self.assertIn("Permission is hereby granted, free of charge", license_text)
        self.assertIn("MIT License", license_text)

    def test_init_project_copies_code_theme_sample(self) -> None:
        project_root = self.create_project()

        workflow = json.loads(
            (project_root / "workflow.json").read_text(encoding="utf-8")
        )
        self.assertEqual(workflow["rendering"]["code_blocks"]["theme"], "github-light")
        self.assertEqual(
            workflow["rendering"]["code_blocks"]["theme_override"],
            "./config/code-theme.user.json",
        )
        self.assertTrue(
            (project_root / "config" / "code-theme.user.sample.json").exists()
        )

    def create_project(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        project_root = Path(temp_dir.name)
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

    def run_json(
        self, project_root: Path, script_name: str, *extra_args: str
    ) -> dict[str, object]:
        result = subprocess.run(
            [
                str(PYTHON),
                str(project_root / "scripts" / script_name),
                "--project-root",
                str(project_root),
                *extra_args,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return json.loads(result.stdout)

    def test_scan_template_reports_heading_anchors_and_field_candidates(self) -> None:
        project_root = self.create_project()
        scan = self.run_json(project_root, "scan_template.py")

        anchors = scan["anchors"]
        headings = anchors["headings"]
        field_candidates = anchors["field_candidates"]

        self.assertTrue(any(item["kind"] == "heading" for item in headings))
        self.assertTrue(
            any(str(item["text"]).endswith("：") for item in field_candidates)
        )

    def test_build_preview_writes_summary_and_region_markers(self) -> None:
        project_root = self.create_project()
        preview = self.run_json(project_root, "build_preview.py")

        self.assertIn("summary", preview)
        summary_path = Path(preview["summary"])
        self.assertTrue(summary_path.exists())
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(summary["preview"], "./out/preview.docx")
        self.assertEqual(summary["summary"], "./out/preview.summary.json")
        self.assertTrue(summary["field_binding"]["bindings"])
        self.assertIn("completion_date", summary["field_binding"]["availability"])

        preview_doc = docx.Document(Path(preview["preview"]))
        texts = [
            paragraph.text.strip()
            for paragraph in preview_doc.paragraphs
            if paragraph.text.strip()
        ]

        self.assertTrue(any("Locked Region" in text for text in texts))
        self.assertTrue(any("Fillable Region" in text for text in texts))

    def test_verify_report_accepts_preview_mode(self) -> None:
        project_root = self.create_project()
        self.run_json(project_root, "build_preview.py")

        result = subprocess.run(
            [
                str(PYTHON),
                str(project_root / "scripts" / "verify_report.py"),
                "--project-root",
                str(project_root),
                "--docx",
                "out/preview.docx",
            ],
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "preview")
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
