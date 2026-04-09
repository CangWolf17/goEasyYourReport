# Default Template Style Alignment Design

## Goal
Make the repo ship with a sanitized built-in default template derived from the user's large-style template, then align generated DOCX output with that template's style system without copying user-specific course text.

## Context
- `init_project.py` currently creates a generic sample template and uses it when the user does not provide `--template`.
- The current renderer still favors generic Word styles such as `Heading 1` and does not fully align body text, figure/table captions, or references with the Chinese style names in the large template.
- Private fields already flow through `config/field.binding.json`, `scripts/list_private_fields.py`, and `scripts/inject_private_fields.py`.
- The user wants the default template to preserve layout/style only, keep the report body redacted, and keep private fields script-driven rather than hard-coded values.

## Decision
- Replace the current generated default sample template with a sanitized template that carries the large template's page setup and named styles.
- Use neutral placeholder text such as `报告题目 / Report Title` instead of course-specific content.
- Keep visible cover anchor labels for field injection, but let field names and availability continue to come from binding config and the private-field scripts.
- Map Markdown output into template-native styles:
  - report title -> `题目`
  - Markdown `#`, `##`, `###` -> `标题2`, `标题3`, `标题4`
  - body paragraphs -> `正文`
  - figure captions -> `图题`
  - table captions -> `表题`
  - reference entries -> `参考文献`
- Keep code blocks on the existing custom `1x1` table path.
- Do not implement cross-references in this change set.

## Default Template Strategy
### Built-In Asset
- The repo will keep an internal default DOCX template asset under `templates/`.
- `init_project.py` will copy that asset into `template.sample.docx` and then into `template.user.docx` when the user provides no template.
- This avoids any runtime dependency on an external `F:\...` path.

### Sanitized Structure
- The built-in template will preserve page setup and style definitions from the large template.
- Cover content will be neutral and reusable:
  - `报告题目 / Report Title`
  - `姓 名：`
  - `学 号：`
  - `完成日期：`
- Body content will contain neutral headings and placeholders only, so the first heading boundary stays predictable for template scanning.

## Field Injection Model
### Existing Mechanism Stays
- `list_private_fields.py` remains the only agent-safe way to inspect field names and availability.
- `inject_private_fields.py` remains responsible for reading values and replacing text after configured anchors.

### Fallback Behavior
- The default sanitized template will contain the expected cover anchors.
- For user-supplied templates that are missing expected anchors, the renderer should be able to create or preserve standard cover label lines in a predictable location so injection still has a target.
- This fallback should stay minimal and only cover configured binding anchors.

## Rendering Rules
### Headings and Body
- Heading blocks should prefer the Chinese style names used by the default template before falling back to generic Heading styles.
- Paragraph blocks should prefer `正文` before falling back to generic defaults.

### Figures
- Insert figures centered.
- Use top-and-bottom wrapping semantics, not side wrapping.
- Add a caption paragraph below each figure using `图题`.

### Tables
- Insert tables centered.
- Add a caption paragraph above each table using `表题`.
- Table cell paragraphs must not use the body first-line indent.
- Table cell paragraphs must use 1.5 line spacing.
- Prefer the template's existing table style if available.

### References
- Visible reference paragraphs should use the `参考文献` style.
- Full GB/T 7714-2015 formatting is out of scope for this pass unless the source already supplies correctly formatted entries.
- This change only aligns reference styling and preserves room for later bibliography formatting work.

## Risks
| Risk | Impact | Mitigation |
| --- | --- | --- |
| The first-heading scan heuristic may still overfill user templates | High | Keep the built-in default template sanitized and structurally simple; only add narrow cover fallback logic |
| Figure floating XML may be brittle in Word | Medium | Add targeted tests and keep inline behavior as a failure mode during implementation if needed |
| Table formatting changes may affect existing tests | Medium | Add tests first for caption order, centering, and cell paragraph formatting |
| Reference styling may be confused with full citation formatting | Medium | Limit scope to style alignment and document that GB/T formatting is not yet automatic |

## Key Principle
The repo's default template should be portable, neutral, and style-rich, while generated content should align with the template's named styles without reintroducing private values or course-specific text.
