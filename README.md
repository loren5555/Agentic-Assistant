# Agentic Assistant

个人科研助理。当前入口依次维护提案、执行一条获批任务、整理人类验收通过的成果：
读取 Inbox 和 elevated TODO，由 `providers.local.Proposer` 提出或修订方案，
交给 Workbench 供人审批。执行结果写回同一页面，等待人工验收。
验收通过不等于值得长期保存：无可复用产出标为 Finished，有用成果存入 Knowledge／Ideas 后
标为 Archived。

`main.py` 使用 `ProposerProtocol` 和 `WorkbenchProtocol`；
`providers.notion.Workbench` 管理 Notion 的读取、报告写入及状态更新。
`providers.local.TaskRunner` 管理执行周期，调用 DecisionRouter、TaskWorker 或 Investigator。
main 仅组装能力并按顺序调用，不持有提案或执行细节。

## 配置

Python 使用社区维护的 [notion-client SDK](https://github.com/ramnes/notion-sdk-py)，
直接连接官方 API。创建内部连接，并为 Inbox、TODO、Workbench 授予读取、插入和
更新内容权限。参见 [Notion 授权指南](https://developers.notion.com/guides/get-started/authorization)。
配置使用 **data source ID**，参见 [数据源指南](https://developers.notion.com/guides/data-apis/working-with-databases)。

将 `src/assistant/config.example.yaml` 复制为 `src/assistant/config.yaml`，填写自己的 Token。
配置文件保留在本地；运行和调试均从 YAML 读取配置。

```yaml
providers:
  inbox: notion
  router: local
  investigator: codex
  proposer: local
  workbench: notion
  worker: local
  execution: local
  curator: local
  archive: notion

local:
  router_model: openai-codex:gpt-5.6-luna
  router_effort: low
  timeout_seconds: 120
  proposer_model: openai-codex:gpt-5.6-luna
  proposer_effort: medium
  proposer_timeout_seconds: 180
  worker_model: openai-codex:gpt-5.6-luna
  worker_effort: low
  worker_timeout_seconds: 180
  curator_model: openai-codex:gpt-5.6-luna
  curator_effort: low
  curator_timeout_seconds: 180

codex:
  router_model: gpt-5.6-luna
  router_effort: low
  timeout_seconds: 120
  executable: codex
  investigator_model: gpt-5.6-luna
  investigator_effort: low
  investigator_timeout_seconds: 300

notion:
  token: "你的 Notion Token"
  inbox_data_source_id: 2e889969-ca07-49cf-92dc-647b232eb4bd
  todo_data_source_id: 0b44813f-387f-4610-9f9c-84df0c02d595
  workbench_data_source_id: b8800c2d-f16b-4ba2-908c-8b8379e12c03
  knowledge_data_source_id: "你的 Knowledge data source ID"
  ideas_data_source_id: "你的 Ideas data source ID"
```

先安装 Codex CLI，运行 `codex login`，使用 ChatGPT 账户登录。
`codex login status` 应显示 ChatGPT 登录。Proposer 与本地 Router 使用 PydanticAI 的
`openai-codex:` 模型接入订阅登录，不启动 Codex CLI 子进程。
两者独立配置模型、推理强度和超时。账户订阅决定额度与可用模型。

## 来源与报告

| 来源 | 查询条件 | 提案保存后的状态 |
|---|---|---|
| Inbox | `Status != Archived` | `Archived` |
| TODO | `Status = elevated` | `handled` |

人类将需要 Agent 额外处置的 TODO 标为 `elevated`。程序只读取这些条目，
成功保存提案后标为 `handled`；不写入 TODO 的 `pending`、`leaved` 或 `finished`。
普通个人待办由人管理。

Workbench 报告包含原始来源链接、内容理解、目的、原因、建议动作、步骤和预期产出。
Action、Agent Understanding、Intention 等内容保存在页面正文中。
修订覆盖正文，只展示当前提案。`Proposal Version` 保存版本号，`Proposal Data`
保存当前结构化提案及来源内容指纹，`Source Kind` 区分 Inbox 与 TODO。
程序直接读取这些属性，不再搜索正文中的 JSON，也不保存旧版报告或完整来源快照。
人类反馈仍保留在审批属性中。

Workbench 使用以下属性：

| 属性 | 内容 |
|---|---|
| Name | 提案标题 |
| Status | `Open`、`Executed`、`Finished`、`Archived`、`Deprecated` |
| Source | 原始来源链接，使用 rich text 保存 |
| Human Review | `Pending`、`Approved`、`Revision Requested`、`Rejected` |
| Human Instruction | 人类审批反馈 |
| Result Review | `Pending`、`Qualified`、`Unqualified` |
| Result Feedback | 人类结果验收反馈 |
| Proposal Version | 当前提案版本号（number） |
| Proposal Data | 当前提案 JSON，不包含模型过程（rich text） |
| Source Kind | `inbox` 或 `todo`（rich text） |
| Result Data | 最新执行结果 JSON，不含模型过程（rich text） |
| Execution Error | 最近一次执行错误（rich text） |
| Curation Data | 当前整理决定、结果指纹和已验证的存档链接（rich text） |

属性只在显式 setup 时初始化，日常写入不检查或修改数据库结构；可以在日常视图隐藏数据属性。
当前不设置 Proposal History，也不累积历史。

数据库已改名为 Workbench，验收字段、`Deprecated` 和 TODO 的 `handled` 已添加。
旧属性删除被自动审批拦截，请在 Workbench 中手动删除 `Action`、
`Agent Understanding`、`Agent Intention`、`Destination`、`Proposed Relation`。
新流程不读取这些属性，也不迁移旧提案；仅管理具有 `Proposal Data` 的记录。

## 人工审批与验收

每轮依次运行 Proposer → TaskRunner → Curator。新提案是 Pending，不会绕过审批。
一次最多执行一条任务；Curator 只处理 Executed / Qualified。

- `Open / Pending`：等待人类审批。
- `Open / Approved`：Router 选择动作，执行后将当前结果写回原页面，标为 `Executed`。
- `Open / Revision Requested`：根据 Human Instruction 修订同一页面，重新设为 `Pending`。
- `Open / Rejected`：标为 `Deprecated`。
- `Executed / Qualified`：Curator 提取有用成果；空产出标为 Finished，否则存档成功后标为 Archived。
- `Executed / Unqualified`：根据 Result Feedback 和旧结果重做，覆盖结果并重新等待验收。

执行失败只记录 Execution Error，不推进状态；下次运行可以重试。
Router 如选择 ask_user，会在正文显示问题并回到 `Open / Pending`，人类在 Human Instruction
填写答案后重新批准。来源内容变化时跳过执行，由 Proposer 修订后重新申报。
执行结束前再次检查提案与人工反馈，发生变化则不提交结果。

`complete_task` 处理自包含的计算、解释、翻译等任务，计算使用受限算术工具；
`organize_material` 使用同一 TaskWorker 整理提供的内容；`investigate_question` 使用 Codex
Investigator 调查公开来源。执行能力不创建其它数据库条目；验收后的 Curator 可保存长期成果。

计算 `1+1` 的调试步骤：第一次运行从 Inbox 生成 Pending 提案；将 Human Review 设为
Approved；第二次运行执行并在同一 Workbench 页面显示结果；将 Result Review 设为
Qualified；下一次运行 Curator 应判断没有长期积累价值，将页面状态设为 Finished。
无需建立额外 Task 或 Activity Log。
归档是退出活跃查询，不是删除页面；暂不自动删除已验收的记录。

Tasks 用于未来需要持续跟踪的工作，Ideas 与 Experiments 用于值得保留的研究产出。
普通问答、计算和中间步骤不另建记录。当前请单进程运行；定时器用下面的 flock 示例
防止重叠，手动运行也不要与定时周期同时启动。

## 运行与定时

首次使用新版本，先填写 Knowledge／Ideas data source ID 并将数据库授权给同一 integration，
然后显式初始化属性：

```bash
uv run python -m providers.notion.setup
```

setup 添加 Workbench 的 Curation Data 和 Finished 状态，以及目标库的 Archive Key 文本属性，
不删除现有属性、不迁移旧记录、不运行模型。标题属性名会在首次存档时自动读取并缓存。
目标 ID 可以暂时留空：零产出任务可正常 Finished；有价值的成果会保持 Executed 并报告
缺少目标配置，填写后重新运行 setup 和主入口即可继续。

手动运行一个周期：

```bash
uv run python -m assistant
```

也可执行 `uv run agentic-assistant`，二者使用相同入口。程序通过 `src/logger/` 输出
处理进度、执行结果链接，以及提案和成果整理摘要。

调试后可由外部定时器每天调用一次。以下是 cron 示例，需先创建项目的 `.agents/` 目录，
并将项目路径和 `uv` 路径改为本机实际值：

```cron
CRON_TZ=Asia/Shanghai
0 7 * * * cd /home/loren/workspace/Agentic-Assistant && flock -n .agents/proposer.lock /home/loren/.local/bin/uv run python -m assistant >> .agents/proposer.log 2>&1
```

`flock` 防止定时器同时启动两个处理周期。上面的示例不会自动安装或启动。

## Provider 与过程记录

业务代码只使用 Protocol 定义的服务。Provider 根据 YAML 动态加载，直接暴露实现类；
每个实现读取自己的配置并管理调用资源。Notion 客户端在一次操作完成或失败时关闭。
正文通过 Notion Markdown API 读取，截断或不可访问块会直接报告，避免把部分内容当作完整来源。

Proposer 自己持有来源处理、提案、修订和人工审批的工作流，TaskRunner 持有执行周期。
Curator 持有验收后的成果整理周期；main 只组装服务并调用它们。
报告通过 PydanticAI 的原生结构化输出生成，不提供执行工具；状态写入由 Proposer 调用
Workbench 完成。Notion Token 不进入模型请求。修订只发送来源、上一版提案和反馈，
不发送过程记录及整页历史。

Curator 第一版只存 Knowledge 和 Ideas。它不新增研究结论，保留原结果中的证据链接、
推测和限制；论文笔记可作为 Knowledge，但暂不创建 Papers 条目或同步 Zotero。
普通计算、临时转换和中间步骤可以零产出，不另存一份报告。

整理决定在写目标库之前保存于 Curation Data。每条成果使用源 Workbench、结果指纹和
产出序号生成稳定的 Archive Key；单进程重试时复用当前决定、查找已有写入，并回读
页面属性和正文后确认收据。全部保存成功才 Archived。失败保留 Executed 和错误，
不会重新运行执行器，也不会重新生成同一份提取决定。当前不做跨任务的语义去重。

本地 Proposer 的 `process.events` 保存 PydanticAI 的真实请求与响应消息，
`process.usage` 保存本次调用的 token 统计，包含缓存输入和请求次数。
这些信息附在本次返回的 Proposal 中，不进入模型输出 Schema，也不写入 Notion 正文或属性。
控制台继续打印调用耗时及 token 用量。
Codex Router 和 Investigator 仍保留 CLI 实现，其过程记录使用原始 JSON 事件。

已有本地 Router 使用 PydanticAI 的 `openai-codex:` 模型直接接入订阅登录，
参见 [PydanticAI Codex 接入](https://pydantic.dev/docs/ai/models/openai-codex/)。
Codex Investigator 使用独立配置进行公开网页调查，现已接入获批任务的执行流程。

正式代码在 `src/assistant/`、`src/providers/` 和 `src/logger/`。
Agent 计划、临时脚本、工作区记录和定时运行日志放在 Git 忽略的 `.agents/`。
