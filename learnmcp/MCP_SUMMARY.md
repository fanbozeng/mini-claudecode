# MCP 总结

## 1. MCP 是什么

MCP，`Model Context Protocol`，可以理解成 AI 和外部能力之间的统一协议。

它解决的问题是：

- AI 怎么发现一个外部服务有哪些能力
- AI 怎么读取外部上下文
- AI 怎么调用外部动作
- 不同 AI 客户端怎么用统一方式接不同服务

一句话记忆：

`MCP = 让 AI 能用统一方式连接外部工具、数据和模板。`

## 2. MCP 里最重要的角色

### Client

Client 是“使用能力的一方”。

例如：

- Claude Desktop
- IDE 里的 AI 插件
- 你自己写的 agent
- 当前项目里的 [demo_client.py](/Users/caobenhui/Documents/learn/learn-claude-code/learnmcp/demo_client.py)

Client 负责：

- 连接 MCP Server
- 初始化握手
- 列出可用能力
- 读取 resource
- 获取 prompt
- 调用 tool

### Server

Server 是“提供能力的一方”。

例如：

- 你自己写的本地文件工具服务
- 某个在线地图服务的 MCP 接口
- 当前项目里的 [server.py](/Users/caobenhui/Documents/learn/learn-claude-code/learnmcp/server.py)

Server 负责：

- 暴露 tools
- 暴露 resources
- 暴露 prompts
- 接收客户端请求并返回结果

### Transport

Transport 是“Client 和 Server 怎么通信”。

常见有两类：

- `stdio`
  适合本地进程通信
- `HTTP / Streamable HTTP / SSE / WebSocket`
  适合远程服务通信

## 3. MCP 的三种核心能力

### Tool

Tool 是“动作”。

适合做：

- 调第三方 API
- 写文件
- 查数据库
- 执行搜索
- 触发某个业务动作

在当前 demo 里：

- `plan_mcp_learning`
- `save_learning_note`

记忆方法：

`tool = 让 AI 去做事`

### Resource

Resource 是“可读上下文”。

适合放：

- 文档
- 配置
- 知识说明
- 笔记内容
- 某个只读数据源

在当前 demo 里：

- `learnmcp://guide/intro`

记忆方法：

`resource = 给 AI 读资料`

### Prompt

Prompt 是“模板”。

适合放：

- 固定提示词模板
- 某类任务的标准问法
- 带参数的工作流入口

在当前 demo 里：

- `teach_mcp`

记忆方法：

`prompt = 给 AI 套模板`

## 4. 客户端到底是怎么连上服务端的

这件事要分本地和远程两种情况。

### 本地 MCP：`stdio`

本地 demo 用的是 `stdio`。

它不是去连接一个已经开好的网络端口，而是：

1. Client 启动一个子进程运行 `server.py`
2. 这个子进程的 `stdin/stdout` 被接成通信管道
3. Client 和 Server 在这两条流上交换 MCP 消息
4. Client 调用 `initialize()` 完成握手
5. 后续再执行 `list_tools()`、`read_resource()`、`call_tool()`

当前项目里，对应代码在 [demo_client.py](/Users/caobenhui/Documents/learn/learn-claude-code/learnmcp/demo_client.py)：

- `StdioServerParameters(...)`
- `stdio_client(server_params)`
- `ClientSession(read_stream, write_stream)`
- `await session.initialize()`

一句话理解：

`stdio 模式 = 客户端自己拉起服务端进程，然后通过标准输入输出和它通信。`

### 远程 MCP：HTTP 或其他网络传输

如果是远程 MCP Server，比如某个云上服务，就不再由客户端启动服务端了，而是：

1. Server 已经运行在远程机器上
2. Client 通过网络地址连接它
3. 可能需要 API Key、Token、OAuth
4. `initialize()`
5. 再执行 `list_tools()`、`call_tool()`

一句话理解：

`远程模式 = 客户端连接一个已经运行好的在线 MCP 服务。`

## 5. 如果是高德地图这种服务，通常怎么接

一般有两种情况。

### 情况 A：对方直接提供原生 MCP 服务

如果高德未来直接提供 MCP Server，那么客户端只需要连它的远程地址即可。

链路会是：

`AI Client -> 高德 MCP Server`

### 情况 B：对方只提供普通 HTTP API

这更常见。

比如高德通常提供的是地图 REST API，而不是原生 MCP。

那你就自己写一个 MCP Server 做“包装层”：

1. Client 调用你的 MCP tool
2. 你的 MCP Server 去请求高德地图 API
3. 你的 Server 再把结果按 MCP 格式返回

链路会是：

`AI Client -> 你的 MCP Server -> 高德地图 API`

一句话记忆：

`很多第三方服务没有 MCP，但你可以自己写一个 MCP 包装层。`

## 6. 当前 demo 的完整调用链

当前项目的调用链是：

1. [demo_client.py](/Users/caobenhui/Documents/learn/learn-claude-code/learnmcp/demo_client.py) 启动 [server.py](/Users/caobenhui/Documents/learn/learn-claude-code/learnmcp/server.py)
2. 两者通过 `stdio` 建立通信
3. Client 执行 `initialize()`
4. Client 调用：
   - `list_tools()`
   - `list_resources()`
   - `list_prompts()`
5. Client 再继续调用：
   - `read_resource("learnmcp://guide/intro")`
   - `get_prompt("teach_mcp", ...)`
   - `call_tool("plan_mcp_learning", ...)`
   - `call_tool("save_learning_note", ...)`
6. Server 返回结果，并在本地写出笔记文件

## 7. 你现在应该形成的心智模型

设计 MCP Server 时，可以这样判断：

- 如果是“给 AI 读”的内容，用 `resource`
- 如果是“给 AI 套用”的模板，用 `prompt`
- 如果是“让 AI 去做”的动作，用 `tool`

连接方式则这样判断：

- 如果服务端就在本机，优先用 `stdio`
- 如果服务端要部署在远程，使用网络 transport

## 8. 新手最容易混淆的点

### 1. `prompt` 不是模型回答

`prompt` 只是一个模板或消息结构，不是最终的 LLM 输出。

### 2. `resource` 不等于 `tool`

`resource` 主要是读数据，`tool` 主要是执行动作。

### 3. `server.py` 单独运行看起来像“卡住了”是正常的

因为它在等待客户端通过 MCP 协议来和它通信。

### 4. `stdio` 不是网络连接

它是本地两个进程之间通过标准输入输出通信。

### 5. 很多服务不是原生 MCP

这时通常不是“不能接”，而是“你需要自己写一个 MCP 包装层”。

## 9. 学 MCP 最推荐的顺序

1. 先理解 `Client / Server / Transport`
2. 再理解 `tool / resource / prompt`
3. 跑通一个本地 `stdio` demo
4. 自己加一个新的 tool
5. 再学习远程 transport
6. 最后把一个真实 REST API 包装成 MCP

## 10. 一句话总复盘

MCP 的本质不是某个具体 SDK，而是一套“让 AI 用统一方式接外部能力”的协议。

而你现在这个项目，就是这套协议的最小可运行例子：

- Client 负责调用
- Server 负责提供能力
- `stdio` 负责通信
- `tool / resource / prompt` 负责表达不同类型的能力
