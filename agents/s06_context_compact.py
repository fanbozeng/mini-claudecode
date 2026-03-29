#!/usr/bin/env python3
# 指定使用 Python 3 解释器运行此脚本
# Harness: compression -- clean memory for infinite sessions.
"""
s06_context_compact.py - Compact

Three-layer compression pipeline so the agent can work forever:

    Every turn:
    +------------------+
    | Tool call result |
    +------------------+
            |
            v
    [Layer 1: micro_compact]        (silent, every turn)
      Replace tool_result content older than last 3
      with "[Previous: used {tool_name}]"
            |
            v
    [Check: tokens > 50000?]
       |               |
       no              yes
       |               |
       v               v
    continue    [Layer 2: auto_compact]
                  Save full transcript to .transcripts/
                  Ask LLM to summarize conversation.
                  Replace all messages with [summary].
                        |
                        v
                [Layer 3: compact tool]
                  Model calls compact -> immediate summarization.
                  Same as auto, triggered manually.

Key insight: "The agent can forget strategically and keep working forever."
"""

# 导入 JSON 模块，用于处理 JSON 数据
import json
# 导入操作系统接口模块，用于环境变量和路径操作
import os
# 导入子进程模块，用于运行外部命令
import subprocess
# 导入时间模块，用于生成时间戳
import time
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

# 定义系统提示，指示代理使用工具解决问题
SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks."

# 设置 token 阈值，当超过此值时触发自动压缩
THRESHOLD = 50000
# 设置转录目录路径
TRANSCRIPT_DIR = WORKDIR / ".transcripts"
# 设置保留最近的工具结果数量
KEEP_RECENT = 3


# 定义估算 token 数量的函数，大约每4个字符一个 token
def estimate_tokens(messages: list) -> int:
    """Rough token count: ~4 chars per token."""
    # 返回消息字符串长度除以4的整数
    return len(str(messages)) // 4


# -- Layer 1: micro_compact - replace old tool results with placeholders --
# 定义 micro_compact 函数，用于替换旧的工具结果为占位符
def micro_compact(messages: list) -> list:
    # 收集所有 tool_result 条目的 (msg_index, part_index, tool_result_dict)
    tool_results = []
    # 遍历消息列表
    for msg_idx, msg in enumerate(messages):
        # 如果消息角色是用户且内容是列表
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            # 遍历内容中的每个部分
            for part_idx, part in enumerate(msg["content"]):
                # 如果部分是字典且类型是 tool_result
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    # 添加到工具结果列表
                    tool_results.append((msg_idx, part_idx, part))
    # 如果工具结果数量不超过保留数量，返回原始消息
    if len(tool_results) <= KEEP_RECENT:
        return messages
    # 通过匹配 tool_use_id 在之前的助手消息中找到每个结果的 tool_name
    tool_name_map = {}
    # 遍历消息
    for msg in messages:
        # 如果消息角色是助手
        if msg["role"] == "assistant":
            # 获取内容，默认空列表
            content = msg.get("content", [])
            # 如果内容是列表
            if isinstance(content, list):
                # 遍历内容中的每个块
                for block in content:
                    # 如果块有 type 属性且类型是 tool_use
                    if hasattr(block, "type") and block.type == "tool_use":
                        # 将 tool_use_id 映射到 tool_name
                        tool_name_map[block.id] = block.name
    # 清除旧结果（保留最后 KEEP_RECENT 个）
    to_clear = tool_results[:-KEEP_RECENT]
    # 遍历要清除的结果
    for _, _, result in to_clear:
        # 如果内容是字符串且长度大于100
        if isinstance(result.get("content"), str) and len(result["content"]) > 100:
            # 获取 tool_use_id，默认空字符串
            tool_id = result.get("tool_use_id", "")
            # 获取 tool_name，默认 unknown
            tool_name = tool_name_map.get(tool_id, "unknown")
            # 替换内容为占位符
            result["content"] = f"[Previous: used {tool_name}]"
    # 返回修改后的消息
    return messages


# -- Layer 2: auto_compact - save transcript, summarize, replace messages --
# 定义 auto_compact 函数，用于保存转录、总结、替换消息
def auto_compact(messages: list) -> list:
    # 保存完整转录到磁盘
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    # 生成转录文件路径，使用时间戳
    transcript_path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
    # 打开文件写入
    with open(transcript_path, "w") as f:
        # 遍历消息，写入 JSON 行
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")
    # 打印转录保存消息
    print(f"[transcript saved: {transcript_path}]")
    # 请求 LLM 总结对话
    conversation_text = json.dumps(messages, default=str)[:80000]
    # 创建消息请求总结
    response = client.messages.create(
        model=MODEL,
        messages=[{"role": "user", "content":
            "Summarize this conversation for continuity. Include: "
            "1) What was accomplished, 2) Current state, 3) Key decisions made. "
            "Be concise but preserve critical details.\n\n" + conversation_text}],
        max_tokens=2000,
    )
    # 获取总结文本
    summary = response.content[0].text
    # 用压缩总结替换所有消息
    return [
        {"role": "user", "content": f"[Conversation compressed. Transcript: {transcript_path}]\n\n{summary}"},
        {"role": "assistant", "content": "Understood. I have the context from the summary. Continuing."},
    ]


# -- Tool implementations --
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
        # 运行命令，使用 shell=True，设置工作目录，捕获输出，设置文本模式和超时
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, text=True, timeout=120)
        # 获取标准输出和错误输出，并去除空白
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
        # 如果设置了限制，且行数超过限制，截取行并添加省略消息
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
    "compact":    lambda **kw: "Manual compression requested.",  # compact 工具：请求手动压缩
}

# 定义工具列表，描述每个工具的名称、描述和输入模式
TOOLS = [
    {"name": "bash", "description": "Run a shell command.",  # bash 工具描述
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},  # 输入模式：command 字符串
    {"name": "read_file", "description": "Read file contents.",  # read_file 工具描述
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},  # 输入模式：path 字符串，可选 limit 整数
    {"name": "write_file", "description": "Write content to file.",  # write_file 工具描述
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},  # 输入模式：path 和 content 字符串
    {"name": "edit_file", "description": "Replace exact text in file.",  # edit_file 工具描述
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},  # 输入模式：path, old_text, new_text 字符串
    {"name": "compact", "description": "Trigger manual conversation compression.",  # compact 工具描述
     "input_schema": {"type": "object", "properties": {"focus": {"type": "string", "description": "What to preserve in the summary"}}}},  # 输入模式：focus 字符串
]


# 定义代理循环函数
def agent_loop(messages: list):
    # 无限循环，直到返回
    while True:
        # Layer 1: 在每次 LLM 调用前进行 micro_compact
        micro_compact(messages)
        # Layer 2: 如果 token 估算超过阈值，触发 auto_compact
        if estimate_tokens(messages) > THRESHOLD:
            print("[auto_compact triggered]")
            messages[:] = auto_compact(messages)
        # 创建消息，使用模型、系统提示、消息列表、工具和最大 token 数
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        # 将助手响应添加到消息列表
        messages.append({"role": "assistant", "content": response.content})
        # 如果停止原因不是工具使用，返回
        if response.stop_reason != "tool_use":
            return
        # 初始化结果列表
        results = []
        # 初始化手动压缩标志
        manual_compact = False
        # 遍历响应内容中的每个块
        for block in response.content:
            # 如果是工具使用块
            if block.type == "tool_use":
                # 如果是 compact 工具
                if block.name == "compact":
                    # 设置手动压缩标志
                    manual_compact = True
                    # 设置输出消息
                    output = "Compressing..."
                else:
                    # 对于其他工具，获取处理器
                    handler = TOOL_HANDLERS.get(block.name)
                    try:
                        # 调用处理器，如果存在；否则返回未知工具消息
                        output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                    except Exception as e:
                        # 捕获异常
                        output = f"Error: {e}"
                # 打印工具名称和输出前200字符
                print(f"> {block.name}: {str(output)[:200]}")
                # 添加工具结果到结果列表
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)})
        # 将结果作为用户消息添加到消息列表
        messages.append({"role": "user", "content": results})
        # Layer 3: 如果触发了手动压缩，执行 auto_compact
        if manual_compact:
            print("[manual compact]")
            messages[:] = auto_compact(messages)


# 如果作为主程序运行
if __name__ == "__main__":
    # 初始化历史消息列表
    history = []
    # 无限循环，等待用户输入
    while True:
        try:
            # 获取用户输入，带颜色提示
            query = input("\033[36ms06 >> \033[0m")
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
