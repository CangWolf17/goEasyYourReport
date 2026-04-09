from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
