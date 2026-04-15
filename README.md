# goEasyYourReport

`goEasyYourReport` 是一个面向中文场景的 agent-driven DOCX 报告框架Skill。它把模板扫描、`preview` 确认、正文渲染、脱敏构建、私密注入和验证收敛到同一个工作区里，适合让 agent 在一次任务内完成“收集需求 -> 写作/排版 -> 产出报告”。

## 先建立这个心智模型
- 这个仓库 / skill 提供的是**报告工作区框架**，不是“丢一个 Markdown 就立即吐出最终 DOCX”的单脚本。
- 真正进入日常协作后，`report.task.yaml` 是项目级 durable entrypoint；用户和 agent 都围绕它协作。
- `scripts/workflow_agent.py` 是唯一稳定 facade；日常不要直接拼装底层脚本链路。
- 当前生效模板的唯一 runtime authority 是 `config/template.plan.json.selection.primary_template`。
- `workflow.json.templates.main_template` 只是初始化 seed mirror；`report.task.yaml.inputs.template_path` 只是任务 / handoff mirror，它们都不负责运行时选模板。

## 你会得到什么
- 用 `report.task.yaml` 管理任务状态、输入材料路径和高层决策
- 用 `scripts/workflow_agent.py` 作为唯一稳定入口
- 用 `prepare -> preview -> build -> verify -> inject` 跑完整生命周期
- 底层渲染仍由 `scripts/build_report.py`、`scripts/build_preview.py` 等脚本完成，但正常使用不需要直接调用

## 快速开始
For Agent:

```text
Install and configure goEasyYourReport by following the instructions here:
https://github.com/CangWolf17/goEasyYourReport/blob/main/INSTALL.md
```

## 第一次上手
最短路径分两种：

### 1) 已经在一个 goEasyYourReport 工作区里
```powershell
uv sync
uv run python scripts/workflow_agent.py prepare --project-root .
```

### 2) 要把框架 bootstrap 到外部目标目录
```powershell
uv sync
uv run python scripts/workflow_agent.py bootstrap --project-root F:\path\to\report-project
```

完整安装、初始化、authority model 和坑点请看 [INSTALL.md](/F:/Codes/Skills/goEasyYourReport/INSTALL.md)。

## 关键约束
- `report.task.yaml` 是工作区入口；`ready_to_write` 是正式写作门。
- `Build blocked until report.task.yaml marks the task as ready_to_write.`
- 默认模板是 `default template` 基线，agent 不应静默重写。
- 运行时模板只认 `config/template.plan.json.selection.primary_template`；不要把 `workflow.json` 或 `report.task.yaml.inputs.template_path` 当成 co-authority。
- `build` 带有 `DOCX integrity gate`；如果失败会返回 `docx_integrity_error`，必须停在 before `verify` or `inject`。
- `prepare` / `preview` 会暴露 `semantic template scan`、`style-gap confirmation`、`TOC / reference-block detection in preview` 和 `semantic style recommendation before build`。
- `TOC is inserted only when detected and confirmed`。
- `figure / table cross-references are a post-processing step`，并且 `cross-reference insertion requires user confirmation`。
- `supported equation syntax` 目前是受限子集；`inline equations render inline, block equations are numbered and cross-referenceable`。
- `bibliography source modes: agent_generate_verified_only, agent_search_and_screen, user_supplied_files`。
- `no reference block in task/template means source-only, not output`。
- `build` 会在必要时自动生成兼容图片到 `temp/generated-images/`；默认优先兼容 JPEG，仅在透明度等确有需要时保留 PNG。

## 文档分工
- [INSTALL.md](/F:/Codes/Skills/goEasyYourReport/INSTALL.md)：给人看的完整安装 / 初始化 / authority model / pitfalls 手册
- [SKILL.md](/F:/Codes/Skills/goEasyYourReport/SKILL.md)：给 agent 的短路径、可控面和运行时规则
- [AGENTS.md](/F:/Codes/Skills/goEasyYourReport/AGENTS.md)：短路由和硬约束

## 适用输入
- 模板 / 任务书 / 格式要求
- 参考文献、图片、相关材料
- `docs/report_body.md` 中的正文语料
- `report.task.yaml` 中的任务决策与运行时状态

## License

MIT。见 `LICENSE`。
