# Report Workflow Skill

## Purpose
Run a semi-automatic project workflow that covers:
- project initialization
- experiment or implementation work
- report body generation
- template recommendation
- preview confirmation
- redacted report generation
- local private-field injection
- verification

## Core Principle
This skill orchestrates the workflow. Deterministic document operations and private-field injection are handled by scripts.

## Required Project Files
- `workflow.json`
- `config/template.plan.json`
- `config/field.binding.json`
- `user/user.md`
- `user/soul.md`

## Required Scripts
- `scripts/init_project.py`
- `scripts/list_private_fields.py`
- `scripts/scan_template.py`
- `scripts/build_preview.py`
- `scripts/build_report.py`
- `scripts/inject_private_fields.py`
- `scripts/verify_report.py`
- `scripts/cleanup_project.py`

## Phase 0: Project Readiness
1. Check whether the project is initialized.
2. If not, run initialization.
3. Ensure required templates and config files exist.
4. Ensure user profile files exist.

## Phase 1: Input Collection
1. Read task requirements.
2. Read project context and relevant files.
3. Read user preferences from `user.md` and `soul.md`.
4. Read template and binding plans.

## Phase 2: Implementation Work
1. Plan the work.
2. Implement required code or content work.
3. Run tests or validations.
4. Generate project artifacts.
5. Produce `docs/report_body.md`.

## Phase 3: Template Recommendation
1. Scan candidate templates.
2. Recommend a primary template.
3. Detect likely locked and fillable regions.
4. Detect candidate field injection positions.

## Phase 4: Preview
1. Generate `out/preview.docx`.
2. Generate one confirmation package:
   - recommended template
   - locked regions
   - fillable regions
   - field bindings
   - private field availability
3. Request one bundled confirmation if needed.

## Phase 5: Redacted Build
1. Build `out/redacted.docx`.
2. Do not inject private values here.
3. Ensure structure matches the confirmed plan.

## Phase 6: Private Injection
1. Call the local injector script.
2. Inject private values into `out/private.docx`.
3. Do not read private values in the skill.
4. Do not re-read `out/private.docx`.

## Phase 7: Verification
1. Verify preview and redacted outputs structurally.
2. Verify locked regions remain unchanged.
3. Verify fillable regions are populated.
4. Verify expected assets and files exist.

## Phase 8: Cleanup
1. Clean only `temp/` and recyclable artifacts by default.
2. Preserve project artifacts unless the user explicitly requests cleanup.

## Never Do
- Never read private values.
- Never overwrite user templates silently.
- Never rebuild a whole template if region fill is possible.
- Never treat preview generation as completion.
- Never assume anchors without scanning or confirmation.
