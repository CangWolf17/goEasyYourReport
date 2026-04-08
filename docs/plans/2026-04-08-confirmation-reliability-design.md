# Confirmation Reliability Design

## Goal
Improve confirmation reliability before any private-field injection by making template scan output richer, making `preview.docx` explicitly reviewable, and emitting a stable machine-readable confirmation summary.

## Repo Context
- The current workflow is template-first, not conversion-first.
- `scripts/scan_template.py` currently emits only `cover` and `body_main` based on the first heading-like paragraph.
- `scripts/build_preview.py` currently replaces each fillable region with a single placeholder paragraph and clears the remaining paragraphs.
- `scripts/verify_report.py` currently verifies only locked-region text equality for redacted output.
- `scripts/inject_private_fields.py` depends on stable paragraph `anchor_text` matches in an existing DOCX.

## Decision
- Keep `python-docx` as the primary engine.
- Do not switch the main pipeline to Pandoc.
- Prioritize confirmation reliability over richer Markdown rendering.

## Why Not Pandoc First
- This repo depends on in-place edits to an existing DOCX template, paragraph-indexed region plans, and anchor-text replacement.
- Pandoc is strong for Markdown-to-DOCX conversion, but weaker for preserving and targeting the exact paragraph structure of an existing template.
- Pandoc is also not installed in the current environment, and it would add a non-Python binary dependency to a workflow the user wants managed with `uv`.

## Scope
### Included
- Enrich template scan output with additive metadata only.
- Mark locked and fillable regions clearly inside `preview.docx`.
- Generate `out/preview.summary.json` as a stable machine-readable confirmation artifact.
- Add preview-aware verification alongside existing redacted verification.
- Set up a `uv`-managed Python project configuration and `requirements.txt`.

### Not Included
- Full Markdown renderer rewrite.
- Bookmark/content-control parsing.
- Direct image embedding in report generation.
- Breaking changes to existing `regions.locked` / `regions.fillable` consumers.

## Architecture
### 1. Additive Scan Metadata
`scripts/scan_template.py` will continue emitting `regions.locked` and `regions.fillable` exactly as it does today so existing consumers keep working.

It will also emit additive metadata describing:
- heading anchors
- label-like field candidates
- simple region boundary hints

This metadata should be safe paragraph-level evidence only. No advanced OpenXML feature parsing is required in this phase.

### 2. Preview Confirmation Package
`scripts/build_preview.py` will keep generating `out/preview.docx` from the selected template, but it will become explicitly reviewable by inserting region markers for locked and fillable areas.

The same script will emit `out/preview.summary.json`, which becomes the stable machine-readable confirmation package.

The summary will include:
- selected template and output paths
- locked and fillable regions
- scan anchors and field candidates
- field binding metadata from `config/field.binding.json`
- private field availability states from the binding file
- unresolved or ambiguous review items

### 3. Verification Modes
`scripts/verify_report.py` will support two behaviors:
- redacted verification: preserve current locked-region equality checks
- preview verification: assert confirmation markers and summary artifact exist and match the current plan inputs

This avoids pretending preview and redacted outputs should be validated in the same way.

## Data Contract Changes
### `logs/template_scan.json`
Additive fields only:
- `anchors.headings`
- `anchors.field_candidates`
- `anchors.region_candidates`

### `config/template.plan.json`
Optional additive fields only if needed by consumers. Existing `regions` keys must remain intact.

### `out/preview.summary.json`
New artifact with stable relative-path-friendly JSON structure.

Proposed top-level shape:

```json
{
  "version": "1.0",
  "template": "./templates/template.user.docx",
  "preview": "./out/preview.docx",
  "summary": "./out/preview.summary.json",
  "regions": {
    "locked": [],
    "fillable": []
  },
  "anchors": {
    "headings": [],
    "field_candidates": [],
    "region_candidates": []
  },
  "field_binding": {
    "path": "./config/field.binding.json",
    "bindings": [],
    "availability": {}
  },
  "review": {
    "warnings": [],
    "needs_confirmation": []
  }
}
```

## Testing Strategy
- Add regression tests before implementation changes.
- Keep tests workflow-level, using temporary project roots, because this repo is script-driven.
- Verify scan output, preview summary generation, preview region markers, and preview verification behavior.
- Preserve existing tests for report generation and private-field injection.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Scan metadata breaks existing consumers | Medium | Keep `regions` unchanged and add metadata only |
| Preview markers make validation ambiguous | Medium | Use preview-specific verification rules instead of text-equality checks |
| Summary becomes another unstable log artifact | Medium | Emit a dedicated JSON summary with relative paths and a stable schema |
| Scope expands into advanced DOCX parsing | High | Limit this phase to paragraph-level anchors and label-like candidates |

## Rollout Order
1. Add `uv` project files and dependencies.
2. Add failing scan tests.
3. Implement additive scan metadata.
4. Add failing preview summary and marker tests.
5. Implement preview confirmation package output.
6. Add failing preview verification tests.
7. Implement preview verification mode.
8. Run full regression and document results.

## Key Principle
Reliability in this repo comes from stable template-aware metadata and explicit confirmation artifacts, not from richer Markdown conversion alone.
