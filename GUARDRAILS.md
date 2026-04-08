# Guardrails

## 1. Project Model
- Treat the workflow as a project, not a single report file.
- Keep code, tests, assets, body source, templates, config, and outputs together.
- Preserve intermediate artifacts unless the user explicitly asks to clean them.

## 2. Template Rules
- Never rebuild a whole DOCX if a template exists.
- Always scan the template structure before writing any output.
- Never guess paragraph indexes, anchors, or locked regions without verification.
- Treat the primary template as the structural contract.
- Treat the reference template as the style reference only.
- If structure and style conflict, preserve structure first.

## 3. Region Safety Rules
- Locked regions must be explicitly confirmed before final generation.
- If locked regions are unknown, stop at preview generation and ask for confirmation.
- Do not write final output until locked and fillable regions are resolved.
- Do not overwrite user templates during normal execution.

## 4. Style Rules
- Prefer extracted template styles over long-term hardcoded style logic.
- If a required style is missing, create it programmatically in the generated output layer only.
- Code blocks must be represented as a 1x1 table cell.
- Figure captions go below figures.
- Table captions go above tables.
- Body text, captions, references, and code blocks must be treated as separate style roles.

## 5. Content Rules
- Complete experiment work before building the final report.
- Prefer a body source file (for example Markdown) over direct authoring in DOCX.
- If content is incomplete, keep placeholders rather than inventing material.
- If the template requires content not present in the project, mark it for confirmation.

## 6. Privacy Rules
- The agent must not read private field values.
- The agent may only read private field names and availability states.
- Secret values must be injected by a local injector, not by the planning agent.
- The agent must not re-read the final private output.
- Redacted output is the agent-visible verification artifact.

## 7. Path Rules
- Outputs must stay inside the project unless the user explicitly asks to export elsewhere.
- Temporary files belong in `temp/`.
- Final outputs belong in `out/`.
- Cleanup must not delete user templates, user profiles, or private outputs by default.

## 8. Verification Rules
- A generated file existing is not enough.
- Always verify:
  - locked regions unchanged
  - fillable regions populated
  - field bindings resolved or intentionally deferred
  - figures, tables, and code blocks structurally correct
  - expected output files exist
- Fix one issue at a time, then regenerate and re-check.

## 9. Recovery Rules
- If output structure is wrong, inspect template structure first.
- If field injection is wrong, inspect binding config before touching the template.
- If styles are wrong, inspect extracted style data before changing generation logic.
- If preview and final differ structurally, treat it as a bug.
- Never patch multiple unknown problems at once.

## 10. User Interaction Rules
- Default mode is semi-auto.
- Minimize user decisions by bundling them into one confirmation package when possible.
- Recommend a default choice before asking the user.
- Ask only when:
  - template choice is ambiguous
  - region locking is ambiguous
  - field binding is ambiguous
  - private field availability is insufficient
