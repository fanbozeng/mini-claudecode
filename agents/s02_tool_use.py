#!/usr/bin/env python3
# Harness: tool dispatch -- expanding what the model can reach.
"""
s02_tool_use.py - Tools

The agent loop from s01 didn't change. We just added tools to the array
and a dispatch map to route calls.

    +----------+      +-------+      +------------------+
    |   User   | ---> |  LLM  | ---> | Tool Dispatch    |
    |  prompt  |      |       |      | {                |
    +----------+      +---+---+      |   bash: run_bash |
                          ^          |   read: run_read |
                          |          |   write: run_wr  |
                          +----------+   edit: run_edit |
                          tool_result| }                |
                                     +------------------+

Key insight: "The loop didn't change at all. I just added tools."
"""

# 导入必要的模块
import os  # 用于操作系统接口，如环境变量
import subprocess  # 用于运行子进程，如执行 shell 命令
from pathlib import Path  # 用于路径操作，提供面向对象的文件系统路径

# 导入 Anthropic 客户端和 dotenv 用于配置
from anthropic import Anthropic  # Anthropic AI 客户端
from dotenv import load_dotenv  # 加载环境变量从 .env 文件

# 加载环境变量，覆盖现有值
load_dotenv(override=True)

# 如果设置了 ANTHROPIC_BASE_URL，移除 ANTHROPIC_AUTH_TOKEN
if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

# 设置工作目录为当前目录
WORKDIR = Path.cwd()
# 创建 Anthropic 客户端，使用自定义 base_url 如果设置
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
# 获取模型 ID 从环境变量
MODEL = os.environ["MODEL_ID"]

# 系统提示，定义代理的角色
SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks. Act, don't explain."


# 定义安全路径函数，确保路径在工作目录内
def safe_path(p: str) -> Path:
    # 将路径解析为绝对路径
    path = (WORKDIR / p).resolve()
    # 检查路径是否在工作目录内，防止路径遍历攻击
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


# 定义运行 bash 命令的函数
def run_bash(command: str) -> str:
    # 定义危险命令列表，防止执行有害命令
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    # 检查命令是否包含危险字符串
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        # 运行命令，使用 shell=True，设置工作目录，捕获输出，设置超时
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, text=True, timeout=120)
        # 获取标准输出和错误输出
        out = (r.stdout + r.stderr).strip()
        # 限制输出长度，返回结果或无输出消息
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        # 处理超时异常
        return "Error: Timeout (120s)"


# 定义读取文件的函数
def run_read(path: str, limit: int = None) -> str:
    try:
        # 读取文件内容
        text = safe_path(path).read_text()
        # 分割为行
        lines = text.splitlines()
        # 如果设置了限制，且行数超过限制，截取并添加省略消息
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        # 连接行并限制长度
        return "\n".join(lines)[:50000]
    except Exception as e:
        # 处理异常，返回错误消息
        return f"Error: {e}"


# 定义写入文件的函数
def run_write(path: str, content: str) -> str:
    try:
        # 获取安全路径
        fp = safe_path(path)
        # 创建父目录如果不存在
        fp.parent.mkdir(parents=True, exist_ok=True)
        # 写入内容
        fp.write_text(content)
        # 返回成功消息
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        # 处理异常，返回错误消息
        return f"Error: {e}"


# 定义编辑文件的函数
def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        # 获取安全路径
        fp = safe_path(path)
        # 读取文件内容
        content = fp.read_text()
        # 检查旧文本是否存在
        if old_text not in content:
            return f"Error: Text not found in {path}"
        # 替换文本，只替换第一次出现
        fp.write_text(content.replace(old_text, new_text, 1))
        # 返回成功消息
        return f"Edited {path}"
    except Exception as e:
        # 处理异常，返回错误消息
        return f"Error: {e}"


# -- The dispatch map: {tool_name: handler} --
# 定义工具处理器映射，将工具名称映射到对应的处理函数
TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),  # bash 工具：运行 shell 命令
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),  # read_file 工具：读取文件
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),  # write_file 工具：写入文件
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),  # edit_file 工具：编辑文件
}

TOOLS = [
    {"name": "bash", "description": "Run a shell command.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
]


def agent_loop(messages: list):
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return
        results = []
        for block in response.content:
            if block.type == "tool_use":
                handler = TOOL_HANDLERS.get(block.name)
                output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                print(f"> {block.name}: {output[:200]}")
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
        messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms02 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if hasattr(block, "text"):
                    print(block.text)
        print()
