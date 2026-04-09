# goEasyYourReport

Document-first Python workflow skeleton for generating reviewable DOCX reports from a template, Markdown body content, and private field bindings.

## What This Repo Does

- scans a DOCX template into locked and fillable regions
- runs a semantic template scan, then builds `preview.docx` plus `preview.summary.json` for confirmation
- builds `redacted.docx` from `docs/report_body.md`
- injects private fields into `out/private.docx`
- verifies locked-region preservation before private output

Current Markdown support includes:
- headings and paragraphs
- styled code blocks with a light printable theme
- syntax highlighting for `python`, `json`, `bash`, `yaml`, `sql`, `javascript`, `typescript`, `c`, `cpp`, and `java`
- alias normalization for `py`, `sh`, `shell`, `yml`, `js`, `ts`, `c++`, `cc`, and `cxx`
- lists
- simple pipe tables
- image insertion with failure reporting

## Setup

This repo uses `uv` for environment management.

```powershell
uv sync
```

## Agent Entry Point

Use `scripts/workflow_agent.py` for normal agent work. It is the stable façade over the lower-level workflow scripts.

Stable actions:
- `prepare` refreshes the workspace, runs the semantic template scan, inspects private fields, and rebuilds the preview package.
- `preview` rebuilds preview artifacts for confirmation, including style-gap confirmation and TOC / reference-block detection in preview.
- `build` generates `out/redacted.docx`, runs a DOCX integrity gate, and emits structured code/image issues.
- `verify` checks a DOCX against the current plan.
- `inject` creates `out/private.docx` from confirmed private data.
- `cleanup` removes only recyclable artifacts.

The façade prints JSON with `action`, `status`, `summary`, `artifacts`, `issues`, `warnings`, and `next_step`.

Return codes:
- `0` means success and you can continue.
- `1` means the action finished but the agent must stop for user confirmation or another handoff.
- `2` means the action failed and needs troubleshooting.

Build success now requires a valid DOCX package. If the DOCX integrity gate fails, the façade returns `kind=docx_integrity_error` and the agent must stop before `verify` or `inject`.

Before build, the workflow may also stop for semantic style recommendation before build if the template is missing required semantic styles or outline metadata.

Run it with:

```powershell
uv run python scripts\workflow_agent.py prepare --project-root .
uv run python scripts\workflow_agent.py build --project-root .
uv run python scripts\workflow_agent.py verify --project-root . --target redacted
```

Inject private fields only after `build` and `verify` both succeed without handoff:

```powershell
uv run python scripts\workflow_agent.py inject --project-root . --source temp\private-fields.sample.json
```

## Important Behavior

- `preview.docx` is for confirmation, not final delivery.
- `build` does not count as successful unless `out/redacted.docx` passes the repo-owned DOCX integrity gate.
- `docx_integrity_error` is a blocking error, not a soft handoff; fix it before `verify` or `inject`.
- The preview package includes a semantic template scan, style-gap confirmation, and TOC / reference-block detection in preview.
- TOC is inserted only when detected and confirmed. If template scan finds a TOC placeholder or field and confirmation is unresolved, review `out/preview.summary.json` before running through build.
- figure / table cross-references are a post-processing step driven by explicit placeholders such as `[[REF:figure:fig_0001]]`, `[[REF:figure:fig_0001|见下图]]`, `[[REF:table:tbl_0001]]`, and `[[REF:table:tbl_0001|见上表]]`.
- cross-reference insertion requires user confirmation; the repo will not silently turn on figure/table reference replacement just because placeholders are present.
- supported equation syntax in v1 is limited to letters, digits, parentheses, `+ - * / =`, superscripts, subscripts, `\frac{...}{...}`, `\sqrt{...}`, and common Greek letters such as `\alpha`.
- inline equations render inline, block equations are numbered and cross-referenceable.
- bibliography source modes: agent_generate_verified_only, agent_search_and_screen, user_supplied_files.
- no reference block in task/template means source-only, not output.
- Repo defaults apply only when the task book and the selected template do not already specify the semantic style choice.
- Unsupported fenced code languages still render as styled fallback blocks, but they are reported as `kind=unsupported_code_language` and require handoff before private injection.
- Image insertion failures are surfaced as `kind=image_insert_failed` and also require handoff before private injection.
- Do not read `out/private.docx` in agent automation flows.
- The façade is the normal agent entrypoint; the lower-level scripts remain implementation details.

## Lower-Level Scripts

Use direct scripts only when you are debugging a single stage or intentionally reproducing a lower-level issue:
- `scripts/init_project.py`
- `scripts/list_private_fields.py`
- `scripts/scan_template.py`
- `scripts/build_preview.py`
- `scripts/build_report.py`
- `scripts/verify_report.py`
- `scripts/inject_private_fields.py`
- `scripts/cleanup_project.py`

## License

MIT. See `LICENSE`.
