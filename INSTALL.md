# Report Skill Installation

## Purpose
Treat this repo as a reusable, agent-driven report framework rather than a one-off workflow script bundle.

The framework layer owns template scan, semantic planning, preview, redacted build, private injection, and verification. Agents consume high-level inputs and durable workspace state; they should not improvise around low-level rendering internals.

## Host Requirements
- Python `>=3.11`
- `uv` available for environment setup
- local filesystem access to the workspace
- a DOCX-capable host environment

Install dependencies from the repo root:

```powershell
uv sync
```

## Installation Contract
Any agent using this repo must follow these rules:

1. Keep the repo as a whole workspace. Do not extract only one script.
2. Preserve the repo layout under `user/`, `templates/`, `config/`, `docs/`, `out/`, `logs/`, and `temp/`.
3. Treat `scripts/workflow_agent.py` as the stable façade.
4. Treat lower-level scripts in `scripts/` as implementation details unless a task explicitly requires stage-level debugging.
5. Treat `report.task.yaml` as the workspace entrypoint and `workflow.json` as the framework runtime contract.

## Read Order For A New Agent
Before taking action, read these files in order:

1. `report.task.yaml`
2. `workflow.json`
3. `INSTALL.md`
4. `GUARDRAILS.md`
5. `SKILL.md`
6. `user/user.md`
7. `user/soul.md`
8. `config/template.plan.json`
9. `config/field.binding.json`

## Bootstrap Contract
When an agent enters a fresh workspace, bootstrap it like this:

1. Check whether `workflow.json` exists.
2. If the repo is already present as a framework workspace, run:

```powershell
uv run python scripts/workflow_agent.py prepare --project-root .
```

3. If the target workspace is new and does not yet contain the expected state files, run:

```powershell
uv run python scripts/init_project.py --project-root .
uv run python scripts/workflow_agent.py prepare --project-root .
```

4. Confirm these state files exist after bootstrap:
   - `report.task.yaml`
   - `user/user.md`
   - `user/soul.md`
   - `config/template.plan.json`
   - `config/field.binding.json`
5. Confirm the main template exists:
   - `templates/template.user.docx`
6. Treat `templates/reference.user.docx` as optional style support, not a structural requirement.

## Workspace Contract
`report.task.yaml` is the durable entrypoint for agent handoff. It records:

- task stage and `ready_to_write`
- requirements and input paths
- high-level report decisions
- runtime links to framework state and output artifacts

The default template is a protected baseline. Agents may set high-level decisions in `report.task.yaml`, but they should not rewrite the default template or user template silently.

## Stable Agent Interface
Run the framework through:

```powershell
uv run python scripts/workflow_agent.py <action> --project-root .
```

Stable actions:
- `prepare`
- `preview`
- `build`
- `verify`
- `inject`
- `cleanup`

Stable JSON fields:
- `action`
- `status`
- `summary`
- `artifacts`
- `issues`
- `warnings`
- `next_step`

Return codes:
- `0`: success, no handoff required
- `1`: action completed but user confirmation or agent handoff is required
- `2`: blocking failure

## Ready-To-Write Gate
- `workflow_agent.py build` now enforces the `ready_to_write` gate.
- Build blocked until `report.task.yaml` marks the task as `ready_to_write`.
- Agents should finish material collection and unresolved confirmations before formal report generation.
- The gate protects the framework from drafting against incomplete evidence or unresolved document contracts.

## First-Session Flow
The first useful agent interaction should look like this:

1. Bootstrap the workspace.
2. Run `prepare`.
3. Present one bundled review package based on:
   - preview artifact
   - locked regions
   - fillable regions
   - field bindings
   - private-field availability
   - style-gap and semantic recommendations
4. Resolve only the decisions that actually block build quality.
5. Mark `report.task.yaml` ready only when the task is genuinely ready_to_write.
6. Proceed to `build`, then `verify`, then `inject` only when the redacted path is clean.

## Privacy And Template Rules
- Do not read private field values directly.
- Use `scripts/list_private_fields.py` only for field names and availability.
- Inject secrets only through `scripts/workflow_agent.py inject` or `scripts/inject_private_fields.py --source ...`.
- Do not reopen or inspect `out/private.docx` in automation.
- Keep intermediate artifacts unless the user explicitly asks to clean them.
- Do not overwrite user templates silently.
- Do not rewrite the default template as part of routine agent execution.

## Summary
Install and use this repo as:

- a persistent workspace
- an agent-driven report framework
- a stateful report generation system with a stable façade

Not as:

- a single-shot DOCX generator
- a loose script collection
- a secret-reading automation tool
