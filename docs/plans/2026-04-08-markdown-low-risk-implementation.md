# Markdown Low-Risk Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend `build_report.py` to support Markdown lists, simple pipe tables, and image placeholders while preserving the current template-first DOCX workflow.

**Architecture:** Keep the existing hand-rolled block parser and extend it incrementally instead of switching to a full Markdown engine. Parse only a low-risk subset into explicit block records, then render those blocks with `python-docx` using existing template styles where available and deterministic fallbacks where they are not.

**Tech Stack:** Python 3, `python-docx`, `unittest`, `uv`, script-based workflow under `scripts/`

---

### Task 1: Add List Rendering Tests

**Files:**
- Modify: `tests/test_init_project.py`
- Modify: `scripts/build_report.py`

**Step 1: Write the failing test**

Add a workflow test that writes Markdown containing unordered and ordered lists, runs `build_report.py`, and asserts the list text appears as separate paragraphs with list styles when available.

**Step 2: Run test to verify it fails**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_renders_markdown_lists -v`
Expected: FAIL because list items currently collapse into plain paragraph text.

**Step 3: Write minimal implementation**

Extend `markdown_to_blocks()` and `apply_block()` so `- item` and `1. item` lines become `list_item` blocks with `ordered` and `depth` metadata. Render them using `List Bullet` / `List Number` styles when available, otherwise `List Paragraph`.

**Step 4: Run test to verify it passes**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_renders_markdown_lists -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_init_project.py scripts/build_report.py
git commit -m "feat: render markdown lists in report output"
```

### Task 2: Add Simple Table Rendering Tests

**Files:**
- Modify: `tests/test_init_project.py`
- Modify: `scripts/build_report.py`

**Step 1: Write the failing test**

Add a workflow test that writes a simple pipe table, runs `build_report.py`, and asserts a DOCX table with matching cell text appears in `out/redacted.docx`.

**Step 2: Run test to verify it fails**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_renders_simple_pipe_table -v`
Expected: FAIL because the current parser treats table rows as plain paragraphs.

**Step 3: Write minimal implementation**

Teach `markdown_to_blocks()` to recognize a contiguous simple pipe-table block with a header separator row. Render it as a standard DOCX table placed in sequence with other blocks.

**Step 4: Run test to verify it passes**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_renders_simple_pipe_table -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_init_project.py scripts/build_report.py
git commit -m "feat: render simple markdown tables"
```

### Task 3: Add Image Placeholder Rendering Tests

**Files:**
- Modify: `tests/test_init_project.py`
- Modify: `scripts/build_report.py`

**Step 1: Write the failing test**

Add a workflow test that writes Markdown image syntax like `![Architecture](images/arch.png)`, runs `build_report.py`, and asserts a visible placeholder paragraph is inserted into the DOCX output.

**Step 2: Run test to verify it fails**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_renders_image_placeholder -v`
Expected: FAIL because the current parser treats image syntax as plain text.

**Step 3: Write minimal implementation**

Parse Markdown image syntax into an `image_placeholder` block. Render a deterministic placeholder paragraph such as `[Image Placeholder] Architecture (images/arch.png)` and apply `Caption` style when available.

**Step 4: Run test to verify it passes**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_renders_image_placeholder -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_init_project.py scripts/build_report.py
git commit -m "feat: render markdown image placeholders"
```

### Task 4: Full Regression

**Files:**
- Verify only: `tests/test_init_project.py`
- Verify only: `tests/test_confirmation_package.py`
- Verify only: `scripts/build_report.py`

**Step 1: Run targeted Markdown tests**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_renders_markdown_lists tests.test_init_project.InitProjectTests.test_build_report_renders_simple_pipe_table tests.test_init_project.InitProjectTests.test_build_report_renders_image_placeholder -v`
Expected: PASS.

**Step 2: Run full test suite**

Run: `uv run -m unittest discover -s tests -v`
Expected: PASS.

**Step 3: Run compile verification**

Run: `uv run python -m py_compile scripts\__init__.py scripts\_shared.py scripts\list_private_fields.py scripts\scan_template.py scripts\build_preview.py scripts\build_report.py scripts\inject_private_fields.py scripts\verify_report.py scripts\cleanup_project.py scripts\init_project.py`
Expected: PASS.

**Step 4: Run workflow verification**

Run: `uv run python scripts\build_report.py --project-root .`
Expected: PASS with updated `out/redacted.docx`.

Run: `uv run python scripts\verify_report.py --project-root . --docx out\redacted.docx`
Expected: PASS with no locked-region mismatches.

**Step 5: Commit**

```bash
git add tests/test_init_project.py scripts/build_report.py
git commit -m "feat: expand markdown report rendering"
```

## Parallelization Note
- Safe to parallelize: isolated investigation of list styles, table rendering constraints, and image placeholder wording.
- Not safe to parallelize: simultaneous code edits to `scripts/build_report.py`, because all three features share the same parser and render pipeline.
- Recommended execution: one controller implements parser/render changes sequentially, while parallel agents only gather constraints or review after each milestone.
