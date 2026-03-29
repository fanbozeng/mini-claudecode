#!/usr/bin/env python3
# Harness: planning -- keeping the model on course without scripting the route.
"""
s03_todo_write.py - TodoWrite

The model tracks its own progress via a TodoManager. A nag reminder
forces it to keep updating when it forgets.

    +----------+      +-------+      +---------+
    |   User   | ---> |  LLM  | ---> | Tools   |
    |  prompt  |      |       |      | + todo  |
    +----------+      +---+---+      +----+----+
                          ^               |
                          |   tool_result |
                          +---------------+
                                |
                    +-----------+-----------+
                    | TodoManager state     |
                    | [ ] task A            |
                    | [>] task B <- doing   |
                    | [x] task C            |
                    +-----------------------+
                                |
                    if rounds_since_todo >= 3:
                      inject <reminder>

Key insight: "The agent can track its own progress -- and I can see it."
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

# 系统提示，定义代理的角色，强调使用 todo 工具规划任务
SYSTEM = f"""You are a coding agent at {WORKDIR}.
Use the todo tool to plan multi-step tasks. Mark in_progress before starting, completed when done.
Prefer tools over prose."""


# -- TodoManager: structured state the LLM writes to --
# 定义 TodoManager 类，用于管理任务列表
class TodoManager:
    # 初始化方法，创建空的任务列表
    def __init__(self):
        self.items = []

    # 更新任务列表的方法
    def update(self, items: list) -> str:
        # 检查任务数量是否超过最大限制
        if len(items) > 20:
            raise ValueError("Max 20 todos allowed")
        # 初始化验证后的列表和进行中任务计数
        validated = []
        in_progress_count = 0
        # 遍历每个任务项
        for i, item in enumerate(items):
            # 获取任务文本并去除空白
            text = str(item.get("text", "")).strip()
            # 获取任务状态并转换为小写
            status = str(item.get("status", "pending")).lower()
            # 获取任务 ID，默认使用索引+1
            item_id = str(item.get("id", str(i + 1)))
            # 检查文本是否为空
            if not text:
                raise ValueError(f"Item {item_id}: text required")
            # 检查状态是否有效
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Item {item_id}: invalid status '{status}'")
            # 如果状态是进行中，计数加一
            if status == "in_progress":
                in_progress_count += 1
            # 添加验证后的任务到列表
            validated.append({"id": item_id, "text": text, "status": status})
        # 检查是否有多于一个进行中任务
        if in_progress_count > 1:
            raise ValueError("Only one task can be in_progress at a time")
        # 更新任务列表
        self.items = validated
        # 返回渲染后的任务列表
        return self.render()

    # 渲染任务列表的方法
    def render(self) -> str:
        # 如果没有任务，返回无任务消息
        if not self.items:
            return "No todos."
        # 初始化行列表
        lines = []
        # 遍历每个任务
        for item in self.items:
            # 根据状态选择标记
            marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}[item["status"]]
            # 添加格式化的任务行
            lines.append(f"{marker} #{item['id']}: {item['text']}")
        # 计算完成的任务数量
        done = sum(1 for t in self.items if t["status"] == "completed")
        # 添加完成统计
        lines.append(f"\n({done}/{len(self.items)} completed)")
        # 返回连接后的字符串
        return "\n".join(lines)


# 创建 TodoManager 的全局实例
TODO = TodoManager()


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
        # 读取文件内容并分割为行
        lines = safe_path(path).read_text().splitlines()
        # 如果设置了限制，且行数超过限制，截取并添加省略消息
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
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
        return f"Wrote {len(content)} bytes"
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


# 定义工具处理器映射，将工具名称映射到对应的处理函数
TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),  # bash 工具：运行 shell 命令
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),  # read_file 工具：读取文件
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),  # write_file 工具：写入文件
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),  # edit_file 工具：编辑文件
    "todo":       lambda **kw: TODO.update(kw["items"]),  # todo 工具：更新任务列表
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
    {"name": "todo", "description": "Update task list. Track progress on multi-step tasks.",  # todo 工具描述
     "input_schema": {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "string"}, "text": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}, "required": ["id", "text", "status"]}}}, "required": ["items"]}},  # 输入模式：items 数组，每个项有 id, text, status
]


# -- Agent loop with nag reminder injection --
# 定义代理循环函数，包含 nag 提醒注入
def agent_loop(messages: list):
    # 初始化自上次使用 todo 工具以来的轮数
    rounds_since_todo = 0
    # 无限循环，直到停止
    while True:
        # Nag 提醒在下面与工具结果一起注入
        # 创建消息，使用模型、系统提示、消息历史、工具和最大 token 数
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        # 将助手响应添加到消息历史
        messages.append({"role": "assistant", "content": response.content})
        # 如果停止原因是工具使用，继续；否则返回
        if response.stop_reason != "tool_use":
            return
        # 初始化结果列表
        results = []
        # 初始化是否使用了 todo 工具
        used_todo = False
        # 遍历响应内容中的每个块
        for block in response.content:
            # 如果是工具使用块
            if block.type == "tool_use":
                # 获取对应的处理器
                handler = TOOL_HANDLERS.get(block.name)
                try:
                    # 调用处理器，如果存在；否则返回未知工具消息
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as e:
                    # 处理异常
                    output = f"Error: {e}"
                # 打印工具名称和输出前200字符
                print(f"> {block.name}: {str(output)[:200]}")
                # 添加工具结果到结果列表
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)})
                # 如果使用了 todo 工具，设置标志
                if block.name == "todo":
                    used_todo = True
        # 如果使用了 todo，重置轮数；否则增加轮数
        rounds_since_todo = 0 if used_todo else rounds_since_todo + 1
        # 如果轮数 >= 3，插入提醒
        if rounds_since_todo >= 3:
            results.insert(0, {"type": "text", "text": "<reminder>Update your todos.</reminder>"})
        # 将结果作为用户消息添加到历史
        messages.append({"role": "user", "content": results})


# 如果作为主程序运行
if __name__ == "__main__":
    # 初始化历史消息列表
    history = []
    # 无限循环，等待用户输入
    while True:
        try:
            # 获取用户输入，带颜色提示
            query = input("\033[36ms03 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            # 处理 EOF 或中断，退出
            break
        # 如果输入是退出命令，退出
        if query.strip().lower() in ("q", "exit", ""):
            break
        # 将用户查询添加到历史
        history.append({"role": "user", "content": query})
        # 调用代理循环
        agent_loop(history)
        # 获取最后的消息内容
        response_content = history[-1]["content"]
        # 如果是列表，遍历并打印文本块
        if isinstance(response_content, list):
            for block in response_content:
                if hasattr(block, "text"):
                    print(block.text)
        # 打印空行
        print()
