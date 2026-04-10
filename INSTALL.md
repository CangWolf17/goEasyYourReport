# 安装与使用手册

## 1. 定位
`goEasyYourReport` 不是单次 DOCX 生成脚本，而是一个可被 agent 驱动的、agent-driven 报告框架。

它的职责是：
- 管理模板扫描、语义规划、`preview` 确认、`redacted` 构建、私密字段注入与验证
- 在工作目录中保留任务状态、中间产物和最终产物
- 通过 `report.task.yaml` 让 agent 和用户共享同一份 durable contract

它不负责的事情：
- 替用户凭空捏造实验结果
- 静默改写用户模板结构
- 删除框架渲染部件来“定制功能”

## 2. Host Requirements
- Python `>=3.11`
- `uv`
- 本地文件系统访问能力
- 可读写 DOCX 的运行环境
- Windows 上如需做 TOC 刷新烟测，建议本机有 Microsoft Word

安装依赖：

```powershell
uv sync
```

## 3. 安装契约
任何 agent 使用这个仓库时都应遵守以下规则：

1. 把它当成完整工作区，而不是只摘取某个脚本。
2. 保留 `user/`、`templates/`、`config/`、`docs/`、`out/`、`logs/`、`temp/` 的目录语义。
3. 把 `scripts/workflow_agent.py` 视为稳定 facade。
4. 把 `workflow.json` 视为运行时总契约。
5. 把 `report.task.yaml` 视为任务状态、handoff 和高层控制面的入口。

## 4. 首次接手时先读什么
建议顺序：

1. `report.task.yaml`
2. `workflow.json`
3. `INSTALL.md`
4. `GUARDRAILS.md`
5. `SKILL.md`
6. `user/user.md`
7. `user/soul.md`
8. `config/template.plan.json`
9. `config/field.binding.json`

## 5. 初始化与刷新
已经是框架工作区时，直接刷新：

```powershell
uv run python scripts/workflow_agent.py prepare --project-root .
```

如果目标目录还是新项目，需要先播种默认状态：

```powershell
uv run python scripts/init_project.py --project-root .
uv run python scripts/workflow_agent.py prepare --project-root .
```

完成后至少应存在：
- `report.task.yaml`
- `workflow.json`
- `templates/template.user.docx`
- `config/template.plan.json`
- `config/field.binding.json`
- `user/user.md`
- `user/soul.md`

`templates/reference.user.docx` 是可选风格参考，不是结构强依赖。

## 6. 工作区结构
常见目录角色：
- `templates/`：主模板、参考模板、sample 模板
- `docs/`：正文、需求、参考资料
- `config/`：模板规划、字段绑定、局部 override
- `out/`：`preview.docx`、`redacted.docx`、`private.docx`
- `logs/`：扫描、初始化、推荐日志
- `temp/`：私密字段样例、本地中间材料
- `user/`：用户偏好与写作风格

核心状态文件：
- `report.task.yaml`
- `workflow.json`
- `config/template.plan.json`
- `config/field.binding.json`
- `out/preview.summary.json`

## 7. 稳定入口
统一通过：

```powershell
uv run python scripts/workflow_agent.py <action> --project-root .
```

稳定动作：
- `prepare`
- `preview`
- `build`
- `verify`
- `inject`
- `cleanup`

稳定 JSON 字段：
- `action`
- `status`
- `summary`
- `artifacts`
- `issues`
- `warnings`
- `next_step`

返回码：
- `0`：成功，可继续
- `1`：已完成本动作，但必须停下等待用户确认或 agent handoff
- `2`：阻塞错误

## 8. 完整配置契约
### 8.1 `report.task.yaml`
这是高层任务契约，负责：
- 任务阶段
- `ready_to_write`
- 需求摘要与路径
- 输入材料路径
- 高层决策项
- 运行时产物指针

当前高层决策项至少包括：
- `toc_enabled`
- `references_required`
- `appendix_enabled`
- `agent_may_write_explanatory_text`
- `default_template_protected`

### 8.2 Agent 可控项
agent 平时应优先控制这些面：
- `report.task.yaml` 里的任务阶段、输入路径和高层决策
- `docs/task_requirements.md`、`docs/document_requirements.md`、`docs/report_body.md`
- `config/template.plan.json` 与 `config/field.binding.json` 中已经暴露的工作区状态
- `templates/template.user.docx` 之外的材料输入，比如参考文献、图片、证据包

### 8.3 不能直接当参数改的东西
以下内容属于框架能力，不应通过“删除部件”来定制：
- 标题、列表、表格、图片、代码块、公式、目录、交叉引用、参考文献等渲染部件
- DOCX integrity、verify、inject 的流程部件

原则是：
- 渲染部件不能删除
- “渲染什么、如何渲染”通过任务需求、模板保留块、`report.task.yaml` 的高层决策和工作区输入来控制
- 如果当前正式参数面不够，再扩展契约，不要绕开框架直接 patch 运行路径

## 9. 默认模板与风格边界
- `default template` 是受保护基线。
- agent 可以根据任务调整高层决策，但不应把默认模板当成普通输出文件来随意重写。
- 如果用户自带模板缺语义样式，优先通过 `semantic template scan` 与推荐模板流程修复，而不是硬编码覆盖。

## 10. 正常工作流
建议顺序：

1. 收集需求、模板、任务书、参考资料、图片等输入。
2. 更新 `report.task.yaml` 的高层决策和输入路径。
3. 运行 `prepare`。
4. 检查 `preview` 包与 `out/preview.summary.json`。
5. 在真正满足写作条件后，把任务推进到 `ready_to_write`。
6. 运行 `build`。
7. 运行 `verify`。
8. 仅在 `redacted` 结果通过后运行 `inject`。

## 11. 硬门与确认点
### 11.1 Ready-To-Write Gate
- `workflow_agent.py build` 会检查 `ready_to_write`。
- `Build blocked until report.task.yaml marks the task as ready_to_write.`
- 没有完成材料收集或仍有待确认项时，不应正式写作。

### 11.2 DOCX Integrity Gate
- `build` 带有 `DOCX integrity gate`。
- 如果失败，会返回 `docx_integrity_error`。
- 这是阻塞错误，必须停在 before `verify` or `inject`。

### 11.3 语义预览门
`prepare` / `preview` 会暴露：
- `semantic template scan`
- `style-gap confirmation`
- `TOC / reference-block detection in preview`
- `semantic style recommendation before build`

如果这些确认项未解决，就不应直接推进正式构建。

## 12. TOC、交叉引用、公式、参考文献
- `TOC is inserted only when detected and confirmed`。
- `figure / table cross-references are a post-processing step`。
- `cross-reference insertion requires user confirmation`。
- 当前 `supported equation syntax` 是受限子集。
- `inline equations render inline, block equations are numbered and cross-referenceable`。
- `bibliography source modes: agent_generate_verified_only, agent_search_and_screen, user_supplied_files`。
- `no reference block in task/template means source-only, not output`。

## 13. 隐私契约
- agent 不能直接读取私密字段值。
- 只能通过 `scripts/list_private_fields.py` 看字段名和可用性。
- 私密注入只通过 `scripts/workflow_agent.py inject` 或 `scripts/inject_private_fields.py --source ...`。
- 不要在 agent 流程里重新读取 `out/private.docx`。
- `out/redacted.docx` 才是 agent 可见的验证产物。

## 14. 什么时候该问用户
只在这些情况下打断：
- 主模板选择不明确
- 锁定区/可填区识别不明确
- 字段绑定意图不明确
- TOC 开关未决
- 图表交叉引用未决
- 参考文献来源模式未决
- 私密字段来源不足

## 15. 什么时候不该问用户
以下属于框架已经编码好的约束，不应反复提问：
- 工作区路径布局
- 输出产物位置
- `redacted -> verify -> inject` 的顺序
- DOCX integrity gate 行为
- 默认的私密隔离规则

## 16. 调试逃生口
只有在单阶段调试、框架开发或复现实验时，才直接调用：
- `scripts/init_project.py`
- `scripts/list_private_fields.py`
- `scripts/scan_template.py`
- `scripts/build_preview.py`
- `scripts/build_report.py`
- `scripts/verify_report.py`
- `scripts/inject_private_fields.py`
- `scripts/cleanup_project.py`

## 17. Release 提示
- 对外 release 时，优先保留 `README.md`、`INSTALL.md`、`SKILL.md`、`AGENTS.md`、`LICENSE`、`pyproject.toml`、`requirements.txt`、`uv.lock`。
- 本地打包检查清单可放在不入库的 `RELEASE.md` 中。
