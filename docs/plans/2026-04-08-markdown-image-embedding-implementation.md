# Markdown Image Embedding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade Markdown image handling from visible placeholders to real DOCX image insertion, while clearly reporting any failed insertions to the user.

**Architecture:** Keep the current block-based Markdown parser and extend the existing `image_placeholder` behavior into an `image` block that attempts insertion during render. On failure, render a deterministic failure placeholder in the DOCX and include structured failure details in `build_report.py` JSON output so the user can tell exactly which images did not insert.

**Tech Stack:** Python 3, `python-docx`, `unittest`, `uv`, script-based workflow under `scripts/`

---

### Task 1: Add Success and Failure Tests

**Files:**
- Modify: `tests/test_init_project.py`
- Modify: `scripts/build_report.py`

**Step 1: Write the failing tests**

Add one test for successful image insertion from a real PNG relative to `docs/report_body.md`, and one test for missing-image fallback plus structured JSON failure reporting.

**Step 2: Run tests to verify they fail**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_inserts_existing_image tests.test_init_project.InitProjectTests.test_build_report_reports_failed_image_insertions -v`
Expected: FAIL because the current implementation only renders a text placeholder and does not report insertion failures.

**Step 3: Write minimal implementation**

Update `scripts/build_report.py` to:
- resolve image paths relative to the Markdown file directory
- insert real images into DOCX when readable
- keep failures non-fatal
- render `[Image Insert Failed] ...` placeholders for failed insertions
- emit inserted/failed image details in the JSON result

**Step 4: Run tests to verify they pass**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_inserts_existing_image tests.test_init_project.InitProjectTests.test_build_report_reports_failed_image_insertions -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_init_project.py scripts/build_report.py
git commit -m "feat: insert markdown images with failure reporting"
```

### Task 2: Full Regression

**Files:**
- Verify only: `tests/test_init_project.py`
- Verify only: `tests/test_confirmation_package.py`
- Verify only: `scripts/build_report.py`

**Step 1: Run targeted image tests**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_inserts_existing_image tests.test_init_project.InitProjectTests.test_build_report_reports_failed_image_insertions -v`
Expected: PASS.

**Step 2: Run full suite**

Run: `uv run -m unittest discover -s tests -v`
Expected: PASS.

**Step 3: Run compile verification**

Run: `uv run python -m py_compile scripts\__init__.py scripts\_shared.py scripts\list_private_fields.py scripts\scan_template.py scripts\build_preview.py scripts\build_report.py scripts\inject_private_fields.py scripts\verify_report.py scripts\cleanup_project.py scripts\init_project.py`
Expected: PASS.

**Step 4: Run workflow verification**

Run: `uv run python scripts\build_report.py --project-root .`
Expected: PASS with image status included in JSON output.

Run: `uv run python scripts\verify_report.py --project-root . --docx out\redacted.docx`
Expected: PASS with no locked-region mismatches.

**Step 5: Commit**

```bash
git add tests/test_init_project.py scripts/build_report.py
git commit -m "feat: improve markdown image handling"
```
