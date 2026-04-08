# Confirmation Reliability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add confirmation-focused scan metadata, preview confirmation artifacts, and preview verification while keeping the current template-first DOCX workflow intact.

**Architecture:** Preserve the existing `regions.locked` and `regions.fillable` contract, then layer additive scan metadata and a new `out/preview.summary.json` artifact on top. Keep `python-docx` as the engine for template-aware edits and add preview-specific verification rather than forcing preview and redacted outputs through the same checks.

**Tech Stack:** Python 3, `python-docx`, `unittest`, `uv`, JSON config files, script-based workflow under `scripts/`

---

### Task 1: Add uv Project Files

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `.gitignore`

**Step 1: Write the config assertions first**

Add a lightweight test in `tests/test_confirmation_package.py` that asserts the repo can install `python-docx` from declared dependencies.

```python
def test_dependency_files_exist(self) -> None:
    self.assertTrue((PROJECT_ROOT / "pyproject.toml").exists())
    self.assertTrue((PROJECT_ROOT / "requirements.txt").exists())
```

**Step 2: Run test to verify it fails**

Run: `D:\Miniconda\python.exe -m unittest tests.test_confirmation_package.ConfirmationPackageTests.test_dependency_files_exist -v`
Expected: FAIL because the files do not exist yet.

**Step 3: Write minimal implementation**

Create `pyproject.toml` with a minimal `uv`-compatible project definition and a `python-docx` dependency. Create `requirements.txt` with the same dependency. Create `.gitignore` entries for `.venv/`, `__pycache__/`, and `*.pyc`.

**Step 4: Run test to verify it passes**

Run: `D:\Miniconda\python.exe -m unittest tests.test_confirmation_package.ConfirmationPackageTests.test_dependency_files_exist -v`
Expected: PASS.

**Step 5: Commit**

If the workspace is later moved into git:

```bash
git add pyproject.toml requirements.txt .gitignore tests/test_confirmation_package.py
git commit -m "chore: add uv-managed Python project files"
```

### Task 2: Additive Template Scan Metadata

**Files:**
- Modify: `scripts/scan_template.py`
- Test: `tests/test_confirmation_package.py`

**Step 1: Write the failing test**

```python
def test_scan_template_reports_heading_anchors_and_field_candidates(self) -> None:
    scan = self.run_json("scan_template.py")
    anchors = scan["anchors"]
    self.assertTrue(any(item["kind"] == "heading" for item in anchors["headings"]))
    self.assertTrue(any(item["text"].endswith("：") for item in anchors["field_candidates"]))
```
```

**Step 2: Run test to verify it fails**

Run: `D:\Miniconda\python.exe -m unittest tests.test_confirmation_package.ConfirmationPackageTests.test_scan_template_reports_heading_anchors_and_field_candidates -v`
Expected: FAIL because `anchors` metadata is not present.

**Step 3: Write minimal implementation**

Update `scripts/scan_template.py` to emit additive `anchors` metadata:
- heading anchors from heading-like paragraphs
- field candidates from label-like paragraphs ending with `:` or `：`
- simple region candidates using the existing cover/body split boundary

Keep `regions.locked` and `regions.fillable` unchanged.

**Step 4: Run test to verify it passes**

Run: `D:\Miniconda\python.exe -m unittest tests.test_confirmation_package.ConfirmationPackageTests.test_scan_template_reports_heading_anchors_and_field_candidates -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/scan_template.py tests/test_confirmation_package.py
git commit -m "feat: enrich template scan metadata"
```

### Task 3: Preview Confirmation Package

**Files:**
- Modify: `scripts/build_preview.py`
- Modify: `workflow.json`
- Test: `tests/test_confirmation_package.py`

**Step 1: Write the failing test**

```python
def test_build_preview_writes_summary_and_region_markers(self) -> None:
    self.run_json("scan_template.py")
    result = self.run_json("build_preview.py")
    self.assertIn("summary", result)
    summary_path = Path(result["summary"])
    self.assertTrue(summary_path.exists())
    preview_doc = docx.Document(Path(result["preview"]))
    texts = [p.text for p in preview_doc.paragraphs if p.text.strip()]
    self.assertTrue(any("Locked Region" in text for text in texts))
    self.assertTrue(any("Fillable Region" in text for text in texts))
```
```

**Step 2: Run test to verify it fails**

Run: `D:\Miniconda\python.exe -m unittest tests.test_confirmation_package.ConfirmationPackageTests.test_build_preview_writes_summary_and_region_markers -v`
Expected: FAIL because no summary is written and no explicit markers exist.

**Step 3: Write minimal implementation**

Update `scripts/build_preview.py` to:
- insert explicit region marker paragraphs for locked and fillable regions
- keep fillable placeholders
- write `out/preview.summary.json`
- include field binding metadata and availability states in the summary

Update `workflow.json` only if a new summary path needs to be declared there.

**Step 4: Run test to verify it passes**

Run: `D:\Miniconda\python.exe -m unittest tests.test_confirmation_package.ConfirmationPackageTests.test_build_preview_writes_summary_and_region_markers -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/build_preview.py workflow.json tests/test_confirmation_package.py
git commit -m "feat: add preview confirmation summary"
```

### Task 4: Preview Verification Mode

**Files:**
- Modify: `scripts/verify_report.py`
- Test: `tests/test_confirmation_package.py`

**Step 1: Write the failing test**

```python
def test_verify_report_accepts_preview_mode(self) -> None:
    self.run_json("scan_template.py")
    preview = self.run_json("build_preview.py")
    result = subprocess.run(
        [
            str(PYTHON),
            str(self.project_root / "scripts" / "verify_report.py"),
            "--project-root",
            str(self.project_root),
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
```
```

**Step 2: Run test to verify it fails**

Run: `D:\Miniconda\python.exe -m unittest tests.test_confirmation_package.ConfirmationPackageTests.test_verify_report_accepts_preview_mode -v`
Expected: FAIL because preview verification is not implemented.

**Step 3: Write minimal implementation**

Update `scripts/verify_report.py` to detect preview mode from the selected docx path and verify:
- preview file exists
- preview summary exists
- locked and fillable region markers are present
- reported summary regions still match the current plan

Preserve existing redacted locked-region checks.

**Step 4: Run test to verify it passes**

Run: `D:\Miniconda\python.exe -m unittest tests.test_confirmation_package.ConfirmationPackageTests.test_verify_report_accepts_preview_mode -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/verify_report.py tests/test_confirmation_package.py
git commit -m "feat: verify preview confirmation artifacts"
```

### Task 5: Full Regression

**Files:**
- Verify only: `tests/test_init_project.py`
- Verify only: `tests/test_confirmation_package.py`
- Verify only: `scripts/*.py`

**Step 1: Run focused confirmation tests**

Run: `D:\Miniconda\python.exe -m unittest tests.test_confirmation_package -v`
Expected: PASS.

**Step 2: Run existing regression tests**

Run: `D:\Miniconda\python.exe -m unittest discover -s tests -v`
Expected: PASS.

**Step 3: Run py_compile verification**

Run: `D:\Miniconda\python.exe -m py_compile scripts\__init__.py scripts\_shared.py scripts\list_private_fields.py scripts\scan_template.py scripts\build_preview.py scripts\build_report.py scripts\inject_private_fields.py scripts\verify_report.py scripts\cleanup_project.py scripts\init_project.py`
Expected: PASS with no output.

**Step 4: Run workflow verification in order**

Run: `D:\Miniconda\python.exe scripts\scan_template.py --project-root .`
Expected: PASS with enriched scan JSON.

Run: `D:\Miniconda\python.exe scripts\build_preview.py --project-root .`
Expected: PASS with preview and summary paths.

Run: `D:\Miniconda\python.exe scripts\verify_report.py --project-root . --docx out\preview.docx`
Expected: PASS in preview mode.

**Step 5: Commit**

```bash
git add .
git commit -m "feat: improve confirmation reliability"
```
