#!/usr/bin/env python3
# Harness: persistent tasks -- goals that outlive any single conversation.
"""
s07_task_system.py - Tasks

这一章的主题是“让任务活在对话之外”。

前面几章里，agent 的状态主要存在 messages 里；一旦上下文压缩、
会话重启，模型就可能忘记之前答应要做什么。

这一版把任务单独存到 .tasks/ 目录里，每个任务就是一个 JSON 文件：

    .tasks/
      task_1.json  {"id":1, "subject":"...", "status":"completed", ...}
      task_2.json  {"id":2, "blockedBy":[1], "status":"pending", ...}
      task_3.json  {"id":3, "blockedBy":[2], "blocks":[], ...}

    Dependency resolution:
    +----------+     +----------+     +----------+
    | task 1   | --> | task 2   | --> | task 3   |
    | complete |     | blocked  |     | blocked  |
    +----------+     +----------+     +----------+
         |                ^
         +--- completing task 1 removes it from task 2's blockedBy

老师视角看这章，请先抓住两个关键词：

1. persist
   任务会落盘，所以不会随着上下文压缩一起消失。
2. dependency graph
   任务之间不是平铺列表，而是可以互相依赖。

一句话总结：
"State that survives compression -- because it's outside the conversation."

如果你是零基础，可以先把整份代码当成一个“三层小系统”：

第 1 层：TaskManager
负责把任务保存到 `.tasks/` 文件夹里。

第 2 层：工具函数
负责读文件、写文件、跑命令、创建任务、更新任务。

第 3 层：agent_loop
负责和大模型来回对话：
模型想调用工具 -> Python 真去执行 -> 再把结果还给模型。

建议你的阅读顺序是：
1. 先看 TaskManager，理解“任务数据长什么样”
2. 再看 TOOL_HANDLERS / TOOLS，理解“模型怎么拿到工具”
3. 最后看 agent_loop，理解“为什么 agent 能一轮一轮自己干活”
"""

# 先别急着背这些 import。
# 这里的模块分三类：
# 1. 标准库：json / os / subprocess / Path
# 2. 第三方库：Anthropic / dotenv
# 3. 真正重要的不是“导了什么”，而是后面会得到三个核心对象：
#    WORKDIR / client / TASKS
import json
import os
import subprocess
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

# 读取 .env，让本地环境变量可用。
# override=True 表示：如果 .env 里有同名值，就以 .env 为准。
load_dotenv(override=True)

# 如果你配置了自定义网关地址，就把另一个可能冲突的 token 环境变量移除。
# 这是“避免配置互相打架”的小细节。
if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

# WORKDIR 是整个 agent 的活动范围。
# 后面读文件、写文件、跑命令，默认都以这里为根目录。
WORKDIR = Path.cwd()

# client 负责真正调用大模型 API。
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))

# MODEL 决定这次对话用哪个模型。
MODEL = os.environ["MODEL_ID"]

# .tasks/ 是这一章最关键的“长期记忆区”。
TASKS_DIR = WORKDIR / ".tasks"

# SYSTEM 是给模型的角色说明。
# 重点不是“你是聊天助手”，而是“你是 coding agent，并且要用任务工具”。
SYSTEM = f"You are a coding agent at {WORKDIR}. Use task tools to plan and track work."


# -- TaskManager: CRUD with dependency graph, persisted as JSON files --
# 这是本章主角。
# 你可以把 TaskManager 想成“一个会把任务保存到磁盘里的小项目经理”。
class TaskManager:
    def __init__(self, tasks_dir: Path):
        # self.dir 就是任务仓库的位置。
        # 你可以把它想成“这个项目的任务文件柜”。
        self.dir = tasks_dir
        # 第一次运行时，如果 .tasks/ 不存在，就先创建出来。
        self.dir.mkdir(exist_ok=True)
        # 任务 id 不是写死从 1 开始，而是从“当前最大 id + 1”继续。
        # 这样即使程序重启，也不会把旧任务编号覆盖掉。
        self._next_id = self._max_id() + 1

    def _max_id(self) -> int:
        # 这里去扫描 .tasks/task_*.json 文件，从文件名里提取编号。
        # 例如 task_3.json -> 3
        ids = [int(f.stem.split("_")[1]) for f in self.dir.glob("task_*.json")]
        return max(ids) if ids else 0

    def _load(self, task_id: int) -> dict:
        # _load() 做的事很像：
        # “去文件柜里找到编号为 task_id 的那张任务卡片，并把它读出来”
        path = self.dir / f"task_{task_id}.json"
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        # read_text() 读到的是字符串，json.loads() 才会把它变回 Python 字典。
        return json.loads(path.read_text())

    def _save(self, task: dict):
        # _save() 刚好和 _load() 相反：
        # “把内存里的任务卡片，重新写回文件柜”
        path = self.dir / f"task_{task['id']}.json"
        # indent=2 纯粹是为了让文件更容易被人类阅读，不影响程序逻辑。
        path.write_text(json.dumps(task, indent=2))

    def create(self, subject: str, description: str = "") -> str:
        # 一个任务本质上就是一个字典。
        # 先别把它想复杂：就是“标题 + 描述 + 状态 + 依赖关系”。
        task = {
            "id": self._next_id, "subject": subject, "description": description,
            "status": "pending", "blockedBy": [], "blocks": [], "owner": "",
        }
        self._save(task)
        self._next_id += 1
        # 这里返回 JSON 字符串而不是字典，是为了直接把结果喂给模型看。
        return json.dumps(task, indent=2)

    def get(self, task_id: int) -> str:
        # get() 就是“读取某个任务的完整详情”。
        return json.dumps(self._load(task_id), indent=2)

    def update(self, task_id: int, status: str = None,
               add_blocked_by: list = None, add_blocks: list = None) -> str:
        # update() 是整章最值得精读的函数。
        # 因为“任务系统”真正难的不是 create，而是：
        # 1. 改状态
        # 2. 维护依赖关系
        task = self._load(task_id)

        if status:
            # 这里只允许三种状态，避免模型乱写出别的字符串。
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Invalid status: {status}")
            task["status"] = status

            # 这是一个关键设计：
            # 某个任务一旦完成，它不该再继续阻塞别人。
            # 所以要去把“别人 blockedBy 里对它的依赖”清掉。
            if status == "completed":
                self._clear_dependency(task_id)

        if add_blocked_by:
            # blockedBy 表示“我被谁卡住了”。
            # list(set(...)) 的写法是在做去重，避免同一个依赖加两次。
            #
            # 例如：
            # 任务 3 的 blockedBy = [1, 2]
            # 意思就是：1 和 2 没做完之前，3 很难开始。
            task["blockedBy"] = list(set(task["blockedBy"] + add_blocked_by))

        if add_blocks:
            # blocks 表示“我会卡住谁”。
            #
            # 例如：
            # 任务 1 的 blocks = [2]
            # 意思就是：任务 2 要等任务 1。
            task["blocks"] = list(set(task["blocks"] + add_blocks))

            # 这里是老师最希望你看懂的地方：
            # 依赖关系最好双向维护。
            #
            # 如果任务 1 blocks 任务 2，
            # 那么任务 2 也应该自动出现 blockedBy=[1]。
            #
            # 不然两个字段会彼此不同步，后面就容易乱。
            for blocked_id in add_blocks:
                try:
                    # 先把“被挡住的那个任务”读出来。
                    blocked = self._load(blocked_id)
                    if task_id not in blocked["blockedBy"]:
                        # 再把当前任务 id 塞进对方的 blockedBy 里。
                        blocked["blockedBy"].append(task_id)
                        self._save(blocked)
                except ValueError:
                    # 如果依赖的那个任务不存在，当前实现选择“跳过”。
                    # 这是一种比较宽松的容错策略。
                    pass

        self._save(task)
        return json.dumps(task, indent=2)

    def _clear_dependency(self, completed_id: int):
        """Remove completed_id from all other tasks' blockedBy lists."""
        # 这一步非常像“项目里某个前置任务做完后，通知所有后续任务解锁”。
        #
        # completed_id = 已经完成的任务编号
        # 我们要做的事就是：
        # 去所有任务里看看，谁还在说“我被它卡住了”
        # 如果有，就把这个依赖删掉
        for f in self.dir.glob("task_*.json"):
            task = json.loads(f.read_text())
            if completed_id in task.get("blockedBy", []):
                task["blockedBy"].remove(completed_id)
                self._save(task)

    def list_all(self) -> str:
        # list_all() 返回的是“简洁版任务总览”，不是完整 JSON。
        # 因为人类和模型在很多时候只需要快速扫一眼。
        tasks = []

        # sorted(...) 是为了让任务显示顺序稳定，通常会按文件名顺序输出。
        for f in sorted(self.dir.glob("task_*.json")):
            tasks.append(json.loads(f.read_text()))

        if not tasks:
            return "No tasks."

        lines = []
        for t in tasks:
            # 这些符号只是为了更适合在终端里快速扫读：
            # [ ] 未开始, [>] 进行中, [x] 已完成
            marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}.get(t["status"], "[?]")
            blocked = f" (blocked by: {t['blockedBy']})" if t.get("blockedBy") else ""
            lines.append(f"{marker} #{t['id']}: {t['subject']}{blocked}")
        return "\n".join(lines)


TASKS = TaskManager(TASKS_DIR)


# -- Base tool implementations --
# 到这里开始，你可以把代码分成两层：
# 1. TaskManager：存任务
# 2. Tool functions：让模型“有手有脚”，能读文件、写文件、改任务
def safe_path(p: str) -> Path:
    # 这是一个很重要的安全习惯。
    # 模型给出 path 时，我们不应该直接信任，而是要检查它有没有跑出工作目录。
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path

def run_bash(command: str) -> str:
    # 让模型能跑命令很强大，但也很危险，所以这里有最基础的黑名单。
    # 注意：这不算完美安全，只是教学版里的最低限度保护。
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        # subprocess.run(...) 可以理解成：
        # “请 Python 去操作系统里真的执行这条命令，然后把结果带回来”
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"

def run_read(path: str, limit: int = None) -> str:
    try:
        # splitlines() 会把文本拆成一行一行，后面 limit 才好截断。
        lines = safe_path(path).read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"

def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        # parents=True 表示：如果上层目录不存在，就一路帮你创建出来。
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes"
    except Exception as e:
        return f"Error: {e}"

def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = safe_path(path)
        c = fp.read_text()
        if old_text not in c:
            return f"Error: Text not found in {path}"
        # replace(..., 1) 里的 1 表示“只改第一次出现的地方”。
        fp.write_text(c.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


# TOOL_HANDLERS 是“Python 这边真正怎么执行”。
# 也就是说：模型说“我要调用 task_create”，程序就来这里找到对应函数。
TOOL_HANDLERS = {
    # 前四个是基础工具：命令行 / 读 / 写 / 改
    "bash":        lambda **kw: run_bash(kw["command"]),
    "read_file":   lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file":  lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":   lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),

    # 后四个是这一章新增的“任务工具”
    "task_create": lambda **kw: TASKS.create(kw["subject"], kw.get("description", "")),
    "task_update": lambda **kw: TASKS.update(kw["task_id"], kw.get("status"), kw.get("addBlockedBy"), kw.get("addBlocks")),
    "task_list":   lambda **kw: TASKS.list_all(),
    "task_get":    lambda **kw: TASKS.get(kw["task_id"]),
}

# TOOLS 是“给模型看的菜单”。
# 初学者最容易混淆这一点：
# - TOOL_HANDLERS：程序内部映射
# - TOOLS：发给模型的工具说明书（名称、描述、参数结构）
TOOLS = [
    # 你可以把 TOOLS 想成“给模型看的工具菜单”。
    # 模型只能看见这里声明过的工具。
    {"name": "bash", "description": "Run a shell command.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
    {"name": "task_create", "description": "Create a new task.",
     "input_schema": {"type": "object", "properties": {"subject": {"type": "string"}, "description": {"type": "string"}}, "required": ["subject"]}},
    {"name": "task_update", "description": "Update a task's status or dependencies.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}, "addBlockedBy": {"type": "array", "items": {"type": "integer"}}, "addBlocks": {"type": "array", "items": {"type": "integer"}}}, "required": ["task_id"]}},
    {"name": "task_list", "description": "List all tasks with status summary.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "task_get", "description": "Get full details of a task by ID.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]}},
]


def agent_loop(messages: list):
    # 这是 agent 的经典“思考 -> 调工具 -> 看结果 -> 继续思考”循环。
    # 如果你以后看别的 agent 框架，核心模式基本都长这样。
    #
    # 可以把它想成下面这个循环：
    #
    # 第 1 步：把当前上下文发给模型
    # 第 2 步：模型决定“直接回答”还是“先调工具”
    # 第 3 步：如果调工具，Python 真去执行
    # 第 4 步：把工具结果再发回模型
    # 第 5 步：重复，直到模型不再调工具
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        # 不管模型返回的是文本还是工具调用，我们都先把它加入历史。
        messages.append({"role": "assistant", "content": response.content})

        # stop_reason != tool_use 表示：这次模型不想再调用工具了，
        # 它已经准备好直接结束这一轮回答。
        if response.stop_reason != "tool_use":
            return
        results = []

        # response.content 里可能混着文本块和工具块。
        # 我们这里只处理工具块。
        for block in response.content:
            if block.type == "tool_use":
                # block.name 就是工具名，比如 "task_create"
                # block.input 就是这个工具要用到的参数
                handler = TOOL_HANDLERS.get(block.name)
                try:
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as e:
                    output = f"Error: {e}"

                # 这行 print 是给人类看的调试信息：方便你在终端观察 agent 调了什么工具。
                print(f"> {block.name}: {str(output)[:200]}")

                # tool_result 会重新喂给模型。
                # 于是模型下一步就能基于“刚刚工具返回了什么”继续推理。
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)})
        messages.append({"role": "user", "content": results})
        # 很多人第一次看到这里会疑惑：为什么 tool_result 要塞成 user 消息？
        # 因为这是 Anthropic 工具调用协议的一部分，工具结果需要作为下一轮输入返回给模型。
        #
        # 虽然看起来像“假装用户说话”，
        # 但其实这只是协议规定的数据格式。


if __name__ == "__main__":
    # 这里是最外层的命令行交互壳子。
    # history 就是当前会话累计下来的消息历史。
    #
    # 注意：
    # history 保存的是“本次会话的消息”
    # TASKS 保存的是“跨会话仍然存在的任务”
    #
    # 这正是本章最重要的区别：
    # 对话会结束，但任务文件还在。
    history = []
    while True:
        try:
            query = input("\033[36ms07 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)

        # agent_loop 结束后，history 的最后一条通常就是模型最新的回答内容。
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if hasattr(block, "text"):
                    # 只有 text 块才直接打印给人看。
                    # 工具块已经在 agent_loop 里处理过了。
                    print(block.text)
        print()
