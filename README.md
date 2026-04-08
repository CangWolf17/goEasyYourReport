# goEasyYourReport

Document-first Python workflow skeleton for generating reviewable DOCX reports from a template, Markdown body content, and private field bindings.

## What This Repo Does

- scans a DOCX template into locked and fillable regions
- builds `preview.docx` plus `preview.summary.json` for confirmation
- builds `redacted.docx` from `docs/report_body.md`
- injects private fields into `out/private.docx`
- verifies locked-region preservation before private output

Current Markdown support includes:
- headings and paragraphs
- styled code blocks with a light printable theme
- syntax highlighting for `python`, `json`, `bash`, `yaml`, `sql`, `javascript`, `typescript`, `c`, `cpp`, and `java`
- lists
- simple pipe tables
- image insertion with failure reporting

## Setup

This repo uses `uv` for environment management.

```powershell
uv sync
```

## Key Commands

Run the full test suite:

```powershell
uv run -m unittest discover -s tests -v
```

Initialize a new workflow project in the current directory:

```powershell
uv run python scripts\init_project.py --project-root .
```

Scan the template and rebuild the preview package:

```powershell
uv run python scripts\scan_template.py --project-root .
uv run python scripts\build_preview.py --project-root .
uv run python scripts\verify_report.py --project-root . --docx out\preview.docx
```

Build and verify the redacted report:

```powershell
uv run python scripts\build_report.py --project-root .
uv run python scripts\verify_report.py --project-root . --docx out\redacted.docx
```

Inject private fields after the preview and redacted outputs are correct:

```powershell
uv run python scripts\inject_private_fields.py --project-root . --source temp\private-fields.sample.json
```

## Important Behavior

- `preview.docx` is for confirmation, not final delivery.
- `build_report.py` returns nonzero when image insertion fails or when code blocks use unsupported languages, so an agent can step in and ask the user how to proceed.
- unsupported code languages still render as styled fallback blocks, but are reported in structured output as `agent_handoff_required`.
- do not read `out/private.docx` in agent automation flows.

## License

MIT. See `LICENSE`.
