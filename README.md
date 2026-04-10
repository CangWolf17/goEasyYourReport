# goEasyYourReport

`goEasyYourReport` 是一个面向中文场景的 agent-driven DOCX 报告框架。它把模板扫描、`preview` 确认、正文渲染、脱敏构建、私密注入和验证收敛到同一个工作区里，适合让 agent 在一次任务内完成“收集需求 -> 写作/排版 -> 产出报告”。

## 你会得到什么
- 用 `report.task.yaml` 管理任务状态、输入材料路径和高层决策
- 用 `scripts/workflow_agent.py` 作为唯一稳定入口
- 用 `prepare -> preview -> build -> verify -> inject` 跑完整生命周期
- 底层渲染仍由 `scripts/build_report.py`、`scripts/build_preview.py` 等脚本完成，但正常使用不需要直接调用

## 快速开始
先安装依赖：

```powershell
uv sync
```

然后在工作区初始化或刷新：

```powershell
uv run python scripts\workflow_agent.py prepare --project-root .
```

最短使用路径：

```powershell
uv run python scripts\workflow_agent.py preview --project-root .
uv run python scripts\workflow_agent.py build --project-root .
uv run python scripts\workflow_agent.py verify --project-root . --target redacted
uv run python scripts\workflow_agent.py inject --project-root . --source temp\private-fields.sample.json
```

## 关键约束
- `report.task.yaml` 是工作区入口；`ready_to_write` 是正式写作门。
- `Build blocked until report.task.yaml marks the task as ready_to_write.`
- 默认模板是 `default template` 基线，agent 不应静默重写。
- `build` 带有 `DOCX integrity gate`；如果失败会返回 `docx_integrity_error`，必须停在 before `verify` or `inject`。
- `prepare` / `preview` 会暴露 `semantic template scan`、`style-gap confirmation`、`TOC / reference-block detection in preview` 和 `semantic style recommendation before build`。
- `TOC is inserted only when detected and confirmed`。
- `figure / table cross-references are a post-processing step`，并且 `cross-reference insertion requires user confirmation`。
- `supported equation syntax` 目前是受限子集；`inline equations render inline, block equations are numbered and cross-referenceable`。
- `bibliography source modes: agent_generate_verified_only, agent_search_and_screen, user_supplied_files`。
- `no reference block in task/template means source-only, not output`。

## 文档分工
- [INSTALL.md](/F:/Codes/Skills/goEasyYourReport/INSTALL.md)：完整安装、初始化、配置契约、工作区结构
- [SKILL.md](/F:/Codes/Skills/goEasyYourReport/SKILL.md)：面向 agent 的标准 skill 说明和高频 `Agent 可控项`
- [AGENTS.md](/F:/Codes/Skills/goEasyYourReport/AGENTS.md)：短路由和硬约束

## 适用输入
- 模板 / 任务书 / 格式要求
- 参考文献、图片、相关材料
- `docs/report_body.md` 中的正文语料
- `report.task.yaml` 中的任务决策与运行时状态

## License

MIT。见 `LICENSE`。
