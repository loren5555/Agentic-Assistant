# Agentic Assistant

个人科研助理。DBOS 管理执行进度、checkpoint 和恢复；Notion 提供输入、人工审批与成果阅读界面。
业务能力通过 Protocol 隔离，实现可在 local／Codex 等 provider 之间替换。

## 当前入口

默认只运行手动指定的任务，不启动定时器：

```bash
uv run python -m assistant run intake
uv run python -m assistant run reviews
uv run python -m assistant run papers
uv run python -m assistant run articles
uv run python -m assistant run recommendations
```

也可使用 `uv run agentic-assistant`，参数相同。VS Code 调试需要设置对应的命令参数。

每个命令和具体 job 都有独立帮助，包含处理范围、写入影响、默认行为及示例：

```bash
uv run python -m assistant --help
uv run python -m assistant run --help
uv run python -m assistant run papers --help
uv run python -m assistant run recommendations --help
uv run python -m assistant resume --help
```

`--help` 在读取配置与启动 DBOS 前退出，不连接 Notion 或调用模型。
`--config FILE` 是全局选项，放在 `run`、`serve` 等命令之前；模型、批量和调度参数仍在 YAML 中配置。

| Job | 输入 | 输出 |
|---|---|---|
| intake | Inbox：Status != Archived；TODO：Status = elevated | Workbench 待审批提案 |
| reviews | 本地索引中受管理的 Open／Executed 提案；Feed 的 Interested 反馈 | 执行、修订、验收后整理；Interested 转 Inbox |
| papers | **Notero 原始库**，Zotero 同步的元数据与页面内容 | **Papers 整理库**中的简报 |
| articles | **简悦独立库**，Agent Archived 未勾选 | Papers、Knowledge 或需要审批的提案 |
| recommendations | 当前为离线 demo discovery | 本地演示报告，**不发布虚构推荐** |

Notero 只读，不是 Papers。当前不会下载 Zotero 附件，也不会把摘要或页面笔记当成已读全文。
全文验证标志默认为 false；全文读取接入后才可开启。

## 配置与首次使用

将 `src/assistant/config.example.yaml` 复制为本地 `src/assistant/config.yaml`。
配置和 Token 从 YAML 读取，不使用环境变量；该文件已被 Git 忽略。
可用 `--config PATH` 选择独立调试配置：

```bash
uv run python -m assistant --config path/to/config.yaml run intake
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

setup 添加 Finished 状态、Workbench 的 Publication Key、Knowledge／Ideas 的 Archive Key 和 Inbox 的 Research Feed Key。
不删除旧属性、不迁移旧记录。简悦库需已有 `Agent Archived` checkbox。
数据库 ID 已记录在配置示例中，可替换为自己的数据源。

## 人工审批闭环

1. `run intake`：提出提案并验证 Notion 写入后，Inbox 标为 Archived，elevated TODO 标为 handled。
2. 人类在 Workbench 设置 Human Review：Approved、Revision Requested 或 Rejected；反馈写入 Human Instruction。
3. `run reviews`：获批后执行；修订后重新等待审批；拒绝标为 Deprecated。执行结果显示在同一页面，状态为 Executed。
4. 人类设置 Result Review：Qualified 或 Unqualified；重做要求写入 Result Feedback。
5. 再次 `run reviews`：Qualified 交给 Curator。没有长期价值则 Finished；有价值的成果写入 Knowledge／Ideas 并验证后 Archived。Unqualified 重做并重新等待验收。

需要人类补充信息时，报告显示问题并回到 Open／Pending。执行时来源发生变化，需要重新申报；
不会把旧批准沿用到新范围。人工反馈和报告在写入前会再次读取检查。

Workbench 页面保留提案与当前结果；人类字段包括 Name、Status、Source、Human Review、
Human Instruction、Result Review、Result Feedback。机器提案、执行结果、整理决定、过程与用量
保存在 DBOS，不再依赖 Proposal Data／Result Data／Curation Data 等属性。
旧字段与旧提案保持不动；只有本地索引登记的记录进入新审批循环。

不为普通任务创建 Tasks 或 Activity Log。Finished／Archived 是退出活跃处理，不是删除页面。

## 原始资料整理

Notero 和简悦每次最多处理 runtime.batch_size 条待处理资料，不会为了凑足数量重复读取正文。
Notero 保持只读：查询页面属性，与本地已成功处理的页面版本比较，仅新增或修改的页面下载正文；
同步时间变化可能触发正文检查，但有意义内容指纹不变时不会重复调用模型或发布。
简悦仅查询 Agent Archived 未勾选的资料，每次从待处理队列头部读取，避免归档后游标跳过记录。
已有处理记录首次运行时会补建本地版本索引，可能仍需读取一次正文；失败的资料不会标为已处理。
Papers 按来源、Zotero URI／DOI 匹配，更新助手简报区域，
保留人类标题与笔记。简悦成功发布或提出提案后勾选 Agent Archived。

显式检查一条已归档的来源更新：

```bash
uv run python -m assistant run articles --page NOTION_PAGE_ID
uv run python -m assistant run papers --page NOTION_PAGE_ID
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
    intake: "0 0 7 * * *"
    reviews: "0 */15 * * * *"
    papers: "0 30 7 * * *"
    articles: "0 45 7 * * *"
    recommendations: "0 0 8 * * *"
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

所有任务使用 `src/logger/` 的统一日志，默认以 INFO 输出到 stderr；最终 JSON 结果单独输出到 stdout。
日志不打印凭证、完整来源正文、模型提示词或完整模型回答。

执行边界明确标记类型：`kind=agent` 是实际模型／智能体调用，`kind=script` 是固定代码或工具，
`kind=checkpoint` 是结果复用或恢复。`provider=local` 不代表纯脚本；例如本地 worker
调用模型时为 agent，模型调用 calculate 时另有 script 的开始与结束日志。
Codex 调用额外标记 `harness=codex`。派发动作日志表示选择能力，实际调用以 provider 日志为准。

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
      process_inputs.py          intake：输入 → 提案 → 人工审批
      process_reviews.py         reviews：批复 → 执行 → 验收 → 整理
      organize_papers.py         papers：Notero → Papers 或提案
      organize_articles.py       articles：简悦 → 整理结果或提案
      recommend_papers.py        recommendations：发现 → 证据 → 评估 → 推荐
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

例如阅读 intake：先看 `commands/run.py` 的分发，再看 `workflows/tasks/process_inputs.py`；
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

为了保留已有 DBOS 检查点，runtime 的注册绑定仍使用原来的持久化名称，例如
`JobWorkflows.intake`、`ProposalWorkflows.review_item`。它们的业务实现在上述新路径中。
旧 pickle 类型路径通过内存别名指向新的唯一模型定义；不需要复制或修改已有数据库。

- `src/plugins/`：按业务模块划分，再选择 local、Codex、Notion 或 demo 实现。
- `src/logger/`：项目日志。
- `data/assistant/`：DBOS SQLite、应用索引、过程与推荐报告，均不进入 Git。
- `.agents/`：本地计划、调试脚本与 fixtures，均不进入 Git。

SQLite 是当前个人原型配置；不要编辑 DBOS 内部表，也不要只删除索引或只删除 DBOS 文件。
机器状态的唯一副本位于本地，需与 DBOS 数据一起保留；后续部署可改 PostgreSQL。
旧 print-only demo 的代码已移除，其数据库与计划不加载，也不恢复旧 Codex 定时任务。
