# AGENTS.md

## Scope and source of truth
- This repo is a document-first Python workflow skeleton, not a normal app repo.
- Normal agent-facing entrypoint is `scripts/workflow_agent.py`. Use it for prepare, preview, build, verify, inject, and cleanup.
- Lower-level scripts in `scripts/` are implementation details. Use them directly only for stage-level debugging, bootstrap work, or when a task explicitly targets that script.
- Verified root files now include `README.md`, `LICENSE`, `pyproject.toml`, `requirements.txt`, and `uv.lock`. There is still no verified `package.json`, `Makefile`, CI workflow, or `opencode.json` at the repo root.
- The executable code lives in `scripts/`; `src/` is currently an empty placeholder.
- Trust order: `workflow.json` -> `scripts/workflow_agent.py` -> `scripts/*.py` -> `tests/test_init_project.py` -> `INSTALL.md` / `GUARDRAILS.md` / `SKILL.md` -> generated files in `logs/` and `out/`.
- Generated artifacts can go stale after a copy/move. In this repo, `logs/init_report.json` and `logs/template_scan.json` still contain absolute paths from the previous location, so rerun the relevant scripts before trusting copied logs.

## Read these first
1. `workflow.json`
2. `INSTALL.md`
3. `GUARDRAILS.md`
4. `tests/test_init_project.py`
5. `tests/test_confirmation_package.py`
6. `scripts/workflow_agent.py`
7. `scripts/init_project.py`, `scripts/scan_template.py`, `scripts/build_preview.py`, `scripts/build_report.py`, `scripts/inject_private_fields.py`, `scripts/verify_report.py`

## Workflow Agent Contract
- Use `prepare` to refresh the workspace state. It covers initialization when needed, semantic template scan, private-field inspection, and preview rebuild.
- Use `preview` to rebuild the confirmation package with style-gap confirmation and TOC / reference-block detection in preview.
- Use `build` to generate `out/redacted.docx`, run a DOCX integrity gate, and surface render issues.
- Use `verify` to check a DOCX against the current plan.
- Use `inject` only after the build result is clean or the user has explicitly accepted any handoff.
- Use `cleanup` only for recyclable artifacts.
- The façade must emit JSON with `action`, `status`, `summary`, `artifacts`, `issues`, `warnings`, and `next_step`.
- Return codes: `0` success, `1` handoff, `2` error.
- Build success now requires a valid DOCX package; if the integrity gate fails, return `kind=docx_integrity_error` and stop before `verify` or `inject`.
- Respect the repo semantic workflow: task/template decisions come first, repo defaults only apply when the task book and template leave the choice unspecified.
- Unsupported fenced code languages must still render as styled fallbacks, but they must be reported as `kind=unsupported_code_language` and treated as a handoff before `inject`.
- Failed image insertions must be reported as `kind=image_insert_failed` and treated as a handoff before `inject`.
- Do not key automation on raw `build_report.py` output when the façade is available.

## Verified repo facts that are easy to miss
- Default mode is `semi-auto`; project language is `zh-CN` (`workflow.json`).
- The project keeps all working state inside the repo: `docs/`, `templates/`, `config/`, `out/`, `logs/`, `temp/`, `user/`.
- `workflow.json` marks `out/private.docx` as protected and `temp/` + `logs/` as recyclable.
- `scripts/_shared.py` hard-fails document operations if `python-docx` is missing.
- CLI scripts now emit ASCII-safe JSON on stdout via `scripts/_shared.py:emit_json`; UTF-8 stays the file-format contract for repo files and logs.
- `scripts/list_private_fields.py` is the only agent-safe way to inspect private-field names and availability. The agent must not read secret values.
- `scripts/inject_private_fields.py` reads secret JSON from `--source` or `REPORT_PRIVATE_SOURCE`, writes `out/private.docx`, and returns non-zero if any required field stays unresolved.
- `scripts/scan_template.py` uses a simple heuristic: everything before the first heading-like paragraph becomes locked `cover`; everything from the first heading onward becomes fillable `body_main`.
- `scripts/build_report.py` is now an orchestrator over `scripts/_report_markdown.py` and `scripts/_report_render.py`; Markdown support currently includes headings, paragraphs, fenced code blocks, lists, simple pipe tables, and images.
- `scripts/build_report.py` now validates the saved package with the repo-owned DOCX integrity gate before reporting success.
- `scripts/scan_template.py` now performs a semantic template scan and persists style candidates, style gaps, outline completeness, and TOC / reference-block signals into `config/template.plan.json`.
- `scripts/build_preview.py` now surfaces style-gap confirmation and semantic style recommendation before build; it does not silently resolve unresolved list semantics or TOC policy.
- TOC is inserted only when detected and confirmed; if `semantics.toc.needs_confirmation` is still true, `workflow_agent.py build` must stop for review instead of silently building through it.
- figure / table cross-references are a post-processing step over explicit placeholder tokens such as `[[REF:figure:fig_0001]]` and `[[REF:table:tbl_0001]]`.
- cross-reference insertion requires user confirmation; keep `semantics.cross_references.figure_table_enabled` unresolved until the user or upstream task explicitly decides it.
- supported equation syntax is intentionally narrow in v1: letters, digits, parentheses, `+ - * / =`, superscripts, subscripts, `\frac`, `\sqrt`, and common Greek letters.
- inline equations render inline, block equations are numbered and cross-referenceable via `eq_0001`-style bookmarks.
- bibliography source modes: agent_generate_verified_only, agent_search_and_screen, user_supplied_files.
- no reference block in task/template means source-only, not output; do not silently emit a bibliography block when the task or template does not reserve one.
- `scripts/_docx_integrity.py` owns ZIP/XML/relationship validation; `scripts/_docx_xml.py` is the whitelist for shared low-level DOCX XML helpers.
- The current code-table implementation passes an explicit width to `add_table(...)`; do not remove that casually.
- `tests/test_init_project.py` hardcodes `D:\Miniconda\python.exe`. If the interpreter changes, the tests need to change too.
- `tests/test_confirmation_package.py` uses `.venv\Scripts\python.exe` and also asserts the presence of `README.md`, `LICENSE`, `pyproject.toml`, and `requirements.txt`.

## Normal Workflow Commands
```powershell
D:\Miniconda\python.exe scripts\workflow_agent.py prepare --project-root .
D:\Miniconda\python.exe scripts\workflow_agent.py preview --project-root .
D:\Miniconda\python.exe scripts\workflow_agent.py build --project-root .
D:\Miniconda\python.exe scripts\workflow_agent.py verify --project-root . --target redacted
D:\Miniconda\python.exe scripts\workflow_agent.py inject --project-root . --source temp\private-fields.sample.json
D:\Miniconda\python.exe scripts\workflow_agent.py cleanup --project-root . --temp --logs
```

## Full Regression for This Repo
Run from repo root:

```powershell
D:\Miniconda\python.exe -m unittest discover -s tests -v
D:\Miniconda\python.exe -m py_compile scripts\__init__.py scripts\_shared.py scripts\_docx_integrity.py scripts\_docx_xml.py scripts\_report_markdown.py scripts\_report_render.py scripts\workflow_agent.py scripts\list_private_fields.py scripts\scan_template.py scripts\build_preview.py scripts\build_report.py scripts\inject_private_fields.py scripts\verify_report.py scripts\cleanup_project.py scripts\init_project.py scripts\recommend_template_styles.py
```

## Required command order
- Fresh project: `workflow_agent.py prepare`
- Normal authoring loop: update `docs/report_body.md` -> `workflow_agent.py build` -> `workflow_agent.py verify`
- Private output: `workflow_agent.py inject` only after the build result is `0` and any handoff issue is resolved with the user
- If `workflow_agent.py build` returns `kind=docx_integrity_error`, treat it as a hard stop before `verify` or `inject`
- Cleanup is optional and should only touch `temp/` / `logs/`

## Repo-specific guardrails
- Treat this repo as a project workspace, not a single-report generator.
- Keep intermediate artifacts unless the user explicitly asks to clean them.
- Do not overwrite `templates/template.user.docx` or `templates/reference.user.docx` silently.
- Do not read or re-open `out/private.docx` in the agent flow.
- If a template scan or preview looks wrong, inspect `config/template.plan.json` and rerun `scan_template.py` before changing generation code.
- If field injection looks wrong, inspect `config/field.binding.json` before touching template logic.
- List/table/image Markdown support is now covered by tests; extend renderer support only with new tests first.
- When the façade reports `kind=unsupported_code_language`, stop before `inject` and get user confirmation about the fallback or a renderer update.
