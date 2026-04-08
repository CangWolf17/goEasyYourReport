# AGENTS.md

## Scope and source of truth
- This repo is a **document-first Python workflow skeleton**, not a normal app repo.
- Verified root files now include `README.md`, `LICENSE`, `pyproject.toml`, `requirements.txt`, and `uv.lock`. There is still no verified `package.json`, `Makefile`, CI workflow, or `opencode.json` at the repo root.
- The executable code lives in `scripts/`; `src/` is currently an empty placeholder.
- Trust order: `workflow.json` → `scripts/*.py` → `tests/test_init_project.py` → `INSTALL.md` / `GUARDRAILS.md` / `SKILL.md` → generated files in `logs/` and `out/`.
- Generated artifacts can go stale after a copy/move. In this repo, `logs/init_report.json` and `logs/template_scan.json` still contain absolute paths from the previous location, so rerun the relevant scripts before trusting copied logs.

## Read these first
1. `workflow.json`
2. `INSTALL.md`
3. `GUARDRAILS.md`
4. `tests/test_init_project.py`
5. `tests/test_confirmation_package.py`
6. `scripts/init_project.py`, `scripts/scan_template.py`, `scripts/build_preview.py`, `scripts/build_report.py`, `scripts/inject_private_fields.py`, `scripts/verify_report.py`

## Verified repo facts that are easy to miss
- Default mode is `semi-auto`; project language is `zh-CN` (`workflow.json`).
- The project keeps all working state inside the repo: `docs/`, `templates/`, `config/`, `out/`, `logs/`, `temp/`, `user/`.
- `workflow.json` marks `out/private.docx` as protected and `temp/` + `logs/` as recyclable.
- `scripts/_shared.py` hard-fails document operations if `python-docx` is missing.
- CLI scripts now emit ASCII-safe JSON on stdout via `scripts/_shared.py:emit_json`; UTF-8 stays the file-format contract for repo files and logs.
- `scripts/list_private_fields.py` is the only agent-safe way to inspect private-field **names and availability**. The agent must not read secret values.
- `scripts/inject_private_fields.py` reads secret JSON from `--source` or `REPORT_PRIVATE_SOURCE`, writes `out/private.docx`, and returns non-zero if any required field stays unresolved.
- `scripts/scan_template.py` uses a simple heuristic: everything before the first heading-like paragraph becomes locked `cover`; everything from the first heading onward becomes fillable `body_main`.
- `scripts/build_report.py` is now an orchestrator over `scripts/_report_markdown.py` and `scripts/_report_render.py`; Markdown support currently includes headings, paragraphs, fenced code blocks, lists, simple pipe tables, and images.
- The current code-table implementation passes an explicit width to `add_table(...)`; do not remove that casually.
- `tests/test_init_project.py` hardcodes `D:\Miniconda\python.exe`. If the interpreter changes, the tests need to change too.
- `tests/test_confirmation_package.py` uses `.venv\Scripts\python.exe` and also asserts the presence of `README.md`, `LICENSE`, `pyproject.toml`, and `requirements.txt`.

## Verified commands

### Full regression for this repo
Run from repo root:

```powershell
D:\Miniconda\python.exe -m unittest discover -s tests -v
D:\Miniconda\python.exe -m py_compile scripts\__init__.py scripts\_shared.py scripts\_report_markdown.py scripts\_report_render.py scripts\list_private_fields.py scripts\scan_template.py scripts\build_preview.py scripts\build_report.py scripts\inject_private_fields.py scripts\verify_report.py scripts\cleanup_project.py scripts\init_project.py
```

### Focused workflow commands
```powershell
D:\Miniconda\python.exe scripts\init_project.py --project-root .
D:\Miniconda\python.exe scripts\list_private_fields.py --project-root .
D:\Miniconda\python.exe scripts\scan_template.py --project-root .
D:\Miniconda\python.exe scripts\build_preview.py --project-root .
D:\Miniconda\python.exe scripts\build_report.py --project-root .
D:\Miniconda\python.exe scripts\verify_report.py --project-root . --docx out\redacted.docx
D:\Miniconda\python.exe scripts\inject_private_fields.py --project-root . --source temp\private-fields.sample.json
D:\Miniconda\python.exe scripts\cleanup_project.py --project-root . --temp --logs
```

## Required command order
- Fresh project: `init_project.py` → `list_private_fields.py` → `scan_template.py` → `build_preview.py`
- Normal authoring loop: update `docs/report_body.md` → `build_report.py` → `verify_report.py`
- Private output: `inject_private_fields.py` only after redacted output is correct
- Cleanup is optional and should only touch `temp/` / `logs/`

## Repo-specific guardrails
- Treat this repo as a **project workspace**, not a single-report generator.
- Keep intermediate artifacts unless the user explicitly asks to clean them.
- Do not overwrite `templates/template.user.docx` or `templates/reference.user.docx` silently.
- Do not read or re-open `out/private.docx` in the agent flow.
- If a template scan or preview looks wrong, inspect `config/template.plan.json` and rerun `scan_template.py` before changing generation code.
- If field injection looks wrong, inspect `config/field.binding.json` before touching template logic.
- List/table/image Markdown support is now covered by tests; extend renderer support only with new tests first.

## Cognitive Framework

### Before Responding to Any Complex Task
- Identify what already exists — read files, check context, don't rebuild from scratch
- State your approach in one sentence before executing
- Decompose — break multi-step work into explicit steps
- Verify — after completing work, check it

### Output Quality Rules
- Be opinionated — say what to do first and WHY
- Be specific — name exact files, functions, APIs. Never hand-wave
- Use tables for risks (Risk | Likelihood | Mitigation) and metrics
- End plans with a Key Principle — one sentence core insight
- Match depth to complexity. One-liner for simple. Detailed for complex.

### Problem-Solving Patterns
- Try before asking — come back with answers not questions
- Fail fast, fix fast — if A fails, immediately try B
- Name your tools — exact command/API, not "build the project"
- Catch your own bugs — ask "what could go wrong?" before declaring done

### Context Injection (for sub-agents)
ALWAYS inject:
- Project context — what exists, what stack
- Today's context — what was just built, recent decisions
- Output format rules — tables, word limits, opinions
- Voice — "senior engineer" not "helpful assistant"

### Never Do These
- ❌ "Great question!" / "I'd be happy to help!"
- ❌ Listing options without recommending one
- ❌ Explaining what you're about to do instead of doing it
- ❌ Asking permission for things you can safely try

## How to investigate
- Read the highest-value sources first:
  - `README*`, root manifests, workspace config, lockfiles
  - build, test, lint, formatter, typecheck, and codegen config
  - CI workflows and pre-commit / task runner config
  - existing instruction files (`AGENTS.md`, `CLAUDE.md`, `.cursor/rules/`, `.cursorrules`, `.github/copilot-instructions.md`)
  - repo-local OpenCode config such as `opencode.json`
- If architecture is still unclear after reading config and docs, inspect a small number of representative code files to find the real entrypoints, package boundaries, and execution flow. Prefer reading the files that explain how the system is wired together over random leaf files.
- Prefer executable sources of truth over prose. If docs conflict with config or scripts, trust the executable source and only keep what you can verify.

## What to extract
- exact developer commands, especially non-obvious ones
- how to run a single test, a single package, or a focused verification step
- required command order when it matters, such as `lint -> typecheck -> test`
- monorepo or multi-package boundaries, ownership of major directories, and the real app/library entrypoints
- framework or toolchain quirks: generated code, migrations, codegen, build artifacts, special env loading, dev servers, infra deploy flow
- repo-specific style or workflow conventions that differ from defaults
- testing quirks: fixtures, integration test prerequisites, snapshot workflows, required services, flaky or expensive suites
- important constraints from existing instruction files worth preserving

Good `AGENTS.md` content is usually hard-earned context that took reading multiple files to infer.

## Questions
- Only ask the user questions if the repo cannot answer something important. Use the `question` tool for one short batch at most.
- Good questions:
  - undocumented team conventions
  - branch / PR / release expectations
  - missing setup or test prerequisites that are known but not written down
- Do not ask about anything the repo already makes clear.

## Writing rules
- Include only high-signal, repo-specific guidance such as:
  - exact commands and shortcuts the agent would otherwise guess wrong
  - architecture notes that are not obvious from filenames
  - conventions that differ from language or framework defaults
  - setup requirements, environment quirks, and operational gotchas
  - references to existing instruction sources that matter
- Exclude:
  - generic software advice
  - long tutorials or exhaustive file trees
  - obvious language conventions
  - speculative claims or anything you could not verify
  - content better stored in another file referenced via `opencode.json` `instructions`
- When in doubt, omit.
- Prefer short sections and bullets. If the repo is simple, keep the file simple. If the repo is large, summarize the few structural facts that actually change how an agent should work.
- If `AGENTS.md` already exists at `/`, improve it in place rather than rewriting blindly. Preserve verified useful guidance, delete fluff or stale claims, and reconcile it with the current codebase.
