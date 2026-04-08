# Styled Code Blocks Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add styled, printable, multi-language code blocks with light-theme defaults, JSON theme overrides, and mandatory agent handoff for unsupported languages.

**Architecture:** Preserve the current explicit-width `1x1` code table in `scripts/build_report.py`, then add header styling, semantic role coloring, supported-language alias normalization, and structured `code_blocks` status reporting. Keep unsupported-language behavior visible and actionable by returning a nonzero exit code while still generating a styled plain fallback.

**Tech Stack:** Python 3, `python-docx`, `Pygments`, `unittest`, `uv`, JSON config files, script-based workflow under `scripts/`

---

### Task 1: Add Theme and Dependency Surface

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Modify: `workflow.json`
- Modify: `scripts/init_project.py`
- Create: `config/code-theme.user.sample.json`
- Test: `tests/test_confirmation_package.py`

**Step 1: Write the failing test**

Add a test asserting the initialized project includes the code-theme sample file and the repo declares the syntax-highlighting dependency.

**Step 2: Run test to verify it fails**

Run: `uv run -m unittest tests.test_confirmation_package -v`
Expected: FAIL because the sample config and dependency are not present yet.

**Step 3: Write minimal implementation**

- Add `Pygments` to `pyproject.toml` and `requirements.txt`
- Add `rendering.code_blocks.theme` and `rendering.code_blocks.theme_override` to `workflow.json`
- Copy `config/code-theme.user.sample.json` during project init

**Step 4: Run test to verify it passes**

Run: `uv run -m unittest tests.test_confirmation_package -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add pyproject.toml requirements.txt workflow.json scripts/init_project.py config/code-theme.user.sample.json tests/test_confirmation_package.py
git commit -m "chore: add code-block theme configuration"
```

### Task 2: Add Styled Plain Code-Block Rendering

**Files:**
- Modify: `scripts/build_report.py`
- Test: `tests/test_init_project.py`

**Step 1: Write the failing test**

Add a workflow test for fenced code with no language that asserts:
- build succeeds
- code still renders inside a single-cell table
- a visible `Code` header is present

**Step 2: Run test to verify it fails**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_renders_styled_plain_code_block -v`
Expected: FAIL because current code blocks have no header or theme styling.

**Step 3: Write minimal implementation**

Capture fence info strings in `markdown_to_blocks()`. Render a light-theme code block with a header label, but no highlighting when no language is specified.

**Step 4: Run test to verify it passes**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_renders_styled_plain_code_block -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/build_report.py tests/test_init_project.py
git commit -m "feat: style plain fenced code blocks"
```

### Task 3: Add Supported-Language Highlighting

**Files:**
- Modify: `scripts/build_report.py`
- Test: `tests/test_init_project.py`

**Step 1: Write the failing tests**

Add tests for supported languages:
- `python`
- `bash`
- `json`
- `c`
- `cpp`
- `java`

Each should assert build success, language header presence, and structured `code_blocks.highlighted` counts.

**Step 2: Run tests to verify they fail**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_highlights_python_code tests.test_init_project.InitProjectTests.test_build_report_highlights_cpp_code tests.test_init_project.InitProjectTests.test_build_report_highlights_java_code -v`
Expected: FAIL because highlighting metadata and styling are not implemented yet.

**Step 3: Write minimal implementation**

- Normalize language aliases
- Restrict highlighting to the supported whitelist
- Use `Pygments` lexers for supported languages
- Map tokens into semantic color roles and render runs in the DOCX code cell

**Step 4: Run tests to verify they pass**

Run the same tests again.
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/build_report.py tests/test_init_project.py
git commit -m "feat: highlight supported code languages"
```

### Task 4: Add Unsupported-Language Agent Handoff

**Files:**
- Modify: `scripts/build_report.py`
- Test: `tests/test_init_project.py`

**Step 1: Write the failing test**

Add a workflow test for unsupported language, such as `rust`, asserting:
- redacted output is still generated
- the code block stays styled
- stdout JSON contains `code_blocks.unsupported`
- process exits nonzero

**Step 2: Run test to verify it fails**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_requires_agent_handoff_for_unsupported_language -v`
Expected: FAIL because unsupported language handoff is not enforced.

**Step 3: Write minimal implementation**

Add structured unsupported-language reporting and return nonzero when unsupported code languages are present.

**Step 4: Run test to verify it passes**

Run the same test again.
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/build_report.py tests/test_init_project.py
git commit -m "feat: require agent handoff for unsupported code languages"
```

### Task 5: Add Theme Override Support

**Files:**
- Modify: `scripts/build_report.py`
- Test: `tests/test_init_project.py`

**Step 1: Write the failing test**

Add a workflow test that writes `config/code-theme.user.json`, points `workflow.json` at it, and asserts the build uses the override according to structured output.

**Step 2: Run test to verify it fails**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_applies_code_theme_override -v`
Expected: FAIL because override loading is not implemented.

**Step 3: Write minimal implementation**

- Add built-in `github-light` theme constants
- Load optional override JSON
- Merge only supported semantic roles
- Fall back to the built-in theme and emit warnings if override loading fails

**Step 4: Run test to verify it passes**

Run the same test again.
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/build_report.py tests/test_init_project.py
git commit -m "feat: support code theme overrides"
```

### Task 6: Full Regression

**Files:**
- Verify only: `tests/test_init_project.py`
- Verify only: `tests/test_confirmation_package.py`
- Verify only: `scripts/*.py`

**Step 1: Run targeted code-block tests**

Run: `uv run -m unittest tests.test_init_project.InitProjectTests.test_build_report_renders_styled_plain_code_block tests.test_init_project.InitProjectTests.test_build_report_highlights_python_code tests.test_init_project.InitProjectTests.test_build_report_highlights_cpp_code tests.test_init_project.InitProjectTests.test_build_report_highlights_java_code tests.test_init_project.InitProjectTests.test_build_report_requires_agent_handoff_for_unsupported_language tests.test_init_project.InitProjectTests.test_build_report_applies_code_theme_override -v`
Expected: PASS.

**Step 2: Run full suite**

Run: `uv run -m unittest discover -s tests -v`
Expected: PASS.

**Step 3: Run compile verification**

Run: `uv run python -m py_compile scripts\__init__.py scripts\_shared.py scripts\list_private_fields.py scripts\scan_template.py scripts\build_preview.py scripts\build_report.py scripts\inject_private_fields.py scripts\verify_report.py scripts\cleanup_project.py scripts\init_project.py`
Expected: PASS.

**Step 4: Run workflow verification**

Run: `uv run python scripts\build_report.py --project-root .`
Expected: PASS for supported languages, or nonzero with `code_blocks.unsupported` for unsupported ones.

Run: `uv run python scripts\verify_report.py --project-root . --docx out\redacted.docx`
Expected: PASS with no locked-region mismatches.

**Step 5: Commit**

```bash
git add tests/test_init_project.py tests/test_confirmation_package.py scripts/build_report.py workflow.json pyproject.toml requirements.txt scripts/init_project.py config/code-theme.user.sample.json
git commit -m "feat: add styled multi-language code blocks"
```
