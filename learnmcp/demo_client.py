from __future__ import annotations

import asyncio
import json
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 当前项目根目录。后面要用它来找到虚拟环境和 server.py。
PROJECT_ROOT = Path(__file__).parent

# 这里明确指定“用哪个 Python 去启动服务端”。
# 我们故意不用系统 python，而是用 learnmcp/.venv/bin/python，
# 这样可以保证服务端启动时一定能找到已经安装好的 mcp 依赖。
PYTHON_BIN = str(PROJECT_ROOT / ".venv" / "bin" / "python")

# 这是要被客户端拉起的服务端脚本。
SERVER_PATH = str(PROJECT_ROOT / "server.py")


async def main() -> None:
    # 这段函数就是“一个最小 MCP 客户端”的完整生命周期：
    #
    # 1. 先准备好“怎么启动服务端进程”
    # 2. 再通过 stdio_client(...) 真正把服务端进程拉起来
    # 3. 拿到和服务端通信用的 read/write 两条流
    # 4. 用这两条流创建 ClientSession
    # 5. 调用 initialize() 完成 MCP 握手
    # 6. 然后才能 list_tools / read_resource / call_tool
    #
    # 你可以把它想成：
    # “客户端自己开了一个子进程跑 server.py，然后通过这个子进程的
    # stdin/stdout 跟它说话。”
    #
    # 可以把这个过程想成下面这张时序图：
    #
    #   demo_client.py                          server.py
    #        |                                     |
    #        | 1. 准备启动参数                      |
    #        |------------------------------------>|
    #        |   command=.venv/bin/python          |
    #        |   args=[server.py]                  |
    #        |                                     |
    #        | 2. stdio_client(...) 启动子进程      |
    #        |================ spawn ==============>|
    #        |                                     |
    #        | 3. 拿到两条通信流                    |
    #        |   write_stream -----> server stdin  |
    #        |   read_stream  <----- server stdout |
    #        |                                     |
    #        | 4. session.initialize()             |
    #        |------------ initialize -----------> |
    #        | <------- initialize result -------- |
    #        |------------ initialized ----------> |
    #        |                                     |
    #        | 5. session.list_tools()             |
    #        |------------ tools/list -----------> |
    #        | <---------- tools list ------------ |
    #        |                                     |
    #        | 6. session.call_tool(...)           |
    #        |------------ tools/call -----------> |
    #        | <--------- tool result ------------ |
    #        |                                     |
    #
    # 这就是“客户端连上服务端”的完整过程。
    # 重点不是网络连接，而是：
    # “客户端拉起服务端进程，并通过 stdio 建立协议通道。”
    async with AsyncExitStack() as stack:
        # StdioServerParameters 不是“建立连接”本身，
        # 它只是告诉 MCP 客户端：
        #
        # - 要运行哪个命令
        # - 给它传什么参数
        # - 让它在什么目录下启动
        #
        # 等价于你手动在终端里执行：
        # .venv/bin/python server.py
        server_params = StdioServerParameters(
            command=PYTHON_BIN,
            args=[SERVER_PATH],
            cwd=str(PROJECT_ROOT),
        )

        # 真正的关键点在这里：
        #
        # stdio_client(server_params) 会做两件事：
        # 1. 启动一个新的子进程去运行 server.py
        # 2. 把这个子进程的 stdout/stdin 包装成两个异步流
        #
        # 这两个流就是 MCP 通信通道：
        # - read_stream: 客户端从这里“读取服务端发回来的消息”
        # - write_stream: 客户端往这里“写入要发给服务端的消息”
        #
        # 注意：
        # 这里并不是走 HTTP，也不是走 TCP 端口。
        # 它是“本地进程 <-> 本地进程”之间通过标准输入输出通信。
        read_stream, write_stream = await stack.enter_async_context(
            stdio_client(server_params)
        )

        # 有了 read/write 两条流之后，ClientSession 才能成立。
        #
        # 你可以把 ClientSession 理解成：
        # “一个懂 MCP 协议格式的高级客户端包装器”。
        #
        # 它知道怎么把
        # - list_tools()
        # - read_resource()
        # - call_tool()
        #
        # 这些高级方法，翻译成底层 JSON-RPC / MCP 消息发给服务端。
        session = await stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        # initialize() 是 MCP 握手步骤。
        #
        # 在这一步里，客户端会先发 initialize 请求给服务端，
        # 服务端返回它支持的协议版本、能力声明(capabilities) 等信息。
        #
        # 只有握手成功后，这个 session 才算“连上了服务端”。
        #
        # 所以“客户端怎么连接上服务端”的答案其实就是：
        # 1. 先用 stdio_client 启动 server.py
        # 2. 再把 server.py 的 stdin/stdout 接成通信流
        # 3. 再用 initialize() 完成 MCP 协议握手
        await session.initialize()

        print("== 1. 列出 server 暴露的能力 ==")
        # 下面这些调用，底层本质都是：
        # “session 组织一条 MCP 请求 -> 发给服务端 -> 等服务端返回结果”
        tools_result = await session.list_tools()
        resources_result = await session.list_resources()
        prompts_result = await session.list_prompts()

        print("Tools:", ", ".join(tool.name for tool in tools_result.tools))
        print(
            "Resources:",
            ", ".join(str(resource.uri) for resource in resources_result.resources),
        )
        print("Prompts:", ", ".join(prompt.name for prompt in prompts_result.prompts))

        print("\n== 2. 读取 resource ==")
        # read_resource 会向服务端发送“resources/read”请求。
        # URI 是资源的唯一标识。
        intro = await session.read_resource("learnmcp://guide/intro")
        print(extract_text_from_contents(intro.contents))

        print("\n== 3. 获取 prompt 模板 ==")
        # get_prompt 会向服务端发送“prompts/get”请求，
        # 并把参数 learner_name/topic 一起传过去。
        prompt = await session.get_prompt(
            "teach_mcp",
            {
                "learner_name": "你",
                "topic": "MCP 里 tool、resource、prompt 的区别",
            },
        )
        print(extract_prompt_text(prompt.messages))

        print("\n== 4. 调用有结构化输出的 tool ==")
        # call_tool 会发送“tools/call”请求。
        # 这里调用的 plan_mcp_learning 是一个纯计算型 tool，
        # 它没有副作用，只是返回文本和 structuredContent。
        learning_plan = await session.call_tool(
            "plan_mcp_learning",
            {
                "goal": "学会自己写一个本地 Python MCP Server",
                "days": 3,
            },
        )
        print("Tool content:")
        print(extract_tool_text(learning_plan.content))
        print("Structured content:")
        print(json.dumps(learning_plan.structuredContent, ensure_ascii=False, indent=2))

        print("\n== 5. 调用会产生副作用的 tool ==")
        # 这次调用的是带副作用的 tool。
        # 服务端收到请求后，会真的在本地创建一个 markdown 文件。
        save_result = await session.call_tool(
            "save_learning_note",
            {
                "title": "python mcp demo note",
                "content": (
                    "今天我跑通了一个最小 Python MCP demo：client 用 stdio 拉起 "
                    "server，然后读取 resource、获取 prompt、调用 tool。"
                ),
            },
        )
        print(extract_tool_text(save_result.content))


def extract_text_from_contents(contents: list[Any]) -> str:
    # read_resource 返回的是一组内容块。
    # 这个辅助函数只是把其中的 text 字段提取出来，方便打印。
    parts: list[str] = []
    for item in contents:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts)


def extract_prompt_text(messages: list[Any]) -> str:
    # get_prompt 返回的是消息列表。
    # 这里把每条消息里的文本内容取出来，拼成可读字符串。
    parts: list[str] = []
    for message in messages:
        content = getattr(message, "content", None)
        text = getattr(content, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts)


def extract_tool_text(content: list[Any]) -> str:
    # call_tool 返回的 content 也是一组内容块。
    # 这里同样只取出文本部分，方便在终端展示。
    parts: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts)


if __name__ == "__main__":
    # asyncio.run(...) 会启动事件循环并执行我们的异步 main 函数。
    asyncio.run(main())
