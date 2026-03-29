# learnmcp

这是一个专门给你练手的最小 Python MCP 项目。

目标很直接：在这个目录里亲手跑通一个本地 MCP demo，然后真正理解：

- MCP 是什么
- MCP Client 和 MCP Server 怎么配合
- `tool`、`resource`、`prompt` 分别解决什么问题
- 一个本地 `stdio` Python demo 是怎么工作的

## 一句话先理解 MCP

你可以把 MCP 理解成 AI 世界里的“统一插座协议”。

以前每个 AI 应用都要单独接文件系统、数据库、任务系统。
有了 MCP 之后，只要 Client 和 Server 都遵守这个协议，它们就能接起来。

## 这个 demo 里每个角色是谁

- [server.py](/Users/caobenhui/Documents/learn/learn-claude-code/learnmcp/server.py)
  你写的 MCP Server
- [demo_client.py](/Users/caobenhui/Documents/learn/learn-claude-code/learnmcp/demo_client.py)
  一个最小 MCP Client
- `stdio`
  Client 启动 Server 进程，并通过标准输入输出和它通信

这就是最小闭环：

1. Client 启动 Server
2. Client 询问 Server 有哪些能力
3. Client 读取 resource
4. Client 获取 prompt
5. Client 调用 tool

## 先记住 3 个最重要的概念

### Tool

Tool 是“动作”。

适合做：

- 调接口
- 算数据
- 写文件
- 执行动作

这个 demo 里有两个 tool：

- `plan_mcp_learning`
  返回一个结构化学习计划
- `save_learning_note`
  把笔记写到本地 `demo-output/`

### Resource

Resource 是“可读上下文”。

适合放：

- 文档
- 配置
- 知识库内容
- 项目说明

这个 demo 里：

- `learnmcp://guide/intro`
  是一份 MCP 入门说明

### Prompt

Prompt 是“模板”。

适合放：

- 固定问法
- 可复用工作流
- 带参数的提示词模板

这个 demo 里：

- `teach_mcp`
  会返回一个适合讲解 MCP 的提示词模板

## 项目结构

```text
learnmcp/
├─ .venv/
├─ demo-output/
├─ demo_client.py
├─ server.py
├─ pyproject.toml
└─ README.md
```

## 运行方式

第一次安装依赖：

```bash
cd /Users/caobenhui/Documents/learn/learn-claude-code/learnmcp
/opt/homebrew/bin/uv sync
```

运行完整 demo：

```bash
/opt/homebrew/bin/uv run python demo_client.py
```

只启动 server：

```bash
/opt/homebrew/bin/uv run python server.py
```

## 运行 `demo_client.py` 时你会看到什么

client 会自动做这几件事：

1. 连接到 MCP Server
2. 列出所有 tools/resources/prompts
3. 读取 `learnmcp://guide/intro`
4. 获取 `teach_mcp` prompt
5. 调用 `plan_mcp_learning`
6. 调用 `save_learning_note`

最后会在 `demo-output/` 下面生成一个 markdown 文件。

这一步很重要，因为它会让你明确看到：

- resource 更像“读数据”
- prompt 更像“拿模板”
- tool 更像“执行动作”

## 推荐你怎么读代码

先看 [server.py](/Users/caobenhui/Documents/learn/learn-claude-code/learnmcp/server.py)：

- `@mcp.resource(...)`
- `@mcp.prompt()`
- `@mcp.tool()`

只要看懂这三个装饰器，你就已经理解 MCP Server 最核心的 80%。

再看 [demo_client.py](/Users/caobenhui/Documents/learn/learn-claude-code/learnmcp/demo_client.py)：

- `session.list_tools()`
- `session.list_resources()`
- `session.list_prompts()`
- `session.read_resource(...)`
- `session.get_prompt(...)`
- `session.call_tool(...)`

这就是一个 MCP Client 最常见的动作集合。

## 为什么 server 里不要乱用 stdout

因为 `stdio` 传输时，`stdout` 要留给 MCP 协议消息。

如果你在 server 里把调试日志直接打到 `stdout`，就可能把协议内容污染掉。
这是本地 MCP 初学者最容易踩的坑之一。

## 建议你马上做的 3 个练习

1. 在 [server.py](/Users/caobenhui/Documents/learn/learn-claude-code/learnmcp/server.py) 里新增一个 tool，比如 `summarize_note`
2. 新增一个 resource，比如 `learnmcp://guide/errors`
3. 把 `save_learning_note` 改成“按日期建目录后再保存”

## 一套最实用的心智模型

- 如果是“给 AI 读”的内容，用 resource
- 如果是“给 AI 套用”的模板，用 prompt
- 如果是“让 AI 去做”的动作，用 tool

## 官方资料

- MCP 文档: https://modelcontextprotocol.io
- Python SDK 文档: https://py.sdk.modelcontextprotocol.io/
- Python Server Quickstart: https://modelcontextprotocol.io/quickstart/server
