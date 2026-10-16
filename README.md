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

setup 添加 Finished 状态、Knowledge／Ideas 的 Archive Key 和 Inbox 的 Research Feed Key。
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

Notero 和简悦分别分页读取，每次最多 runtime.batch_size 条。来源的有意义内容指纹用于去重；
Notero 的同步修改时间不触发重读。Papers 按来源、Zotero URI／DOI 匹配，更新助手简报区域，
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
成功步骤保留，包括已得到的模型响应。外部写入使用稳定标识与独立 readback；
失败可通过 status 找到工作流 ID 后恢复。授权变更导致的停止应先处理反馈／重新申报，而不是盲目重试。

## 本地状态与代码

- `src/assistant/protocol/`：能力接口。
- `src/assistant/schemas/`：业务信息格式。
- `src/assistant/workflows/`：durable jobs、提案生命周期、推荐流程。
- `src/assistant/services.py`：懒加载 provider 的衔接层。
- `src/providers/`：具体服务与模型实现。
- `src/logger/`：项目日志。
- `data/assistant/`：DBOS SQLite、应用索引、过程与推荐报告，均不进入 Git。
- `.agents/`：本地计划、调试脚本与 fixtures，均不进入 Git。

SQLite 是当前个人原型配置；不要编辑 DBOS 内部表，也不要只删除索引或只删除 DBOS 文件。
机器状态的唯一副本位于本地，需与 DBOS 数据一起保留；后续部署可改 PostgreSQL。
旧 print-only demo 的数据库与计划保留但不加载，也不恢复旧 Codex 定时任务。
