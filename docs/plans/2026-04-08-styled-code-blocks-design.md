# Styled Code Blocks Design

## Goal
Add stable, printable, styled code-block rendering with limited multi-language syntax highlighting, user-selectable light themes, and explicit agent handoff for unsupported languages.

## Context
- `scripts/build_report.py` already renders fenced code blocks as a `1x1` DOCX table.
- `AGENTS.md` explicitly warns not to casually remove the explicit table width behavior.
- The project optimizes for template-aware DOCX generation and confirmation reliability, not for replacing the pipeline with a new document engine.
- The user wants stability first, but visual quality still matters.
- The default report output must be white-paper printing friendly.

## Decision
- Keep the `1x1` table as the code-block container.
- Add a light theme header and syntax-colored runs inside the code table.
- Support a fixed first-wave language set:
  - `python`, `json`, `bash`, `yaml`, `sql`, `javascript`, `typescript`, `c`, `cpp`, `java`
- Normalize common aliases such as `py`, `sh`, `yml`, `js`, `ts`, `c++`, `cc`, `cxx`.
- Do not auto-detect languages.
- For unsupported languages, continue rendering a styled plain code block, but require agent handoff via structured output and nonzero exit code.

## Why This Approach
### Keep the Existing Table Shell
The current table-based code-block implementation is already tested and stable in this repo. It gives a predictable box model for padding, background, width, and multi-line layout in Word.

### Avoid Full Markdown or Pandoc Migration
Replacing the rendering chain would add risk across a workflow that depends on deterministic DOCX edits. The code-block upgrade should stay local to `build_report.py`.

### Fixed Support Before Broad Support
The goal is stable coverage for common languages, not generic best-effort support for everything. A whitelist keeps behavior testable and predictable.

## Rendering Model
### Container
- Use the existing explicit-width `1x1` table.
- Add a lightweight header row or leading styled paragraph that shows the normalized language name.
- Keep a white body background and light border for print friendliness.

### Typography
- Use a monospace font in the code body.
- Keep line spacing compact and stable.
- Use a light visual header with shallow contrast, not a dark IDE block.

### Syntax Color Roles
Map lexer tokens into a small semantic palette:
- `default`
- `keyword`
- `string`
- `comment`
- `number`
- `function`
- `type`
- `operator`

The render layer consumes only these roles, not lexer-specific token classes.

## Theme Model
### Built-In Themes
- Default: `github-light`
- Optional future presets can include other light themes, but dark themes are not the default because printed output matters more.

### User Override
`workflow.json` will point to:
- selected built-in theme
- optional JSON override path

`config/code-theme.user.sample.json` documents user overrides for semantic roles only.

### Failure Handling
- Invalid theme override: fall back to built-in theme and emit a warning
- Do not fail the whole build for a bad theme override alone

## Language Handling
### Supported
Highlight only when the fenced code block language is in the supported normalized whitelist.

### Unsupported
If the fenced language is unknown or unsupported:
- render a styled plain code block
- include a structured unsupported-language entry in `build_report.py` output
- return nonzero so the agent must surface the issue and ask the user whether to add support

Example output shape:

```json
{
  "code_blocks": {
    "styled": 3,
    "highlighted": 2,
    "unsupported": [
      {
        "language": "rust",
        "normalized": null,
        "action": "agent_handoff_required"
      }
    ]
  }
}
```

## Testing Strategy
- Add workflow tests, not only unit tests, because rendering output matters.
- Test plain fenced blocks with no language.
- Test supported languages for behavior and metadata, not exact XML colors.
- Test unsupported languages for nonzero exit, styled fallback, and structured agent handoff.
- Test theme override loading and fallback.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Syntax coloring creates brittle output assertions | Medium | Assert metadata and visible text, not exact low-level XML colors |
| Unsupported languages silently degrade | High | Nonzero exit plus structured handoff payload |
| Theme override breaks rendering | Medium | Validate and fall back to built-in theme |
| Code-block changes regress existing code rendering | Medium | Preserve table shell and keep current fenced-code regression test |

## Key Principle
Stable DOCX code blocks come from preserving the proven table container and making highlighting a controlled enhancement layer, not a new rendering engine.
