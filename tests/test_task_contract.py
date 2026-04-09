from __future__ import annotations

import json
import subprocess
import unittest
import uuid
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(r"D:\Miniconda\python.exe")


class TaskContractTests(unittest.TestCase):
    def create_project(self) -> Path:
        sandbox_root = PROJECT_ROOT / "temp" / "task-contract-tests"
        sandbox_root.mkdir(parents=True, exist_ok=True)
        project_root = sandbox_root / uuid.uuid4().hex
        project_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(
            lambda: __import__("shutil").rmtree(project_root, ignore_errors=True)
        )
        return project_root

    def load_task_yaml(self, project_root: Path) -> dict[str, object]:
        return yaml.safe_load(
            (project_root / "report.task.yaml").read_text(encoding="utf-8")
        )

    def init_project(self, project_root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(PYTHON),
                str(PROJECT_ROOT / "scripts" / "init_project.py"),
                "--project-root",
                str(project_root),
            ],
            capture_output=True,
            text=True,
        )

    def run_workflow(
        self, project_root: Path, action: str, *extra_args: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(PYTHON),
                str(PROJECT_ROOT / "scripts" / "workflow_agent.py"),
                action,
                "--project-root",
                str(project_root),
                *extra_args,
            ],
            capture_output=True,
            text=True,
        )

    def assert_task_contract_shape(self, payload: dict[str, object]) -> None:
        for key in (
            "schema",
            "task",
            "requirements",
            "inputs",
            "decisions",
            "runtime",
        ):
            self.assertIn(key, payload)
        self.assertEqual(payload["schema"]["kind"], "report_task")
        self.assertFalse(payload["task"]["ready_to_write"])
        self.assertEqual(payload["runtime"]["workflow_config"], "./workflow.json")

    def test_init_project_creates_report_task_yaml(self) -> None:
        project_root = self.create_project()

        result = self.init_project(project_root)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue((project_root / "report.task.yaml").exists())
        self.assert_task_contract_shape(self.load_task_yaml(project_root))

    def test_load_task_contract_returns_default_shape(self) -> None:
        from scripts._task_contract import load_task_contract

        project_root = self.create_project()
        task_path = project_root / "report.task.yaml"

        payload = load_task_contract(task_path)

        self.assert_task_contract_shape(payload)

    def test_dump_task_contract_round_trips_yaml(self) -> None:
        from scripts._task_contract import (
            default_task_contract,
            dump_task_contract,
            load_task_contract,
        )

        project_root = self.create_project()
        task_path = project_root / "report.task.yaml"
        payload = default_task_contract()
        payload["task"]["name"] = "示例任务"

        dump_task_contract(task_path, payload)
        loaded = load_task_contract(task_path)

        self.assert_task_contract_shape(loaded)
        self.assertEqual(loaded["task"]["name"], "示例任务")

    def test_workflow_agent_prepare_updates_report_task_runtime(self) -> None:
        project_root = self.create_project()

        init_result = self.init_project(project_root)
        self.assertEqual(init_result.returncode, 0, msg=init_result.stderr)

        result = self.run_workflow(project_root, "prepare")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["action"], "prepare")

        task_contract = self.load_task_yaml(project_root)
        runtime = task_contract["runtime"]
        self.assertEqual(runtime["preview_output"], "./out/preview.docx")
        self.assertEqual(runtime["template_plan"], "./config/template.plan.json")
        self.assertEqual(runtime["field_binding"], "./config/field.binding.json")
        self.assertIn(runtime["next_step"], {"review_preview_summary", "build"})


if __name__ == "__main__":
    unittest.main()
