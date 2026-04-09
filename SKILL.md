# Report Workflow Skill

## Purpose
Use `scripts/workflow_agent.py` as the normal agent-facing entrypoint for this repo. The façade wraps project readiness, preview/build/verify, private injection, and cleanup. Lower-level scripts remain implementation details unless you are debugging a single stage.

## Read First
- `workflow.json`
- `INSTALL.md`
- `GUARDRAILS.md`
- `user/user.md`
- `user/soul.md`
- `config/template.plan.json`
- `config/field.binding.json`

## Façade Contract
Run the workflow with:

```powershell
uv run python scripts\workflow_agent.py <action> --project-root .
```

Stable actions:
- `prepare`: initialize or refresh the workspace, run the semantic template scan, inspect private-field availability, and build the preview confirmation package.
- `preview`: rebuild the preview confirmation package with style-gap confirmation and TOC / reference-block detection in preview.
- `build`: generate `out/redacted.docx`, run a DOCX integrity gate, and report structured code/image issues.
- `verify`: verify a DOCX against the current plan.
- `inject`: create `out/private.docx` from a confirmed redacted build and private source.
- `cleanup`: remove only recyclable artifacts.

Top-level JSON contract:
- `action`
- `status`
- `summary`
- `artifacts`
- `issues`
- `warnings`
- `next_step`

Expected `status` values:
- `ok`
- `needs_user_confirmation`
- `needs_agent_handoff`
- `error`

Return codes:
- `0`: success, no handoff needed.
- `1`: the action completed but the agent must stop for user confirmation or another handoff.
- `2`: the action failed and must be fixed before retrying.

## DOCX Integrity Contract
- `build` success now requires the saved `out/redacted.docx` to pass the repo-owned DOCX integrity gate.
- If the integrity gate fails, the façade returns `status=error` with `kind=docx_integrity_error`.
- Treat `docx_integrity_error` as blocking and stop before `verify` or `inject`.
- Integrity failures are not soft handoffs; fix the DOCX package first, then rerun `build`.

## Semantic Style Contract
- `prepare` and `preview` now include a semantic template scan over style candidates, outline metadata, and semantic block signals.
- Treat style-gap confirmation as a real review gate; do not silently decide missing list semantics or outline semantics in code.
- The preview package must surface TOC / reference-block detection in preview rather than auto-inserting those blocks.
- If a semantic style recommendation is pending, handle that semantic style recommendation before build instead of assuming repo defaults should override the template.

## Code Rendering Contract
- Supported fenced code languages are `python`, `json`, `bash`, `yaml`, `sql`, `javascript`, `typescript`, `c`, `cpp`, and `java`.
- Common aliases are normalized before rendering: `py`, `sh`, `shell`, `yml`, `js`, `ts`, `c++`, `cc`, and `cxx`.
- Supported languages may render with syntax highlighting.
- Plain fenced code blocks render as styled code blocks without language-specific highlighting.
- Unsupported fenced languages must still render as readable styled code blocks in `out/redacted.docx`.
- Unsupported fenced languages must also surface a machine-readable issue with `kind=unsupported_code_language`.
- Failed image insertions must surface `kind=image_insert_failed`.
- If `build` returns `1`, stop before `inject` and ask the user whether to accept the fallback or add support with tests.
- Treat both `unsupported_code_language` and `image_insert_failed` as blocking handoff issues before `inject`.

## Lower-Level Scripts
Use direct scripts only when you need to debug one stage, probe a specific behavior, or the façade is unavailable.
- `scripts/init_project.py`
- `scripts/list_private_fields.py` - only agent-safe way to inspect private-field names and availability
- `scripts/scan_template.py`
- `scripts/build_preview.py`
- `scripts/build_report.py`
- `scripts/verify_report.py`
- `scripts/inject_private_fields.py`
- `scripts/cleanup_project.py`

## Guardrails
- Do not read or reopen `out/private.docx`.
- Do not overwrite user templates silently.
- Do not treat preview generation as completion.
- Do not inject private values until the build handoff is cleared.
