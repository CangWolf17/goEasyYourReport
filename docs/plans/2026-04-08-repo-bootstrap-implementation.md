# Repo Bootstrap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a repo-level README and MIT license, then initialize git without creating commits.

**Architecture:** Treat this as a minimal repository bootstrap. Validate the presence and contents of the root documentation files with tests first, then add the files, then initialize git as a final non-destructive workspace step.

**Tech Stack:** Python 3, `unittest`, `uv`, Markdown, Git

---

### Task 1: Add Root Documentation Tests

**Files:**
- Modify: `tests/test_confirmation_package.py`

**Step 1: Write the failing test**

Add tests asserting:
- `README.md` exists at repo root and mentions `uv`, `build_report.py`, and `preview`
- `LICENSE` exists and contains the standard MIT grant text

**Step 2: Run test to verify it fails**

Run: `uv run -m unittest tests.test_confirmation_package -v`
Expected: FAIL because the root files do not exist yet.

**Step 3: Write minimal implementation**

No implementation in this task; move directly to Task 2 after confirming red.

**Step 4: Run test to verify it passes**

Covered in Task 2.

**Step 5: Commit**

```bash
git add tests/test_confirmation_package.py README.md LICENSE
git commit -m "docs: add repository bootstrap files"
```

### Task 2: Add README and MIT License

**Files:**
- Create: `README.md`
- Create: `LICENSE`

**Step 1: Write minimal implementation**

Create a concise README covering purpose, setup, key commands, current feature boundaries, and license. Create a standard MIT license file.

**Step 2: Run tests to verify they pass**

Run: `uv run -m unittest tests.test_confirmation_package -v`
Expected: PASS.

**Step 3: Commit**

Only if later requested.

### Task 3: Initialize Git

**Files:**
- No file edits required

**Step 1: Verify git is not already initialized**

Run: `git rev-parse --is-inside-work-tree`
Expected: nonzero / not a git repository.

**Step 2: Initialize git**

Run: `git init -b main`
Expected: repository initialized in current workspace.

**Step 3: Verify status**

Run: `git status --short`
Expected: shows current files as untracked/modified, no commit created.

### Task 4: Full Verification

**Files:**
- Verify only: `tests/test_confirmation_package.py`
- Verify only: root repo files

**Step 1: Run focused docs test suite**

Run: `uv run -m unittest tests.test_confirmation_package -v`
Expected: PASS.

**Step 2: Run full suite**

Run: `uv run -m unittest discover -s tests -v`
Expected: PASS.

**Step 3: Report git state**

Run: `git status --short`
Expected: repo initialized, no commit created.
