# AGENTS.md

## Route First
- 这是一个 agent-driven 报告框架工作区，不是普通应用仓库。
- 正常入口只有 `scripts/workflow_agent.py`。
- 先读：`report.task.yaml` -> `workflow.json` -> `INSTALL.md` -> `SKILL.md`。
- 完整手册看 [INSTALL.md](/F:/Codes/Skills/goEasyYourReport/INSTALL.md)；高频 agent 规则看 [SKILL.md](/F:/Codes/Skills/goEasyYourReport/SKILL.md)。

## Daily Entry
```powershell
uv run python scripts\workflow_agent.py prepare --project-root .
uv run python scripts\workflow_agent.py preview --project-root .
uv run python scripts\workflow_agent.py build --project-root .
uv run python scripts\workflow_agent.py verify --project-root . --target redacted
uv run python scripts\workflow_agent.py inject --project-root . --source temp\private-fields.sample.json
```

## Agent 可控项
- 通过 `report.task.yaml` 调高层决策和任务阶段
- 通过 `docs/report_body.md` 与需求文档控制“写什么”
- 通过模板保留块、绑定和输入材料控制“渲染什么、如何渲染”
- 不要删除框架渲染部件；不要静默重写 `default template`

## Non-Negotiable Contracts
- `report.task.yaml` is the durable workspace entrypoint.
- `Build blocked until report.task.yaml marks the task as ready_to_write.`
- `build` includes a `DOCX integrity gate`; `docx_integrity_error` is blocking before `verify` or `inject`.
- `prepare` / `preview` expose `semantic template scan`, `style-gap confirmation`, `TOC / reference-block detection in preview`, and `semantic style recommendation before build`.
- `TOC is inserted only when detected and confirmed`.
- `figure / table cross-references are a post-processing step`.
- `cross-reference insertion requires user confirmation`.
- `supported equation syntax` is intentionally narrow.
- `inline equations render inline, block equations are numbered and cross-referenceable`.
- `bibliography source modes: agent_generate_verified_only, agent_search_and_screen, user_supplied_files`.
- `no reference block in task/template means source-only, not output`.

## Debug Only
直接脚本只用于单阶段排错：
- `scripts/init_project.py`
- `scripts/list_private_fields.py`
- `scripts/scan_template.py`
- `scripts/build_preview.py`
- `scripts/build_report.py`
- `scripts/verify_report.py`
- `scripts/inject_private_fields.py`
