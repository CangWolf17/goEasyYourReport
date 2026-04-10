---
name: go-easy-your-report
description: Use when an agent needs to initialize or run the goEasyYourReport workspace to build a DOCX report from templates, Markdown body content, and report.task.yaml decisions.
---

# goEasyYourReport

## Overview
Use `scripts/workflow_agent.py` as the normal entrypoint for this agent-driven report framework. The framework owns preview/build/verify/inject orchestration; the agent should focus on collecting requirements, updating `report.task.yaml`, and deciding when to stop for confirmation.

## When to Use
- 用户要在工作目录里完成报告写作、排版、脱敏构建与私密注入
- 你需要读取模板、正文、材料包并输出 `preview` / `redacted` / `private`
- 你希望通过 `report.task.yaml` 持久化任务状态，而不是只靠会话上下文

不要在这些情况下使用它：
- 只想调试某个底层脚本的单点行为
- 只想做一次性的 DOCX 文本替换

## Read First
- `report.task.yaml`
- `workflow.json`
- `INSTALL.md`
- `GUARDRAILS.md`

## Agent 可控项
- 可以修改 `report.task.yaml` 中的任务阶段、输入路径和高层决策
- 可以更新 `docs/task_requirements.md`、`docs/document_requirements.md`、`docs/report_body.md`
- 可以补充模板外材料，例如参考文献、图片、证据包
- 可以基于确认结果推进 `prepare`、`preview`、`build`、`verify`、`inject`

不要这样做：
- 不要删除框架渲染部件来定制功能
- 不要把 `default template` 当作普通输出文件静默改写
- 不要读取私密字段值或重新打开 `out/private.docx`

## Workflow
1. 先读 `report.task.yaml` 和工作区输入。
2. 补充或修正高层决策与正文材料。
3. 运行 `prepare`，必要时再运行 `preview`。
4. 解决确认项后再推进到 `ready_to_write`。
5. 运行 `build`、`verify`、`inject`。

```powershell
uv run python scripts\workflow_agent.py prepare --project-root .
uv run python scripts\workflow_agent.py build --project-root .
uv run python scripts\workflow_agent.py verify --project-root . --target redacted
```

## Required Contracts
- `report.task.yaml` is the durable entrypoint and handoff file.
- `Build blocked until report.task.yaml marks the task as ready_to_write.`
- `build` includes a `DOCX integrity gate`; if it fails, expect `docx_integrity_error` and stop before `verify` or `inject`.
- `prepare` / `preview` surface `semantic template scan`, `style-gap confirmation`, `TOC / reference-block detection in preview`, and `semantic style recommendation before build`.
- `TOC is inserted only when detected and confirmed`.
- `figure / table cross-references are a post-processing step`.
- `cross-reference insertion requires user confirmation`.
- `supported equation syntax` is intentionally limited.
- `inline equations render inline, block equations are numbered and cross-referenceable`.
- `bibliography source modes: agent_generate_verified_only, agent_search_and_screen, user_supplied_files`.
- `no reference block in task/template means source-only, not output`.

## Ask The User When
- 模板结构或字段绑定含义不明确
- TOC、图表交叉引用、参考文献来源模式尚未确认
- 材料不足以推进到 `ready_to_write`
- 私密字段来源不足以安全注入

## Lower-Level Escape Hatches
Only use these for stage-level debugging:
- `scripts/init_project.py`
- `scripts/list_private_fields.py`
- `scripts/scan_template.py`
- `scripts/build_preview.py`
- `scripts/build_report.py`
- `scripts/verify_report.py`
- `scripts/inject_private_fields.py`
