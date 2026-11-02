# Agentic Assistant

个人科研助理。DBOS 管理执行进度、checkpoint 和恢复；Notion 提供输入、人工审批与成果阅读界面。
业务能力通过 Protocol 隔离，实现可在 local／Codex 等 provider 之间替换。

## 当前入口

默认只运行手动指定的任务，不启动定时器：

```bash
uv run python -m assistant run propose-tasks
uv run python -m assistant run process-workbench
uv run python -m assistant run organize-papers
uv run python -m assistant run organize-articles
uv run python -m assistant run recommend-papers
```

也可使用 `uv run agentic-assistant`，参数相同。VS Code 调试需要设置对应的命令参数。

每个命令和具体 job 都有独立帮助，包含处理范围、写入影响、默认行为及示例：

```bash
uv run python -m assistant --help
uv run python -m assistant run --help
uv run python -m assistant run organize-papers --help
uv run python -m assistant run recommend-papers --help
uv run python -m assistant resume --help
```

`--help` 在读取配置与启动 DBOS 前退出，不连接 Notion 或调用模型。
`--config FILE` 是全局选项，放在 `run`、`serve` 等命令之前；模型、批量和调度参数仍在 YAML 中配置。

| Job | 输入 | 输出 |
|---|---|---|
| propose-tasks | Inbox：Status != Archived；TODO：Status = elevated | Workbench 待审批提案 |
| process-workbench | 本地索引中受管理的 Open／Executed 提案；Feed 的 Interested 反馈 | 执行、修订、验收后整理；Interested 转 Inbox |
| organize-papers | **Notero 原始库**，Zotero 同步的元数据与页面内容 | **Papers 整理库**中的简报 |
| organize-articles | **简悦独立库**，Agent Archived 未勾选 | Papers、Knowledge 或需要审批的提案 |
| recommend-papers | 当前为离线 demo discovery | 本地演示报告，**不发布虚构推荐** |

Notero 是原始资料，不是 Papers。论文成功发布到 Papers 后，`Agent In Papers` 复选框会被勾选；发布到 Knowledge 或仅提出 proposal 不会勾选。当前不会下载 Zotero 附件，也不会把摘要或页面笔记当成已读全文。

Papers 保存阅读所需的 Original Title、Authors、Abstract、Date、Year、Publication、Keywords 和 Reading Summary。
Abstract 是来源中的原始摘要；Reading Summary 是基于实际可用证据生成的阅读摘要，不能冒充原文或全文阅读。
未知日期、刊物和摘要留空。发布时只补空属性，保留已有人工内容；关键词用于研究主题检索，不复制行政标签。
阅读进度和 Status 由 Notero 管理，Papers 不再重复保存；Brief Status 是助手简报的发布状态，仍然保留。
引用、BibTeX、附件等详细书目信息由 Notero 管理，Papers 的 Source Page、Zotero URI 和 DOI 用于来源追溯与去重。

Papers 属性职责如下；同类属性合并管理，避免再次复制整个 Notero 结构：

| 属性 | 处理与用途 |
| --- | --- |
| Title | 保留，面向阅读的标题 |
| Original Title | 保留，论文原始标题 |
| Authors | 保留，作者信息 |
| Date / Year | 保留，发表日期和便于分组的年份 |
| Publication | 保留，统一保存期刊、会议或预印本平台 |
| Abstract | 保留，原文摘要 |
| Reading Summary | 保留，基于可用证据的阅读摘要 |
| Tags | 保留，宽泛研究方向，优先使用有效 Collections 与研究标签 |
| Keywords | 保留，具体问题、机制与方法关键词 |
| Link | 保留，论文原始网页或全文入口，优先使用 Notero URL |
| Code | 保留，仅保存已明确给出的官方实现链接 |
| Related Papers | 保留，有依据的论文关系；当前不自动生成 |
| Source Type | 保留，Zotero 或 SimpRead 来源类型 |
| Source Page / Zotero URI / DOI | 保留，来源链接与发布去重，不作为重复书目管理入口 |
| Brief Status / Publication Key | 保留，简报发布状态与重试确认码 |
| Last edited time | 保留，Notion 自动记录的页面修改时间 |
| Source / URL | 删除空的重复属性，分别由 Source Type 与 Link 承担 |
| Collections | 删除空属性，有效研究分类归入 Tags |
| Proceedings Title / Series Title | 删除空属性，发表载体统一归入 Publication |
| Place / Editors / Item Type / Extra / Short Title | 删除空的详细书目字段，由 Notero 管理 |
| Date Added / Date Modified / Source Edited Time | 删除空的旧同步字段，当前流程不使用 |
| rank | 删除空的旧排序字段，当前没有评分流程 |
| 阅读进度 / Status | 已删除，阅读状态由 Notero 管理 |
| Citation Key / In-Text Citation / Full Citation / File Path | 当前 Papers 已无这些字段，引用和附件由 Notero 管理 |

填充操作只补空值，不覆盖人工内容。保留 Code、Related Papers 并不意味着每篇论文都应该有值；
未知代码地址、没有证据的论文关系都应留空。
全文验证标志默认为 false；全文读取接入后才可开启。

## 配置与首次使用

将 `src/assistant/config.example.yaml` 复制为本地 `src/assistant/config.yaml`。
配置和 Token 从 YAML 读取，不使用环境变量；该文件已被 Git 忽略。
可用 `--config PATH` 选择独立调试配置：

```bash
uv run python -m assistant --config path/to/config.yaml run propose-tasks
```

现阶段模型角色默认使用 local provider 的 PydanticAI 调用。保留模型、effort 和超时配置。
`openai-codex:` 模型使用已登录的订阅身份；安装 Codex CLI 后先运行 `codex login`。
复杂执行能力以后可以切换 provider，不改变工作流接口。

Notion 连接需要授权 Inbox、TODO、Workbench、Knowledge、Ideas、Papers、简悦及研究相关数据库。
**Notero 只需要读取权限。** Python 的 notion-client SDK 调用官方 Notion API。

显式初始化必要的属性／状态选项：

```bash
uv run python -m assistant setup
```

setup 添加 Finished 状态、Workbench／Papers／Knowledge 的 Publication Key、Knowledge／Ideas 的 Archive Key 和 Inbox 的 Research Feed Key。
不删除旧属性、不迁移旧记录。简悦库需已有 `Agent Archived` checkbox。
数据库 ID 已记录在配置示例中，可替换为自己的数据源。

## 人工审批闭环

1. `run propose-tasks`：提出提案并验证 Notion 写入后，Inbox 标为 Archived，elevated TODO 标为 handled。
2. 人类在 Workbench 设置 Human Review：Approved、Revision Requested 或 Rejected；反馈写入 Human Instruction。
3. `run process-workbench`：获批后执行；修订后重新等待审批；拒绝标为 Deprecated。执行结果显示在同一页面，状态为 Executed。
4. 人类设置 Result Review：Qualified 或 Unqualified；重做要求写入 Result Feedback。
5. 再次 `run process-workbench`：Qualified 交给 Curator。没有长期价值则 Finished；有价值的成果写入 Knowledge／Ideas 并验证后 Archived。Unqualified 重做并重新等待验收。

需要人类补充信息时，报告显示问题并回到 Open／Pending。执行时来源发生变化，需要重新申报；
不会把旧批准沿用到新范围。人工反馈和报告在写入前会再次读取检查。

Workbench 页面保留提案与当前结果；人类字段包括 Name、Status、Source、Human Review、
Human Instruction、Result Review、Result Feedback。机器提案、执行结果、整理决定、过程与用量
保存在 DBOS，不再依赖 Proposal Data／Result Data／Curation Data 等属性。
旧字段与旧提案保持不动；只有本地索引登记的记录进入新审批循环。

不为普通任务创建 Tasks 或 Activity Log。Finished／Archived 是退出活跃处理，不是删除页面。

## 原始资料整理

Notero 和简悦每次最多处理 runtime.batch_size 条待处理资料，不会为了凑足数量重复读取正文。
Notero 保留原始资料，仅写入可见的 `Agent In Papers` 标记：查询页面属性，与本地已成功处理的页面版本比较，仅新增或修改的页面下载正文；
同步时间变化可能触发正文检查，但有意义内容指纹不变时不会重复调用模型或发布。
Notero 没有写入“已处理”属性。标记位于 `runtime.directory/index.sqlite` 的
`handled_captures` 表：保存来源页面 ID 和成功处理的版本。只有发布与确认完成后才登记。
失败项会再次读取；清空本地数据或改用另一个运行目录，也会失去这份跳过记录。
日志中的 `properties_scanned` 是扫描属性数，`bodies_read` 才是读取正文数，
`unchanged_skipped` 是直接跳过数；看到属性查询不等于重新阅读或重新调用模型。
简悦仅查询 Agent Archived 未勾选的资料，每次从待处理队列头部读取，避免归档后游标跳过记录。
已有处理记录首次运行时会补建本地版本索引，可能仍需读取一次正文；失败的资料不会标为已处理。
Papers 按来源、Zotero URI／DOI 匹配，更新助手简报区域，
保留人类标题与笔记。简悦成功发布或提出提案后勾选 Agent Archived。
Papers／Knowledge 简报使用文本属性 `Publication Key` 确认发布：正文 API 成功后再写确认码，
回读仅检查确认码，不逐字比较 Notion 导出的 Markdown。确认码包含来源指纹和当前简报，
相同确认码的重试不改正文、不重置人工状态。更新正文时仍检查助手区域边界，避免覆盖人工笔记。
此确认表示发布步骤已完成，不保证正文逐字完整；内容质量仍由人工审阅。
所需确认码属性通过 `setup` 初始化，正常发布不重复修改数据库 schema。

显式检查一条已归档的来源更新：

```bash
uv run python -m assistant run organize-articles --page NOTION_PAGE_ID
uv run python -m assistant run organize-papers --page NOTION_PAGE_ID
```

内容未改变时仍复用现有产出，不额外调用模型。

## 推荐与证据

推荐默认每类每日最多一条，允许零条。包括 Understanding Daily、Mainline Deep Read、
Frontier Radar、Exceptional Event。深读必须有已获取的完整原文；作者主张、实验支持和 Agent 推断
分开记录，不生成 graphical abstract，不修改长期兴趣或 Human Feedback。

AMiner API 尚未接入。当前 discovery／evidence 使用明确标记的离线 fixtures，
不调用推荐模型、不读取真实兴趣、不写 Research Feed。推荐报告包含实际发布数、
拒绝／重复理由、来源失败、待恢复写入和兴趣变更（目前为空）。

未来真实推荐将独立 checkpoint 搜索、阅读、评价和发布。每日推荐工作流 ID 固定，
失败恢复不会重复已完成的模型调用。Interested 只生成一条可去重的 Inbox 跟进，不直接写 Papers。

## 定时与恢复

`runtime.schedules: {}` 表示手动模式。调试后按需启用，例如：

```yaml
runtime:
  directory: data/assistant
  batch_size: 20
  schedules:
    propose-tasks: "0 0 7 * * *"
    process-workbench: "0 */15 * * * *"
    organize-papers: "0 30 7 * * *"
    organize-articles: "0 45 7 * * *"
    recommend-papers: "0 0 8 * * *"
```

```bash
uv run python -m assistant serve
uv run python -m assistant status
uv run python -m assistant resume WORKFLOW_ID
```

Cron 使用六位格式：秒、分、时、日、月、星期，时区 Asia/Shanghai。
DBOS 持久保存 schedule；serve 会暂停本应用不再配置的 schedule，不自动补跑离线期间的定时任务。
停止 Python 后不会继续计时执行；重启可能恢复已启动但未完成的工作流。
手动模式不会派发定时工作，但 DBOS 仍可能恢复已有的未完成工作。

一次只运行一个本地进程，runtime.lock 防止调度器和手动命令并行启动。
serve 使用串行入口队列。不同 job 可配置日／周／月等频率，工作流代码不必改变。

对 ERROR 工作流，resume 命令从失败步骤 rewind；对中断的非终态工作流使用 DBOS resume。
未完成任务若绑定其他应用版本，会明确报错并显示任务 ID 和两个版本，不自动迁移、删除或无限等待。
开发阶段可停机后显式清理旧任务再重新运行；成功任务仍可复用其结果。
成功步骤保留，包括已得到的模型响应。外部写入使用稳定标识与独立 readback；
失败可通过 status 找到工作流 ID 后恢复。授权变更导致的停止应先处理反馈／重新申报，而不是盲目重试。

Workbench 使用轻量发布确认：正文写入成功后，再将 SHA-256 发布标识写入文本属性 `Publication Key`，
同时更新相应状态。回读仅比较该属性，不比较 Markdown 正文，也不比较更新时间。
确认码相同的重试复用原发布，不覆盖正文或重置人类审批；正文成功但确认码未写入时，重试会重新发布到原页面。
这是流程完成确认，不保证正文逐字完整；具体内容由人类审阅。正文不再新增 Publication／Publication applied 标记。
审批流程通过发布确认码识别报告版本，不再对正文计算指纹；修改意图或执行要求请填写人工反馈属性。
已有页面不批量迁移；缺少该属性时，先执行 `setup` 或在 Workbench 手动添加同名文本属性。

## 运行日志

所有任务使用 `src/logger/` 的统一日志输出到 stderr；最终 JSON 结果单独输出到 stdout。
日志数量由 `src/logger/base_config.py` 的 `BaseConfig.level`、`console_log_level` 和
`file_log_level` 控制，`-v` 不修改这些级别。DBOS 自身日志独立使用 WARNING 阈值，同样不受 `-v` 影响。
日志不打印凭证、完整来源正文、模型提示词或完整模型回答。

默认模式只显示行为、结果、数量和耗时，不显示 workflow/page ID、查询键、游标、路径或完整 token 统计。
加 `-v`／`--verbose` 后，相同的日志记录在 `Details` 中额外显示结构化诊断字段，异常显示完整 traceback：

```bash
uv run python -m assistant run process-workbench
uv run python -m assistant run process-workbench -v
uv run python -m assistant -v run process-workbench
```

参数可放在命令前、命令后或任务名后。verbosity 只控制日志，不改变 stdout 的 JSON 业务结果，
例如 status 的结果仍保留供 resume 使用的工作流 ID。正常模式的异常仅显示类型及 `-v` 提示，
verbose 模式保留完整异常链。日志字段使用 `extra={"details": {...}}` 显式声明，不靠正则过滤正文。

执行边界明确标记类型：`kind=agent` 是实际模型／智能体调用，`kind=script` 是固定代码或工具，
`kind=checkpoint` 是结果复用或恢复。`provider=local` 不代表纯脚本；例如本地 worker
调用模型时为 agent，模型调用 calculate 时另有 script 的开始与结束日志。
Codex 调用额外标记 `harness=codex`。派发动作日志表示选择能力，实际调用以 provider 日志为准。

每行只显示当前正在执行的节点，不重复调用链和完整 Python 模块名，例如：

```text
INFO  | workflow:process_workbench | Review item 1/2: title='awesome-math GitHub'.
INFO  |     step:read_review | Reading current human review: title='awesome-math GitHub'.
DEBUG |         component:workbench.read_item | Reading Workbench properties.
INFO  | workflow:process_workbench | Waiting for human review: title='awesome-math GitHub' status=Open approval=Pending acceptance=Pending.
```

`command` 是 CLI 入口，`workflow` 是任务或子流程，`step` 是实际执行的 DBOS 步骤，
`component` 是能力方法，`tool` 是智能体调用的工具。不再为每一层额外输出泛化的
Call started/completed/failed 行；保留具体业务操作的开始、结果、耗时和失败原因。
异步调用通过 ContextVar 隔离上下文；无节点上下文时，显示去掉 assistant 前缀的 logger 名。
checkpoint 复用不进入已完成步骤或组件，不会伪装成新的调用。
`BaseConfig.fmt` 默认使用 `{operation}`；完整 `{call_path}` 仅作为可选诊断字段保留。
条目级进度在普通日志正文中保留标题：审阅哪项申报、执行什么任务、结果是否已发布，
无需从 ID 或网址推测。执行开始还显示简短任务描述；ID、网址和查询键只用于 `-v` 诊断。
缩进按语义层级固定：command/workflow 为第一层，step 为第二层，component/tool
为第三层。子工作流和工具内部调用不会不断向右偏移；此显示不改变日志级别或数量。

## Workbench 属性归属

Notion 展示当前申报、交付内容和人工反馈；DBOS 保存结构化对象、执行轨迹和恢复检查点。
页面正文保存可阅读的 proposal／执行结果，不再把 JSON 副本写入属性。

| 属性 | 维护方与写入时机 |
| --- | --- |
| Name、Source | 申报时写标题与原始来源链接；修订更新标题 |
| Source Kind | 申报、修订时写 inbox／todo／notero／simpread |
| Proposal Version | 申报写 1，修订写递增版本，与发布确认码一起提交 |
| Publication Key | 正文写入成功后写入，用于重试与发布确认 |
| Status | 流程维护 Open／Executed／Deprecated／Finished／Archived |
| Human Review、Human Instruction | 人工审批及补充要求；申报、修订时只把审批重置 Pending |
| Result Review、Result Feedback | 人工验收及返工反馈；成功发布结果时把验收重置 Pending |
| Execution Error | 路由、执行或结果发布失败时写简短错误；完整异常保留于日志和 DBOS。新申报、修订、返回补充输入或结果发布成功时清空 |
| Last edited time | Notion 自动维护，无需程序填写 |
| Proposal Data、Result Data | 已停用，可删除；结构化 proposal/result 已由 DBOS 检查点保存 |

字段缺失时用 `setup` 显式创建所需字段；正常读写不重复检查 schema。
现有条目不会批量回填，也不会从已停用属性迁移旧 JSON。

## 执行智能体的工具插件

worker 使用 PydanticAI 原生 Toolset，工具选择由 YAML 决定：

```yaml
local:
  worker_toolsets:
    calculator.local: {}
```

`plugins/tools/__init__.py:load_toolsets` 将 `calculator.local` 加载为
`plugins.tools.calculator.local`，调用 `create_toolset(options)`，传入
`Agent(toolsets=...)`。设为 `{}` 可禁用全部工具。工具实现、参数说明和使用指导
归工具插件所有，worker 不再逐个导入工具或维护工具专属提示词。
插件返回原生 `AbstractToolset`，可使用 `FunctionToolset`，也可接 MCP 等原生工具集。
Agent as tool 同样通过工具函数调用下游 Agent，并把结果返回上层；不需要修改 worker。

注册时，PydanticAI 从工具签名、类型标注和 Google docstring 构造名称、说明与 JSON 参数
schema，再交给模型 API。模型决定是否调用以及参数；框架校验参数、执行对应 Python 函数，
把工具结果加入消息历史，再请求模型。模型不会直接执行 Python。
当前 worker 的 `NativeOutput(TaskResult)` 校验最终结果，得到有效最终输出时结束循环；
工具返回本身不会结束整个任务。框架默认请求上限和 worker 超时也会终止异常循环。
如果工具需要更长的审批等待，应另用 deferred tools／DBOS 工作流，而不是保持一次模型调用等待。

工具插件可持有自己的资源和下游 Agent；worker 的 `async with self.agent` 负责原生工具集
生命周期。Agent 循环内的每次工具调用目前并非独立 DBOS 检查点；带外部副作用的工具需要
自行保证幂等或接入 durable step，不能把模型重试当作只执行一次的保证。

官方机制说明：[Toolsets](https://pydantic.dev/docs/ai/tools-toolsets/toolsets/)、
[Function Tools](https://pydantic.dev/docs/ai/tools-toolsets/tools/)。

日志级别：INFO 保留行为开始／结束、派发和汇总；DEBUG 记录逐页读取、分页、校验子步骤和
未变化跳过；WARNING 表示异常恢复或取消；ERROR 表示实际失败并保留异常链。

- 入口：命令、provider 选择、workflow ID、运行目录、调度触发和关闭过程。
- 读取：筛选范围、每批返回数量、累计页面数、是否还有下一页、逐页正文读取进度。
- 处理：当前第几项、来源页面 ID、去重跳过、等待人工审批、选择的执行动作与状态推进。
- 模型：请求开始、超时上限、完成耗时、token 用量；demo 评估明确标记为不调用模型。
- 写入：新建、更新或恢复已有产出，随后独立回读验证；只有验证成功才报告完成。
- 汇总：读取数、处理／复用数、未变化跳过数、等待数，以及推荐拒绝、来源失败与待恢复项。
- 故障：记录 job、workflow ID、已耗时和 traceback，异常仍向上传播，不伪装成成功。

DBOS 重放时，流程中的进度行可能再次出现，表示重新走到该处理阶段，不代表再次发送请求。
实际请求的开始／完成日志位于现有 step 或 provider 内；已完成 step 从 checkpoint 返回时不会再次输出。
已完成的整条子工作流会明确记录 `Reusing completed workflow result`。
汇总中的 `processed_or_reused`、`advanced_or_reused` 不等于新建页面数。
重复正文读取和 checkpoint 索引细节放在 DEBUG 层级，按现有 logger 配置开启。

## 从命令找到代码

`main.py` 解析参数、取得本地运行锁，然后启动应用。五个命令分别由同名模块负责：

```text
src/assistant/
  commands/
    setup.py                     初始化存储结构
    run.py                       选择任务、启动一次、打印结果
    serve.py                     注册计划并持续运行
    status.py                    查看计划与 workflow 状态
    resume.py                    恢复指定 workflow

  workflows/
    tasks/
      propose_tasks.py          propose-tasks：Inbox/TODO → 申报 → 人工审批
      process_workbench.py      process-workbench：批复 → 执行 → 验收 → 整理
      organize_papers.py        organize-papers：Notero → Papers 或申报
      organize_articles.py      organize-articles：简悦 → 整理结果或申报
      recommend_papers.py       recommend-papers：发现 → 证据 → 评估 → 推荐
    steps/
      submit_proposal.py         多种输入共同使用的提案提交过程
      organize_capture.py        论文和文章共用的逐项整理与游标步骤

  components/
    inputs/                      输入读取和完成确认
    workbench/                   提案、审批和执行结果的存储对象
    proposer/                    提案生成能力
    router/                      动作选择能力与候选动作
    task_worker/                 已批准任务的执行能力
    investigator/                调查能力
    curator/                     有用成果提取能力
    archive/                     Knowledge / Ideas 存储能力
    captures/                    原始材料、简报与发布能力
    recommendations/             发现、证据、评估与 Feed 能力

  runtime/
    application.py               组装服务、注册 DBOS 函数、管理启停
    services.py                  按配置懒加载组件实现
    schedules.py                 定时触发同一组完整任务
    recovery.py                  重试、恢复和子任务结果复用
    index.py                     本地来源、版本和游标索引
    records.py                   执行过程记录及旧 checkpoint 类型路径适配
```

每个组件的 `models.py` 定义其数据格式，`protocol.py` 引用这些类型并声明能力方法。
数据类型只定义一次；plugin 实现这些接口，不自行编排审批或归档循环。
任务文件从完整流程入口向下排列步骤。专用于该任务的步骤留在本文件，实际跨任务复用的步骤才进入 `steps/`。

例如阅读 propose-tasks：先看 `commands/run.py` 的分发，再看 `workflows/tasks/propose_tasks.py`；
提案的生成、发布、checkpoint 和来源确认集中在 `workflows/steps/submit_proposal.py`。
输入的 Notion 实现位于 `plugins/inputs/notion.py`，Workbench 页面写入实现位于 `plugins/workbench/notion.py`。

插件按“模块 → 实现来源”组织，与 `assistant/components/` 的模块一一对应：

```text
src/plugins/
  __init__.py                    get_plugin(module, source)，只导入所选实现
  inputs/notion.py               Inbox、TODO 输入
  workbench/notion.py            提案、审阅和执行结果存储
  proposer/local.py              提案生成
  router/{local,codex}.py        动作决策
  task_worker/local.py           已审批任务执行
  investigator/{local,codex}.py  问题调查
  curator/local.py               有用产出提取
  archive/notion.py              Knowledge、Ideas 存档
  captures/
    local.py                    论文／文章简报生成
    notion/
      source.py                 Notero、简悦读取
      publisher.py              Papers、Knowledge 简报发布与校验
  recommendations/
    local.py                    推荐评估
    notion.py                   Research Interests、Research Feed 存储
    demo.py                     离线发现、证据及评估 fixtures
  _shared/
    local/config.py             本地模型设置
    codex/{config,process}.py    CLI 设置和事件解析
    notion/{config,schema,markdown}.py
                                Notion 设置、属性初始化和完整正文读取
```

例如 `get_plugin("router", "codex")` 加载 `plugins.router.codex`，不加载该来源的其他能力。
`Services` 负责懒初始化，业务代码获得的类型仍是对应 Protocol。
配置中的 `providers` 继续表示各能力选用哪个来源，`local`、`notion`、`codex` 的设置无需更改。
`_shared` 仅供插件内部共用，不汇总导出业务能力；旧 `providers` Python 包已移除。

runtime 的注册绑定使用稳定的持久化名称，例如
`JobWorkflows.intake`、`ProposalWorkflows.review_item`。它们的业务实现在上述新路径中。
五个任务按动作＋对象命名：`propose-tasks`、`process-workbench`、`organize-papers`、
`organize-articles`、`recommend-papers`；Python 文件和函数使用对应的下划线名称。
DBOS 已持久化的注册名与操作身份保留，例如 `JobWorkflows.papers`，以复用已有检查点。
旧 CLI 名不再接受；YAML schedules 的任务键也使用新命令名。已有计划不会自动重写：
下次 serve 按 YAML 暂停旧任务键的计划并应用新计划；此次未启动调度器、迁移或删除任务。
旧 pickle 类型路径通过内存别名指向新的唯一模型定义；不需要复制或修改已有数据库。

- `src/plugins/`：按业务模块划分，再选择 local、Codex、Notion 或 demo 实现。
- `src/logger/`：项目日志。
- `data/assistant/`：DBOS SQLite、应用索引、过程与推荐报告，均不进入 Git。
- `.agents/`：本地计划、调试脚本与 fixtures，均不进入 Git。

SQLite 是当前个人原型配置；不要编辑 DBOS 内部表，也不要只删除索引或只删除 DBOS 文件。
机器状态的唯一副本位于本地，需与 DBOS 数据一起保留；后续部署可改 PostgreSQL。
旧 print-only demo 的代码已移除，其数据库与计划不加载，也不恢复旧 Codex 定时任务。
