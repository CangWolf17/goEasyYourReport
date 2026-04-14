---
name: go-easy-your-report
description: Use when an agent needs to initialize or run the goEasyYourReport workspace to build a DOCX report from templates, Markdown body content, and report.task.yaml decisions.
---

# goEasyYourReport

Use this when you need an agent-driven report workspace that turns Markdown + templates + `report.task.yaml` decisions into `preview` / `redacted` / `private` DOCX outputs.

The build path can automatically rescue some problematic source images by generating compatible assets under `temp/generated-images/`, preferring JPEG for photos and keeping PNG only when transparency requires it.

## Quick Start / Default Path

Default path:
1. Read `report.task.yaml` and `workflow.json`.
2. Update the writable inputs:
   - `docs/task_requirements.md`
   - `docs/document_requirements.md`
   - `docs/report_body.md`
   - optional images / evidence under `assets/` or `docs/references/`
3. Run `prepare`.
4. Resolve only true blocking confirmations from `out/preview.summary.json`.
5. Use `status` any time you want a quick view of blocking confirmations vs advisory warnings.
6. Run `ready` to mark the task `ready_to_write`.
7. Run `build`, then `verify`.
8. Run `inject` only after the redacted output passes verification.

```powershell
uv run python scripts\workflow_agent.py prepare --project-root .
uv run python scripts\workflow_agent.py status --project-root .
uv run python scripts\workflow_agent.py ready --project-root .
uv run python scripts\workflow_agent.py build --project-root .
uv run python scripts\workflow_agent.py verify --project-root . --target redacted
```

What usually blocks:
- no fillable regions
- unresolved cover-field bindings that the template actually expects
- `ready_to_write` still false at build time

What usually needs confirmation:
- TOC decisions
- figure / table cross-reference decisions
- bibliography source-mode decisions

What is usually advisory:
- body-only / no-cover tasks with no field candidates
- missing field noise when the task intentionally does not use the cover area
- non-blocking preview warnings that do not invalidate the build path

`status` separates:
- `issues` with `confirmation_required` for real blockers
- `issues` with `decision_required` for non-blocking decisions
- `warnings` for advisory noise

## Common Variants

### Body-only / assignment report
Use the same workflow, but keep the task body-first:
- put the real content in `docs/report_body.md`
- set `report.task.yaml -> decisions.report_profile: body_only`
- disable TOC / references / appendix in `report.task.yaml` when not needed
- treat no-cover / no-fields noise as advisory unless the template truly requires those fields
- still respect the normal `prepare -> build -> verify` path

### External target directory
If the report project lives outside the framework root, start from the framework root and bootstrap the target directly:

```powershell
uv run python scripts\workflow_agent.py bootstrap --project-root F:\path\to\report-project
```

After bootstrap, continue to use the same facade commands against that target:

```powershell
uv run python scripts\workflow_agent.py prepare --project-root F:\path\to\report-project
uv run python scripts\workflow_agent.py build --project-root F:\path\to\report-project
uv run python scripts\workflow_agent.py verify --project-root F:\path\to\report-project --target redacted
```

### Private-field injection
Only do this after the redacted build is verified:

```powershell
uv run python scripts\workflow_agent.py inject --project-root . --source temp\private-fields.sample.json
```

## Agent Guardrails

You can safely control:
- `report.task.yaml` stage, input paths, and high-level decisions
- `docs/task_requirements.md`
- `docs/document_requirements.md`
- `docs/report_body.md`
- template-external materials such as images, references, and evidence packs

Do not:
- delete framework rendering parts to customize behavior
- silently rewrite the `default template`
- read private field values directly or reopen `out/private.docx`

Ask the user only when:
- template structure or field binding meaning is genuinely unclear
- TOC / figure-table cross references / bibliography source mode is still undecided
- private-field source data is missing

## Required Contracts

- `report.task.yaml` is the durable entrypoint and handoff file.
- `Build blocked until report.task.yaml marks the task as ready_to_write.`
- `build` includes a `DOCX integrity gate`; if it fails, expect `docx_integrity_error` and stop before `verify` or `inject`.
- `prepare` / `preview` surface `semantic template scan`, `style-gap confirmation`, `TOC / reference-block detection in preview`, and `semantic style recommendation before build`.
- `TOC is inserted only when detected and confirmed`.
- `figure / table cross-references are a post-processing step`.
- `cross-reference insertion requires user confirmation`.
- `supported equation syntax` is intentionally limited.
- `inline equations render inline, block equations are numbered and cross-referenceable`.
- `bibliography source modes: agent_generate_verified_only, agent_search_and_screen, user_supplied_files`.
- `no reference block in task/template means source-only, not output`.

## Read First When You Need More Than the Fast Path

- `report.task.yaml`
- `workflow.json`
- `INSTALL.md`
- `GUARDRAILS.md`

## Debug / Escape Hatches

Only use these for stage-level debugging:
- `scripts/init_project.py`
- `scripts/list_private_fields.py`
- `scripts/scan_template.py`
- `scripts/build_preview.py`
- `scripts/build_report.py`
- `scripts/verify_report.py`
- `scripts/inject_private_fields.py`
