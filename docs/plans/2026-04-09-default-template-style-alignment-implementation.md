# Default Template Style Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship a sanitized built-in default template derived from the large-style template and align generated DOCX output with its title, body, figure, table, and reference styles.

**Architecture:** Replace the generic sample-template generator with a stored sanitized DOCX asset, then update the render layer to prefer template-native Chinese style names and add explicit figure/table caption formatting. Keep private field injection on the existing binding-based flow, and keep code blocks on the current custom table renderer.

**Tech Stack:** Python 3, `python-docx`, `unittest`, `uv`, JSON config files, script-based workflow under `scripts/`

---

### Task 1: Add the Sanitized Default Template Asset

**Files:**
- Create: `templates/template.sample.docx`
- Possibly update: `templates/reference.sample.docx`
- Modify: `scripts/init_project.py`
- Test: `tests/test_init_project.py`

**Step 1: Write the failing test**

Add a test asserting that `init_project.py` without `--template` produces `template.sample.docx` / `template.user.docx` whose visible title is `报告题目 / Report Title` and whose cover anchor labels include `姓 名：`, `学 号：`, and `完成日期：`.

**Step 2: Run test to verify it fails**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_init_project_uses_sanitized_default_template -v`
Expected: FAIL because the current sample generator still produces the generic English template.

**Step 3: Write minimal implementation**

- Add the sanitized default template asset under `templates/`
- Update `init_project.py` so the built-in sample copy path prefers the stored asset instead of generating the old generic sample
- Preserve existing behavior when the user passes `--template`

**Step 4: Run test to verify it passes**

Run the same test again.
Expected: PASS.

### Task 2: Add Style-Mapped Heading and Body Rendering

**Files:**
- Modify: `scripts/_report_render.py`
- Test: `tests/test_init_project.py`

**Step 1: Write the failing test**

Add a test building a report from Markdown headings and paragraphs, then assert the rendered paragraphs use `标题2`, `标题3`, `标题4`, and `正文` when those styles exist.

**Step 2: Run test to verify it fails**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_prefers_template_native_body_styles -v`
Expected: FAIL because the renderer still prefers generic `Heading N` styles and leaves body paragraphs unstylized.

**Step 3: Write minimal implementation**

- Add style-preference mapping helpers to `_report_render.py`
- Prefer Chinese template-native names before generic Word names
- Apply `正文` to normal paragraphs when available

**Step 4: Run test to verify it passes**

Run the same test again.
Expected: PASS.

### Task 3: Add Figure Caption and Placement Rules

**Files:**
- Modify: `scripts/_report_markdown.py`
- Modify: `scripts/_report_render.py`
- Test: `tests/test_init_project.py`

**Step 1: Write the failing test**

Add a test for a Markdown image asserting:
- the picture is centered
- the caption is below the figure
- the caption uses `图题`

**Step 2: Run test to verify it fails**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_renders_centered_figure_with_caption_below -v`
Expected: FAIL because successful images currently have no centering or caption paragraph.

**Step 3: Write minimal implementation**

- Extend image blocks to carry numbering/caption text
- Center the picture paragraph
- Emit a caption paragraph below using `图题`
- Keep image failure reporting behavior intact

**Step 4: Run test to verify it passes**

Run the same test again.
Expected: PASS.

### Task 4: Add Table Caption and Cell Paragraph Formatting

**Files:**
- Modify: `scripts/_report_markdown.py`
- Modify: `scripts/_report_render.py`
- Test: `tests/test_init_project.py`

**Step 1: Write the failing test**

Add a test for a Markdown table asserting:
- the caption is above the table
- the caption uses `表题`
- the table is centered
- cell paragraphs have no first-line indent
- cell paragraphs use 1.5 line spacing

**Step 2: Run test to verify it fails**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_renders_centered_table_with_caption_and_cell_formatting -v`
Expected: FAIL because the current table renderer only writes plain cell text.

**Step 3: Write minimal implementation**

- Add table caption support in the Markdown/render path
- Apply centered alignment to the table
- Normalize all cell paragraphs to no first-line indent and 1.5 line spacing
- Prefer the template's table style when present

**Step 4: Run test to verify it passes**

Run the same test again.
Expected: PASS.

### Task 5: Add Reference Style Alignment

**Files:**
- Modify: `scripts/_report_render.py`
- Test: `tests/test_init_project.py`

**Step 1: Write the failing test**

Add a test that places a `## 参考文献` section in Markdown with one or more `[1] ...` entries and asserts the entries use the `参考文献` style.

**Step 2: Run test to verify it fails**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_applies_reference_style_in_reference_section -v`
Expected: FAIL because references currently render as generic paragraphs.

**Step 3: Write minimal implementation**

- Detect entry paragraphs under a references heading
- Apply `参考文献` when available
- Keep source text untouched; do not implement full GB/T formatting in this task

**Step 4: Run test to verify it passes**

Run the same test again.
Expected: PASS.

### Task 6: Preserve Cover Field Injection Targets

**Files:**
- Modify: `scripts/init_project.py`
- Modify: `scripts/inject_private_fields.py`
- Test: `tests/test_init_project.py`

**Step 1: Write the failing test**

Add a test asserting the default initialized template remains injectable for `full_name`, `student_id`, and `completion_date`, and that injection still succeeds against the redacted output.

**Step 2: Run test to verify it fails**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_private_field_injection_works_with_sanitized_default_template -v`
Expected: FAIL if the new template asset or fallback logic breaks the anchor-based injector.

**Step 3: Write minimal implementation**

- Ensure the sanitized default template includes or reliably preserves the configured cover anchors
- Only if necessary, add minimal fallback logic so missing configured anchors can be created before injection

**Step 4: Run test to verify it passes**

Run the same test again.
Expected: PASS.

### Task 7: Full Regression

**Files:**
- Verify only: `tests/test_init_project.py`
- Verify only: `tests/test_confirmation_package.py`
- Verify only: `scripts/*.py`

**Step 1: Run targeted tests**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_init_project_uses_sanitized_default_template tests.test_init_project.InitProjectTests.test_build_report_prefers_template_native_body_styles tests.test_init_project.InitProjectTests.test_build_report_renders_centered_figure_with_caption_below tests.test_init_project.InitProjectTests.test_build_report_renders_centered_table_with_caption_and_cell_formatting tests.test_init_project.InitProjectTests.test_build_report_applies_reference_style_in_reference_section tests.test_init_project.InitProjectTests.test_private_field_injection_works_with_sanitized_default_template -v`
Expected: PASS.

**Step 2: Run full suite**

Run: `uv run -m unittest discover -s tests -v`
Expected: PASS.

**Step 3: Run compile verification**

Run: `uv run python -m py_compile scripts\__init__.py scripts\_shared.py scripts\_report_markdown.py scripts\_report_render.py scripts\workflow_agent.py scripts\list_private_fields.py scripts\scan_template.py scripts\build_preview.py scripts\build_report.py scripts\inject_private_fields.py scripts\verify_report.py scripts\cleanup_project.py scripts\init_project.py`
Expected: PASS.
