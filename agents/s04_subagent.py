#!/usr/bin/env python3
# 指定使用 Python 3 解释器运行此脚本
# Harness: context isolation -- protecting the model's clarity of thought.
"""
s04_subagent.py - Subagents

Spawn a child agent with fresh messages=[]. The child works in its own
context, sharing the filesystem, then returns only a summary to the parent.

    Parent agent                     Subagent
    +------------------+             +------------------+
    | messages=[...]   |             | messages=[]      |  <-- fresh
    |                  |  dispatch   |                  |
    | tool: task       | ---------->| while tool_use:  |
    |   prompt="..."   |            |   call tools     |
    |   description="" |            |   append results |
    |                  |  summary   |                  |
    |   result = "..." | <--------- | return last text |
    +------------------+             +------------------+
              |
    Parent context stays clean.
    Subagent context is discarded.

Key insight: "Process isolation gives context isolation for free."
"""

# 导入操作系统接口模块，用于环境变量和路径操作
import os
# 导入子进程模块，用于运行外部命令
import subprocess
# 导入路径模块，提供面向对象的文件系统路径操作
from pathlib import Path

# 导入 Anthropic AI 客户端，用于与 AI 模型交互
from anthropic import Anthropic
# 导入 dotenv 模块，用于从 .env 文件加载环境变量
from dotenv import load_dotenv

# 加载环境变量，覆盖现有值
load_dotenv(override=True)

# 如果设置了 ANTHROPIC_BASE_URL，移除 ANTHROPIC_AUTH_TOKEN 以避免冲突
if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

# 设置工作目录为当前目录
WORKDIR = Path.cwd()
# 创建 Anthropic 客户端实例，使用自定义 base_url 如果设置
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
# 从环境变量获取模型 ID
MODEL = os.environ["MODEL_ID"]

# 定义父代理的系统提示，指示使用 task 工具委托探索或子任务
SYSTEM = f"You are a coding agent at {WORKDIR}. Use the task tool to delegate exploration or subtasks."
# 定义子代理的系统提示，指示完成给定任务，然后总结发现
SUBAGENT_SYSTEM = f"You are a coding subagent at {WORKDIR}. Complete the given task, then summarize your findings."


# -- Tool implementations shared by parent and child --
# 定义安全路径函数，确保路径在工作目录内，防止路径遍历攻击
def safe_path(p: str) -> Path:
    # 将输入路径与工作目录结合，并解析为绝对路径
    path = (WORKDIR / p).resolve()
    # 检查解析后的路径是否在工作目录内
    if not path.is_relative_to(WORKDIR):
        # 如果不在，抛出值错误
        raise ValueError(f"Path escapes workspace: {p}")
    # 返回安全路径
    return path

# 定义运行 bash 命令的函数
def run_bash(command: str) -> str:
    # 定义危险命令列表，这些命令可能有害
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    # 检查命令是否包含任何危险字符串
    if any(d in command for d in dangerous):
        # 如果包含，返回阻塞错误消息
        return "Error: Dangerous command blocked"
    try:
        # 尝试运行命令，使用 shell=True，设置工作目录，捕获输出，设置文本模式和超时
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, text=True, timeout=120)
        # 获取标准输出和标准错误输出，并去除空白
        out = (r.stdout + r.stderr).strip()
        # 如果有输出，返回前50000字符；否则返回无输出消息
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        # 如果超时，返回超时错误消息
        return "Error: Timeout (120s)"

# 定义读取文件的函数
def run_read(path: str, limit: int = None) -> str:
    try:
        # 读取文件内容并分割为行列表
        lines = safe_path(path).read_text().splitlines()
        # 如果设置了限制且行数超过限制，截取行并添加省略消息
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
        # 连接行并限制总长度
        return "\n".join(lines)[:50000]
    except Exception as e:
        # 捕获异常，返回错误消息
        return f"Error: {e}"

# 定义写入文件的函数
def run_write(path: str, content: str) -> str:
    try:
        # 获取安全路径
        fp = safe_path(path)
        # 创建父目录如果不存在
        fp.parent.mkdir(parents=True, exist_ok=True)
        # 写入内容到文件
        fp.write_text(content)
        # 返回成功消息，包含写入的字节数
        return f"Wrote {len(content)} bytes"
    except Exception as e:
        # 捕获异常，返回错误消息
        return f"Error: {e}"

# 定义编辑文件的函数
def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        # 获取安全路径
        fp = safe_path(path)
        # 读取文件内容
        content = fp.read_text()
        # 检查旧文本是否存在于内容中
        if old_text not in content:
            # 如果不存在，返回未找到错误消息
            return f"Error: Text not found in {path}"
        # 替换旧文本为新文本，只替换第一次出现
        fp.write_text(content.replace(old_text, new_text, 1))
        # 返回成功消息
        return f"Edited {path}"
    except Exception as e:
        # 捕获异常，返回错误消息
        return f"Error: {e}"


# 定义工具处理器映射，将工具名称映射到对应的处理函数
TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),  # bash 工具：运行 shell 命令
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),  # read_file 工具：读取文件内容
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),  # write_file 工具：写入内容到文件
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),  # edit_file 工具：替换文件中的文本
}

# 定义子代理可用的工具列表，不包括 task 工具以避免递归生成
CHILD_TOOLS = [
    {"name": "bash", "description": "Run a shell command.",  # bash 工具描述
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},  # 输入模式：command 字符串
    {"name": "read_file", "description": "Read file contents.",  # read_file 工具描述
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},  # 输入模式：path 字符串，可选 limit 整数
    {"name": "write_file", "description": "Write content to file.",  # write_file 工具描述
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},  # 输入模式：path 和 content 字符串
    {"name": "edit_file", "description": "Replace exact text in file.",  # edit_file 工具描述
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},  # 输入模式：path, old_text, new_text 字符串
]


# -- Subagent: fresh context, filtered tools, summary-only return --
# 定义运行子代理的函数，子代理有新鲜上下文、过滤工具，只返回总结
def run_subagent(prompt: str) -> str:
    # 初始化子代理消息列表，只包含用户提示，新鲜上下文
    sub_messages = [{"role": "user", "content": prompt}]  # fresh context
    # 循环最多30次，作为安全限制
    for _ in range(30):  # safety limit
        # 创建消息，使用子代理系统提示、消息列表、子工具和最大 token 数
        response = client.messages.create(
            model=MODEL, system=SUBAGENT_SYSTEM, messages=sub_messages,
            tools=CHILD_TOOLS, max_tokens=8000,
        )
        # 将助手响应添加到子消息列表
        sub_messages.append({"role": "assistant", "content": response.content})
        # 如果停止原因不是工具使用，跳出循环
        if response.stop_reason != "tool_use":
            break
        # 初始化结果列表
        results = []
        # 遍历响应内容中的每个块
        for block in response.content:
            # 如果是工具使用块
            if block.type == "tool_use":
                # 获取对应的处理器
                handler = TOOL_HANDLERS.get(block.name)
                # 调用处理器，如果存在；否则返回未知工具消息
                output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                # 添加工具结果到结果列表，限制内容长度
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)[:50000]})
        # 将结果作为用户消息添加到子消息列表
        sub_messages.append({"role": "user", "content": results})
    # 只返回最终文本给父代理 -- 子代理上下文被丢弃
    # 从响应内容中提取所有文本块，连接成字符串；如果没有，返回无总结消息
    return "".join(b.text for b in response.content if hasattr(b, "text")) or "(no summary)"


# -- Parent tools: base tools + task dispatcher --
# 定义父代理工具列表，包括子工具加上 task 调度器
PARENT_TOOLS = CHILD_TOOLS + [
    {"name": "task", "description": "Spawn a subagent with fresh context. It shares the filesystem but not conversation history.",  # task 工具描述
     "input_schema": {"type": "object", "properties": {"prompt": {"type": "string"}, "description": {"type": "string", "description": "Short description of the task"}}, "required": ["prompt"]}},  # 输入模式：prompt 字符串，可选 description 字符串
]


# 定义代理循环函数
def agent_loop(messages: list):
    # 无限循环，直到返回
    while True:
        # 创建消息，使用父系统提示、消息列表、父工具和最大 token 数
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=PARENT_TOOLS, max_tokens=8000,
        )
        # 将助手响应添加到消息列表
        messages.append({"role": "assistant", "content": response.content})
        # 如果停止原因不是工具使用，返回
        if response.stop_reason != "tool_use":
            return
        # 初始化结果列表
        results = []
        # 遍历响应内容中的每个块
        for block in response.content:
            # 如果是工具使用块
            if block.type == "tool_use":
                # 如果是 task 工具
                if block.name == "task":
                    # 获取描述，默认是 "subtask"
                    desc = block.input.get("description", "subtask")
                    # 打印 task 信息，包括描述和提示前80字符
                    print(f"> task ({desc}): {block.input['prompt'][:80]}")
                    # 运行子代理，传入提示
                    output = run_subagent(block.input["prompt"])
                else:
                    # 对于其他工具，获取处理器
                    handler = TOOL_HANDLERS.get(block.name)
                    # 调用处理器，如果存在；否则返回未知工具消息
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                # 打印输出前200字符
                print(f"  {str(output)[:200]}")
                # 添加工具结果到结果列表
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)})
        # 将结果作为用户消息添加到消息列表
        messages.append({"role": "user", "content": results})


# 如果作为主程序运行
if __name__ == "__main__":
    # 初始化历史消息列表
    history = []
    # 无限循环，等待用户输入
    while True:
        try:
            # 获取用户输入，带颜色提示
            query = input("\033[36ms04 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            # 处理 EOF 或中断，退出循环
            break
        # 如果输入是退出命令（q, exit, 或空），退出循环
        if query.strip().lower() in ("q", "exit", ""):
            break
        # 将用户查询添加到历史消息列表
        history.append({"role": "user", "content": query})
        # 调用代理循环，传入历史消息
        agent_loop(history)
        # 获取最后的消息内容（代理的最终响应）
        response_content = history[-1]["content"]
        # 如果响应内容是列表，遍历每个块
        if isinstance(response_content, list):
            for block in response_content:
                # 如果块有 text 属性，打印文本
                if hasattr(block, "text"):
                    print(block.text)
        # 打印空行分隔
        print()
