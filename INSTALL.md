# Report Workflow Installation

## Purpose
Initialize a semi-automatic report workflow project that preserves the full project lifecycle: code, tests, assets, body source, templates, previews, redacted outputs, and private outputs.

## First-Run Contract
The agent must treat this directory as a project, not as a single report output folder.

On first run the agent must:
1. Check whether `workflow.json` exists.
2. If missing, run `scripts/init_project.py --project-root .`.
3. Ensure these files exist:
   - `user/user.md`
   - `user/soul.md`
   - `config/template.plan.json`
   - `config/field.binding.json`
4. Ensure the user template files exist:
   - `templates/template.user.docx`
   - `templates/reference.user.docx` (optional)
5. Run `scripts/list_private_fields.py` to get field names and availability only.
6. Run `scripts/scan_template.py` to inspect the main template structure.
7. Run `scripts/build_preview.py` to generate `out/preview.docx` when a template is available.
8. Present one bundled confirmation package to the user:
   - recommended template
   - locked regions
   - fillable regions
   - field bindings
   - private field availability

## Agent Rules
- Do not read private field values.
- You may read field names and availability only.
- Treat `user/user.md` and `user/soul.md` as editable user preference files.
- Keep intermediate artifacts unless the user explicitly asks to clean them.
- Do not overwrite user templates without explicit confirmation.

## Expected Questions
Ask only when necessary:
1. Which template should be the primary template?
2. Is there a separate reference template?
3. Does the user want to provide writing samples for `soul.md`?
4. Are the detected locked regions and field bindings acceptable?

## Standard Execution Flow
1. Initialize project
2. Complete experiment or implementation work
3. Write or update `docs/report_body.md`
4. Scan templates and recommend a plan
5. Generate and confirm preview
6. Build redacted output
7. Inject private fields locally
8. Verify outputs
9. Clean only recyclable artifacts when requested
