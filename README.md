# Agentic Assistant

个人科研助理。当前入口读取 Notion Inbox 最近更新的一条记录，交给真实
PydanticAI 本地 Router 直接调用订阅模型理解意图，再打印原文和结构化建议。
不执行建议、不更改记录、不自动标记已处理。

## 配置 Notion

Python 使用社区维护的 [notion-client SDK](https://github.com/ramnes/notion-sdk-py)，
直接连接官方 API，不经过 Codex 的 Notion 连接工具。SDK 仍需授权，
请求受 Notion API 自身的权限和限流约束。

1. 按 [Notion 授权指南](https://developers.notion.com/guides/get-started/authorization)
   创建内部连接，启用读取内容权限；本功能不需要写入权限。
2. 在 Notion 中将 Inbox 数据库授权给该连接。
3. 获取 Inbox 的 **data source ID**（不是页面 ID，也不是数据库容器 ID）。
   参见 [数据源指南](https://developers.notion.com/guides/data-apis/working-with-databases)。
4. 在 `src/assistant/config.yaml` 中填写连接信息：

```yaml
providers:
  inbox: notion
  router: local

local:
  router_model: openai-codex:gpt-5.6-luna
  router_effort: low
  timeout_seconds: 120

codex:
  router_model: gpt-5.6-luna
  router_effort: low
  timeout_seconds: 120
  executable: codex

notion:
  token: "你的 Notion Token"
  inbox_data_source_id: "你的 Inbox 数据源 ID"
```

也支持 Notion 的个人访问 Token（PAT），填入同一个 `notion.token` 即可。
PAT 继承你的用户权限；若只想授权 Inbox，优先使用上述内部连接。

填写后运行：

```bash
uv run python -m assistant
```

也可执行 `uv run agentic-assistant`，二者使用相同入口。
运行和调试均从上述 YAML 读取配置，不需要环境变量。

## 配置决策服务

先安装 Codex CLI，运行 `codex login` 并使用 ChatGPT 账户登录。
`codex login status` 应显示 ChatGPT 登录。当前配置使用
ChatGPT 认证，不自动回退到付费 API。
订阅用量仍受账户额度和模型可用性限制。

当前 `providers.router: local` 使用 PydanticAI 的 `openai-codex:` 模型接入，
读取已有 Codex CLI 登录凭证，直接调用模型，不启动 CLI、不载入 Codex 的
编码指令、skills、工作目录或执行工具。只发送 Router 指令、输入和输出 Schema。
参见 [PydanticAI Codex 接入](https://pydantic.dev/docs/ai/models/openai-codex/)。
`local.router_effort` 指定推理强度，`local.timeout_seconds` 限制整个决策调用。
刷新后的凭证只保留在进程内，PydanticAI 不改写 CLI 登录文件。

将 `providers.router` 改回 `codex` 可继续使用完整 CLI harness。
`codex.router_model: null` 使用 CLI 默认模型（不加载个人 config.toml）；
也可以填入账户可用的模型标识。`timeout_seconds` 限制一次决策等待时间。

Codex CLI provider 使用临时工作目录、只读沙箱、禁用相关工具/插件的配置和结构化输出。
不会将项目配置或 Notion Token 放入模型请求。Inbox 正文和来源信息会发送给
Codex 服务。CLI 本身仍使用已有登录状态，临时请求文件会在调用结束后清理。
参见 [非交互调用](https://learn.chatgpt.com/docs/non-interactive-mode) 和
[配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)。

输出分为 `inbox` 和 `suggestion`。建议包含内容类型、用户意图、下一步、
简短依据、必要的澄清问题以及候选动作 ID。动作仅供审核，并不表示执行器已接入。
模型失败直接报告；空 Inbox 不调用模型。

当前 Inbox 候选动作集中在 `src/assistant/actions/inbox.py`：

- `organize_material`：整理已有材料，形成可审阅的结构化草稿。
- `investigate_question`：解释或调查问题，形成有依据的回答。
- `ask_user`：获取推进工作所必需的用户信息或选择。

入口直接使用 `INBOX_CANDIDATES`，Router 根据传入的描述选择一个动作。
动作 ID 使用字符串，不维护另一份固定枚举；返回值仍必须属于本次候选集合。
后续关系发现等阶段可在 `assistant/actions/` 中增加自己的候选目录，按阶段提供给
Router，不把全部动作一次性加入 Inbox。整理、提交审阅、正式写入和归档的执行逻辑
尚未接入，当前不会因为选中了某个动作而更改 Notion。

空 Inbox 打印“没有记录”。授权、网络及内容读取异常直接报告，不伪造成功结果。
正文使用 Notion 的 Markdown 导出；若 API 报告截断或不可访问的块，程序会停止，
不会将部分正文当作完整输入。此步骤不下载附件或展开关联页面。
当前选择不依赖特定的状态字段，也不限定“未处理”记录；每次读取最近更新的一条。

## 结构

运行进度、JSON 结果和 Router 的耗时、token usage 通过 `src/logger/` 输出到 stderr。
日志支持多行对齐，
终端支持彩色输出；默认只打印，不保存文件、不上传观测数据。

- `src/assistant/main.py`：读取、构造决策请求、调用 Router 并打印建议。
- `src/assistant/actions/`：按工作阶段集中定义候选动作及其业务含义。
- `src/assistant/config.yaml`：选择 Inbox provider，配置 Notion Token 和数据源 ID。
- `src/assistant/protocol/`：能力接口。
- `src/assistant/schemas/`：业务数据结构。
- `src/assistant/schemas/routing.py`：RouterInput 包含内容文本、上下文和候选动作；`from_source()` 读取来源的普通 `context_content` 属性，不要求各来源字段一致。
- `src/assistant/protocol/content.py`：供模型上下文使用的通用内容接口。来源自行组织语义内容，不依赖 Router；完整序列化仍保留 ID、版本等存储信息，普通属性不会重复加入序列化结果。
- `src/assistant/protocol/router.py`：Router 接口，规定必须实现的 decide 方法。
- `src/providers/__init__.py`：按名称导入 Provider 包，不包装各项能力。
- `src/providers/local/router.py`：本地 PydanticAI Router 实现，从自身配置创建模型。
- `src/providers/routing.py`：两种 Router 共用的理解指令和候选动作校验。
- `src/assistant/workflows/`：保留的旧执行流程，尚未迁移到新候选目录，当前建议入口不调用。
- `src/providers/notion/`：Notion SDK 的 Inbox 实现。
- `src/providers/codex/`：实现 Router 接口的 Codex CLI 服务适配器。

业务代码给实例标注能力 Protocol，只使用接口定义的方法。Router 包直接导出
DecisionRouter 类，构造函数接收自身配置并完成初始化，不再套 open_router 或
无清理职责的上下文管理器。Router 仅在读取到 Inbox 内容后创建。

Notion 直接导出 InboxSource，构造时保存自身配置；fetch 和 fetch_latest 内部
创建客户端，在一次读取完成或失败时关闭连接，调用方无需管理上下文。
插件仍按配置名称动态加载，不额外定义 Factory Protocol 或接口校验层。
调用侧的类型注解提供提示和参数检查；缺失入口或调用不兼容时自然报错。
Protocol 不读取配置，也不自行选择实现。
工作区 Pylance 配置启用了 basic 检查，并将抽象类实例化问题显示为错误。

现有 YAML 格式不变。每个 Provider 读取与包同名的配置节；切换到本地 Router
时设置 `providers.router: local`，并添加 `local.router_model`（PydanticAI 的模型名称）、
`local.router_effort` 和 `local.timeout_seconds`。
配置解析与客户端创建均在使用对应能力时进行，空 Inbox 不初始化决策服务。

旧 Demo 已移除。Agent 计划、临时验证脚本和工作区记录留在 Git 忽略的 `.agents/`。
