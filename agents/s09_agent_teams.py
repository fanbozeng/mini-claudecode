#!/usr/bin/env python3
# Harness: team mailboxes -- multiple models, coordinated through files.

"""
████████████████████████████████████████████████████████████████████████████
★★★ 🏢 博士生&小学生智力讲解：AI代理团队协作系统 🏢 ★★★

亲爱的各位诸位：

这个程序讲的是："多个AI秘书如何一起工作"

如果你看过 s08_background_tasks.py，那了解了"一个秘书在后台工作"
现在 s09 讲的是："怎么同时雇佣好几个秘书，让他们互相聊天"

想象你的秘书事务所升级了！
- 旧版本（s08）：1个秘书，会在后台任务
- 新版本（s09）：🎉 多个秘书，会互相通信！

████████████████████████████████████████████████████████████████████████████

【核心概念：文件邮件系统】
==========================

问题：多个秘书怎样才能安全地互相通信？

方案：用"邮件文件"！

    Alice 秘书          Bob 秘书
    +----------+        +----------+
    | 工作中   |        | 工作中   |
    |（线程1） |        |（线程2） | 每个秘书在自己的线程里
    +----------+        +----------+
         │                   │
         v                   v
    alice.jsonl          bob.jsonl
    (Alice的邮件)        (Bob的邮件)
         ↑                   ↑
         │                   │
    "嘿Alice,            "嘿Bob,
     我完成了!"          你来帮我!"

为什么用文件？
✓ 安全（不会互相打扰）
✓ 简单（就是写/读文件）
✓ 持久化（重启后消息不丢）
✓ 可以有多线程访问

【整个系统的结构】
==================

                  Lead（你）
                     │
         ┌───────────┼───────────┐
         │           │           │
         ▼           ▼           ▼
    Alice秘书     Bob秘书     Carol秘书
    (Thread1)   (Thread2)   (Thread3)
         │           │           │
         ▼           ▼           ▼
    alice.jsonl  bob.jsonl  carol.jsonl
    (邮件盒)     (邮件盒)   (邮件盒)

所有秘书通过"邮件盒"互相通信，互不干扰！

【5种消息类型】
================

在这个系统里，秘书们说话有规范！

1. "message"              → 普通信息（"嘿Alice，请做X")
2. "broadcast"            → 广播消息（"各位，大家都来听!")
3. "shutdown_request"     → 关闭请求（要秘书停止工作）
4. "shutdown_response"    → 关闭响应（同意/拒绝停止）
5. "plan_approval_response" → 计划批准（批准秘书的计划）

████████████████████████████████████████████████████████████████████████████

现在让我们一行行读代码...
"""

# ========================= 导入部分 =========================

# 处理 JSON 数据（秘书们的邮件都是 JSON 格式）
import json
# 操作系统相关（路径、环境变量等）
import os
# 运行外部命令（秘书执行 bash 命令）
import subprocess
# 线程模块 ★ 关键！让多个秘书同时工作
import threading
# 时间模块（给邮件加时间戳）
import time
# 路径操作（比字符串更好用）
from pathlib import Path

# ★★★ Claude AI 客户端 - 秘书的"大脑"
from anthropic import Anthropic
# 加载 .env 文件的配置
from dotenv import load_dotenv

# ========================= 初始化 =========================

load_dotenv(override=True)
if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

# 秘书事务所的位置
WORKDIR = Path.cwd()
# 连接到 Claude AI
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
# 选择哪个 Claude 模型
MODEL = os.environ["MODEL_ID"]
# 团队办公室的目录
TEAM_DIR = WORKDIR / ".team"
# 邮件盒的目录（每个秘书一个邮件盒）
INBOX_DIR = TEAM_DIR / "inbox"

# Lead（你）的系统提示
SYSTEM = f"You are a team lead at {WORKDIR}. Spawn teammates and communicate via inboxes."

# ★ 定义允许的消息类型（防止秘书们乱说话）
VALID_MSG_TYPES = {
    "message",              # 普通消息
    "broadcast",             # 广播消息
    "shutdown_request",      # 关闭请求
    "shutdown_response",     # 关闭响应
    "plan_approval_response" # 计划批准响应
}


# ═══════════════════════════════════════════════════════════════
# ★★★ 第一部分：MessageBus（秘书的邮件系统）★★★
# ═══════════════════════════════════════════════════════════════

class MessageBus:
    """
    ★ MessageBus = "邮件总站"
    
    就像邮政总局一样，负责：
    1. 收邮件（接收消息）
    2. 存邮件（存储在 JSONL 文件里）
    3. 送邮件（从收件箱取出）
    4. 广播（一推多）
    
    核心特色：文件很简单，就是追加写
    """
    
    def __init__(self, inbox_dir: Path):
        """初始化邮件系统"""
        # 设置邮件盒的位置
        self.dir = inbox_dir
        # 创建目录（如果不存在）
        self.dir.mkdir(parents=True, exist_ok=True)
    
    def send(self, sender: str, to: str, content: str,
             msg_type: str = "message", extra: dict = None) -> str:
        """
        ★ 发送一条消息
        
        参数：
        - sender: 谁发的（比如"lead"或"alice"）
        - to: 发给谁（比如"alice"）
        - content: 邮件内容（文字）
        - msg_type: 消息类型（普通/广播/等等）
        - extra: 额外信息（可选）
        
        流程：
        1. 检查消息类型是否有效
        2. 创建一个邮件对象（JSON格式）
        3. 追加写入到对方的邮件盒（alice.jsonl）
        4. 返回发送确认
        """
        
        # ★ 检查消息类型是否有效
        if msg_type not in VALID_MSG_TYPES:
            return f"Error: Invalid type '{msg_type}'. Valid: {VALID_MSG_TYPES}"
        
        # 创建邮件对象（字典）
        msg = {
            "type": msg_type,           # 消息类型
            "from": sender,              # 谁发的
            "content": content,          # 邮件内容
            "timestamp": time.time(),    # 时间戳（发送时间）
        }
        
        # 如果有额外信息，添加到邮件
        if extra:
            msg.update(extra)
        
        # 计算收件方的邮件盒路径
        # 比如：.team/inbox/alice.jsonl
        inbox_path = self.dir / f"{to}.jsonl"
        
        # ★ 以"追加"模式打开文件，并写入
        # "a" = append（追加）
        # 这样即使多个线程同时写，也不会互相覆盖
        with open(inbox_path, "a") as f:
            # 把邮件转为 JSON，然后写一行
            f.write(json.dumps(msg) + "\n")
        
        # 返回发送确认
        return f"Sent {msg_type} to {to}"
    
    def read_inbox(self, name: str) -> list:
        """
        ★ 收邮件（读取并清空收件箱）
        
        参数：
        - name: 谁的收件箱（比如"alice"）
        
        返回：
        - 所有邮件的列表
        
        流程：
        1. 找到这个人的邮件盒文件（alice.jsonl）
        2. 读出所有邮件（每行一个 JSON）
        3. 清空文件（删除所有邮件）
        4. 返回邮件列表
        
        ★ 关键：这是"排出"操作，读完就删！
        """
        
        # 计算邮件盒的路径
        inbox_path = self.dir / f"{name}.jsonl"
        
        # 如果文件不存在，返回空列表
        if not inbox_path.exists():
            return []
        
        # 初始化邮件列表
        messages = []
        
        # 读取文件内容，按行分割
        for line in inbox_path.read_text().strip().splitlines():
            if line:
                # 每一行都是一个 JSON 邮件，解析它
                messages.append(json.loads(line))
        
        # ★ 清空文件（"收完了的垃圾邮箱，就清空了"）
        inbox_path.write_text("")
        
        # 返回所有邮件
        return messages
    
    def broadcast(self, sender: str, content: str, teammates: list) -> str:
        """
        ★ 广播消息（一个人给所有人发消息）
        
        参数：
        - sender: 谁发的广播
        - content: 广播内容
        - teammates: 所有队友的名单
        
        流程：
        1. 遍历所有队友
        2. 逐个发送消息
        3. 返回发送了多少个
        """
        
        # 计数器：发送了多少条
        count = 0
        
        # 遍历所有队友
        for name in teammates:
            if name != sender:  # 不能给自己发
                # 发送广播消息
                self.send(sender, name, content, "broadcast")
                count += 1
        
        # 返回广播确认
        return f"Broadcast to {count} teammates"


# ★ 创建全局的邮件总线实例
BUS = MessageBus(INBOX_DIR)


# -- TeammateManager: persistent named agents with config.json --
class TeammateManager:
    """
    ★ TeammateManager = "秘书管理公司"
    
    职责：
    1. 招聘（spawn）新秘书
    2. 启动秘书的工作线程
    3. 记录秘书信息到 config.json
    4. 追踪秘书状态
    
    关键点：每个秘书在**独立的线程**里运行！
    """
    
    # 初始化方法
    def __init__(self, team_dir: Path):
        """初始化秘书管理公司"""
        # 设置团队办公室位置
        self.dir = team_dir
        # 创建目录如果不存在
        self.dir.mkdir(exist_ok=True)
        # 设置配置文件路径
        self.config_path = self.dir / "config.json"
        # 加载配置
        self.config = self._load_config()
        # 初始化线程字典
        self.threads = {}

    # 私有方法，加载配置
    def _load_config(self) -> dict:
        # 如果配置文件存在，读取并解析
        if self.config_path.exists():
            return json.loads(self.config_path.read_text())
        # 否则返回默认配置
        return {"team_name": "default", "members": []}

    # 私有方法，保存配置
    def _save_config(self):
        # 将配置写入文件，缩进 2
        self.config_path.write_text(json.dumps(self.config, indent=2))

    # 私有方法，查找成员
    def _find_member(self, name: str) -> dict:
        # 遍历成员列表
        for m in self.config["members"]:
            if m["name"] == name:
                # 返回匹配的成员
                return m
        # 如果未找到，返回 None
        return None

    # 生成队友的方法
    def spawn(self, name: str, role: str, prompt: str) -> str:
        """
        ★ 招聘新秘书（或重新启动旧秘书）
        
        想象场景：
        "嘿 HR，请招聘一个新秘书Alice，她是代码编写员，
         初始任务是'写一个Hello World程序'"
        
        参数：
        - name: 秘书的名字（如"alice"）
        - role: 职位（如"coder", "reviewer"等）
        - prompt: 初始任务（秘书拿到的第一个任务）
        
        核心流程（5个步骤）：
        ═══════════════════════════════════════════
        
        【步骤1】检查这个名字是否已经存在
        ─────────────────────────────────────
        先look看 config.json 里有没有这个人
        - 如果有这个人，检查她的状态
        - 状态必须是 "idle" 或 "shutdown"（闲置或关闭状态）
        - 如果状态是 "working"，说明她还在工作，不能重新启动
        
        【步骤2】创建或更新成员信息
        ─────────────────────────────────────
        如果是新秘书：
          member = {
            "name": "alice",
            "role": "coder",
            "status": "working"   ← 标记为正在工作
          }
        
        如果是旧秘书被重新启动：
          member["status"] = "working"
          member["role"] = role   ← 可能分配新职位
        
        【步骤3】保存配置到 config.json
        ─────────────────────────────────────
        把更新后的成员列表写回文件
        "记录在案"
        
        【步骤4】创建线程（秘书要在"后台"工作）
        ─────────────────────────────────────
        创建一个新的 Python 线程（Thread）
        - 线程的目标函数：_teammate_loop
        - 参数：name（名字）, role（职位）, prompt（任务）
        - daemon=True 意思是"当主程序结束时，我也停止"
        
        【步骤5】启动线程
        ─────────────────────────────────────
        thread.start() 就像按下"开始工作"按钮
        现在秘书在后台独立工作，不会阻塞主程序
        
        ★ 关键概念解释：为什么需要线程？
        
        如果不用线程：
        ┌──────────┐
        │ Lead     │
        │ (你)     │
        └────┬─────┘
             │ 派 Alice 去做任务
             │ ...等待 Alice 完成（卡住了！）
             ▼
        ┌──────────┐
        │ Alice    │
        │ 在工作   │
        └──────────┘
        
        如果用线程：
        ┌──────────┐              ┌──────────┐
        │ Lead     │              │ Alice    │
        │ (你)     │ ───派──→     │ 在后台   │
        │ 继续工作 │              │ 工作     │
        └──────────┘              └──────────┘
        
        Lead 不用等，可以继续做别的事！
        """
        # 【步骤1】检查这个名字是否已经存在
        member = self._find_member(name)
        if member:
            # ★ 如果成员存在，检查状态
            if member["status"] not in ("idle", "shutdown"):
                # 如果秘书还在工作，拒绝重新启动
                return f"Error: '{name}' is currently {member['status']}"
            # 【步骤2】更新状态和角色
            member["status"] = "working"
            member["role"] = role
        else:
            # ★ 如果是新秘书，创建成员记录
            member = {"name": name, "role": role, "status": "working"}
            # 添加到成员列表
            self.config["members"].append(member)
        
        # 【步骤3】保存配置
        self._save_config()
        
        # 【步骤4】创建新线程
        thread = threading.Thread(
            target=self._teammate_loop,
            args=(name, role, prompt),
            daemon=True,
        )
        # 存储线程（以便后续管理）
        self.threads[name] = thread
        
        # 【步骤5】启动线程
        thread.start()
        
        # 返回成功信息
        return f"Spawned '{name}' (role: {role})"

    # 私有方法，队友循环
    def _teammate_loop(self, name: str, role: str, prompt: str):
        """
        ★ 秘书的"工作循环" ★
        
        这是秘书在后台做的事情。秘书不停地循环这个过程：
        1. 检查邮件盒
        2. 问 Claude AI "我应该干什么？"
        3. AI 回答"做这个工具"
        4. 秘书执行工具
        5. 循环回到第 1 步，直到任务完成
        
        ★ 类比：秘书的日常工作
        ═══════════════════════════════════════════
        
        08:00 秘书 Alice 上班
             "早上好，你今天的任务是：写一个 Python 文件"
        
        【第1轮循环】
        08:05 Alice 检查邮件盒：有没有新消息？（没有）
        08:06 Alice 问 Claude AI：我应该做什么？
             Claude AI："你需要写一个文件，起名叫 test.py" 
        08:07 Alice 用"写文件"工具，写了 test.py
        
        【第2轮循环】
        08:10 Alice 检查邮件盒：有没有新消息？
             "嘿 Alice，请给 test.py 加上注释"
        08:11 Alice 告诉 Claude AI："我收到一条消息..."
             Claude AI："你需要编辑文件，加上注释"
        08:12 Alice 用"编辑文件"工具，加了注释
        
        【第3轮循环】
        08:15 Alice 检查邮件盒：有没有新消息？（没有）
        08:16 Alice 问 Claude AI：我应该做什么？
             Claude AI："没有更多任务了，你完成了！"
        08:17 Alice 停止循环，标记状态为 "idle"（空闲）
        
        ★ 核心流程图
        ═══════════════════════════════════════════
        
        初始化
        ↓
        ┌─────────────────────────────────────┐
        │   开始循环（最多 50 轮）             │
        │   （防止无限循环）               │
        └─────────────────────────────────────┘
                          ↓
        ┌─────────────────────────────────────┐
        │ 【步骤1】检查邮件                   │
        │ inbox = BUS.read_inbox(name)     │
        │ （从 alice.jsonl 读取所有邮件）  │
        └─────────────────────────────────────┘
                          ↓
        ┌─────────────────────────────────────┐
        │ 【步骤2】把邮件内容添加到           │
        │ Claude AI 的对话                  │
        │ "Claude 你看，这是我收到的消息..."│
        └─────────────────────────────────────┘
                          ↓
        ┌─────────────────────────────────────┐
        │ 【步骤3】问 Claude AI               │
        │ "我应该干什么？"                 │
        │ → claude.messages.create()      │
        │ → 得到 response                 │
        └─────────────────────────────────────┘
                          ↓
        ┌─────────────────────────────────────┐
        │ 【步骤4】检查 AI 的回答             │
        │ 如果说"我需要用工具"：           │
        │   提取工具名和参数                  │
        │   执行工具                         │
        │   把结果告诉 Claude AI            │
        │   继续循环                         │
        │ 如果说"任务完成了":               │
        │   退出循环                         │
        └─────────────────────────────────────┘
                          ↓
        任务完成，标记状态为 "idle"
        
        ★ 关键技术点
        ═══════════════════════════════════════════
        
        1. 消息历史记录（messages）
           ─────────────────────────
           维护一个对话历史，像这样：
           
           messages = [
             {"role": "user", "content": "初始任务"},
             {"role": "assistant", "content": "我将使用write_file"},
             {"role": "user", "content": [{"type": "tool_result", ...}]},
             ...
           ]
           
           每一轮对话都被记录下来，这样 Claude AI 就能理解上下文
        
        2. 工具执行（tool_use）
           ───────────────────────
           当 Claude AI 决定使用工具时，response.content 会有
           type == "tool_use" 的块。我们需要：
           - 提取工具名（block.name）
           - 提取参数（block.input）
           - 调用 self._exec() 执行它
           - 收集结果
           - 添加到下一轮对话
        
        3. 停止条件（stop_reason）
           ──────────────────────
           - "tool_use": 还需要工具，继续循环
           - 其他原因（"end_turn" 等）：任务完成，退出
        
        4. 循环保护（range(50)）
           ──────────────────────
           最多循环 50 次，防止无限循环
           （以防万一 AI 一直想用工具）
        """
        # ★ 系统提示：告诉 Claude AI"你是谁"
        sys_prompt = (
            f"You are '{name}', role: {role}, at {WORKDIR}. "
            f"Use send_message to communicate. Complete your task."
        )
        
        # ★ 对话历史：存储所有的对话记录
        messages = [{"role": "user", "content": prompt}]
        
        # ★ 获取这个秘书可用的工具
        tools = self._teammate_tools()
        
        # ★ 循环最多 50 次（防止无限循环）
        for iteration in range(50):
            # 【步骤1】检查邮件盒（读取并清空）
            inbox = BUS.read_inbox(name)
            
            # 【步骤2】如果有邮件，添加到对话历史
            for msg in inbox:
                # 把新邮件纳入对话
                messages.append({"role": "user", "content": json.dumps(msg)})
            
            try:
                # 【步骤3】问 Claude AI 应该做什么
                response = client.messages.create(
                    model=MODEL,
                    system=sys_prompt,
                    messages=messages,
                    tools=tools,
                    max_tokens=8000,
                )
            except Exception as e:
                # 如果 API 调用出错，停止工作（避免死循环）
                break
            
            # ★ 把 AI 的回答添加到对话历史
            messages.append({"role": "assistant", "content": response.content})
            
            # ★ 检查 AI 是否完成任务
            if response.stop_reason != "tool_use":
                # 如果 stop_reason 不是 "tool_use"（比如是 "end_turn"）
                # 说明 AI 已经完成，我们可以退出循环
                break
            
            # 【步骤4】AI 说要用工具，执行工具
            results = []
            
            # 遍历 AI 的回答块
            for block in response.content:
                if block.type == "tool_use":
                    # ★ 这是一个工具使用块
                    output = self._exec(name, block.name, block.input)
                    
                    # 打印执行结果（用于调试）
                    print(f"  [{name}] {block.name}: {str(output)[:120]}")
                    
                    # 收集工具执行结果
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(output),
                    })
            
            # ★ 把工具结果添加到对话历史
            # 这样下一轮 Claude AI 就能看到工具的结果
            messages.append({"role": "user", "content": results})
        
        # ★ 任务完成，更新秘书状态
        member = self._find_member(name)
        if member and member["status"] != "shutdown":
            # 标记为空闲（可以接新任务或者下班）
            member["status"] = "idle"
            # 保存配置
            self._save_config()

    # 私有方法，执行工具
    def _exec(self, sender: str, tool_name: str, args: dict) -> str:
        """
        ★ 执行工具的"调度员"
        
        想象场景：
        Alice AI 说："我想读取 hello.txt 文件"
        → 这个方法就负责把请求转发给正确的函数
        
        参数：
        - sender: 谁发出的请求（如"alice"）
        - tool_name: 要使用哪个工具（如"read_file"）
        - args: 工具的参数（如{"path": "hello.txt"}）
        
        返回值：
        - 工具执行的结果字符串
        
        ★ 工具列表（6个可用工具）
        ════════════════════════════════════
        
        1. "bash" - 执行 shell 命令
           ──────────────────────
           参数: {"command": "ls -la"}
           返回: 命令的输出
           用途: 运行任何 bash 命令
           例子: "python test.py"
        
        2. "read_file" - 读取文件
           ──────────────────────
           参数: {"path": "data.txt"}
           返回: 文件内容
           用途: 查看文件内容
           例子: "cat test.txt"
        
        3. "write_file" - 写入文件
           ──────────────────────
           参数: {"path": "output.txt", "content": "Hello World"}
           返回: 成功/失败消息
           用途: 创建或覆盖文件
           例子: "创建新文件 result.txt，内容是 SUCCESS"
        
        4. "edit_file" - 编辑文件（替换文本）
           ──────────────────────
           参数: {
             "path": "test.py",
             "old_text": "print('hi')",
             "new_text": "print('hello world')"
           }
           返回: 成功/失败消息
           用途: 精确替换文件中的文本
           例子: "把文件中的 'bug' 改成 'feature'"
        
        5. "send_message" - 发送消息给其他秘书
           ──────────────────────
           参数: {
             "to": "bob",
             "content": "嘿 Bob，帮我检查一下代码",
             "msg_type": "message"
           }
           返回: 发送成功消息
           用途: 秘书间通信
           例子: "Alice 让 Bob 帮她审核代码"
        
        6. "read_inbox" - 读取自己的邮件盒
           ──────────────────────
           参数: {} （无参数）
           返回: 所有未读邮件的 JSON 列表
           用途: 检查是否有其他秘书的消息
           例子: "检查有没有新邮件"
        
        ★ 工作流程
        ════════════════════════════════════
        
        AI 的请求
           ↓
        ┌─────────────────────────┐
        │ 工具名是什么？          │
        └─────────────────────────┘
           ↓
        ┌─ bash? ─┬─ read_file? ─┬─ write_file? ─┬─ ...
        │         │              │                │
        ▼         ▼              ▼                ▼
      bash()  read() write()  edit()  ...
        │         │              │                │
        └─────────┴──────────────┴────────────────┘
                   ↓
              执行函数，得到结果
                   ↓
              返回结果字符串
        """
        # ★ 根据工具名，转发到对应的函数
        
        if tool_name == "bash":
            # 执行 bash 命令
            return _run_bash(args["command"])
        
        if tool_name == "read_file":
            # 读取文件内容
            return _run_read(args["path"])
        
        if tool_name == "write_file":
            # 写入新文件
            return _run_write(args["path"], args["content"])
        
        if tool_name == "edit_file":
            # 编辑文件（替换文本）
            return _run_edit(args["path"], args["old_text"], args["new_text"])
        
        if tool_name == "send_message":
            # 发送消息给其他秘书
            return BUS.send(sender, args["to"], args["content"], args.get("msg_type", "message"))
        
        if tool_name == "read_inbox":
            # 读取并清空自己的邮件盒
            return json.dumps(BUS.read_inbox(sender), indent=2)
        
        # ★ 如果工具名不存在，返回错误
        return f"Unknown tool: {tool_name}"

    def _teammate_tools(self) -> list:
        """
        ★ 获取秘书可用的所有工具
        
        这个方法返回一个"工具菜单"，告诉 Claude AI：
        "你可以用这些工具"
        
        每个工具有三部分信息：
        1. name: 工具的名字
        2. description: 工具的说明（帮助 AI 理解用途）
        3. input_schema: 工具需要的参数（JSON Schema 格式）
        
        ★ 工具菜单的格式
        ════════════════════════════════════
        
        {
          "name": "bash",
          "description": "Run a shell command.",
          "input_schema": {
            "type": "object",
            "properties": {
              "command": {"type": "string"}
            },
            "required": ["command"]
          }
        }
        
        意思是：
        - 工具名叫 "bash"
        - 功能是"运行 shell 命令"
        - 需要一个参数叫 "command"（字符串类型）
        - "command" 是必需的
        
        ★ 类比：餐厅菜单
        ════════════════════════════════════
        
        如果没有菜单，顾客都不知道有什么菜
        有了菜单，顾客就能选择：
        "我要 A 菜（需要鸡肉）"
        "我要 B 菜（需要米饭+菜叶）"
        
        这里的工具菜单就是一样的道理
        """
        # ★ 返回 6 个工具的完整菜单
        return [
            {
                "name": "bash",
                "description": "Run a shell command.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"}
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "read_file",
                "description": "Read file contents.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "write_file",
                "description": "Write content to file.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "edit_file",
                "description": "Replace exact text in file.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old_text": {"type": "string"},
                        "new_text": {"type": "string"}
                    },
                    "required": ["path", "old_text", "new_text"]
                }
            },
            {
                "name": "send_message",
                "description": "Send message to a teammate.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string"},
                        "content": {"type": "string"},
                        "msg_type": {
                            "type": "string",
                            "enum": list(VALID_MSG_TYPES)
                        }
                    },
                    "required": ["to", "content"]
                }
            },
            {
                "name": "read_inbox",
                "description": "Read and drain your inbox.",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            },
        ]

    # 列出所有队友的方法
    def list_all(self) -> str:
        """
        ★ 列出所有队友信息（"公司成员名册"）
        
        这个方法就像 HR 部门拿出的"员工名单"
        
        返回值格式：
        ────────
        Team: default
          alice (coder): idle
          bob (reviewer): working
          carol (manager): shutdown
        
        展示出来的信息：
        ────────────
        - 团队名字（Team: default）
        - 每个成员的：
          * 名字
          * 职位（role）
          * 状态（idle/working/shutdown）
        
        用途：
        ────
        了解当前团队有哪些秘书，她们在做什么
        """
        # ★ 如果没有成员，返回特殊消息
        if not self.config["members"]:
            return "No teammates."
        
        # ★ 开始组建名册
        lines = [f"Team: {self.config['team_name']}"]
        
        # ★ 遍历所有成员
        for m in self.config["members"]:
            # 添加每个成员的信息
            lines.append(f"  {m['name']} ({m['role']}): {m['status']}")
        
        # ★ 把所有行连接成一个字符串并返回
        return "\n".join(lines)

    def member_names(self) -> list:
        """
        ★ 获取所有队友的名字列表
        
        如果 list_all 是"完整名册"
        那这个方法就是"只要名字列表"
        
        返回格式：
        ────────
        ["alice", "bob", "carol"]
        
        用途：
        ────
        当需要广播消息时，我们需要知道所有队友的名字
        比如：BUS.broadcast(sender, content, member_names())
             → 发送给 alice, bob, carol
        """
        # ★ 用列表推导式提取所有成员的名字
        return [m["name"] for m in self.config["members"]]


TEAM = TeammateManager(TEAM_DIR)


TEAM = TeammateManager(TEAM_DIR)


# ═══════════════════════════════════════════════════════════════
# ★★★ 第三部分：基础工具实现（秘书的"技能"）★★★
# ═══════════════════════════════════════════════════════════════

def _safe_path(p: str) -> Path:
    """
    ★ 路径安全检查（防止秘书乱动其他目录）
    
    想象场景：
    AI 秘书说："我想读取 /etc/passwd 文件"
    这个函数会说："不行！这个文件不在你的工作目录！"
    
    参数：
    ────
    p: 想要访问的路径（如"../../../etc/passwd"）
    
    返回值：
    ──────
    如果路径在工作目录内：返回绝对路径
    如果路径超出工作目录：抛出错误
    
    ★ 防护机制
    ════════════════════════════════════
    
    WORKDIR（工作目录）= /Users/caobenhui/Documents/learn/learn-claude-code
    
    允许访问：
    ✓ /Users/caobenhui/Documents/learn/learn-claude-code/test.txt
    ✓ /Users/caobenhui/Documents/learn/learn-claude-code/src/main.py
    
    不允许访问：
    ✗ /etc/passwd                （越界）
    ✗ /Users/caobenhui/secret.txt  （越界）
    ✗ ../../../../../../etc/passwd  （想偷跑，不行！)
    
    ★ 流程
    ════════════════════════════════════
    1. 把相对路径转换为绝对路径
       test.txt → /Users/caobenhui/.../learn-claude-code/test.txt
    
    2. 检查这个绝对路径是否在 WORKDIR 里面
       如果是：✓ 通过
       如果不是：✗ 抛出错误
    
    3. 返回安全的路径
    """
    # ★ 转换为绝对路径，并"解析"（比如消除 ..）
    path = (WORKDIR / p).resolve()
    
    # ★ 检查这个路径是否在工作目录内（safety check）
    if not path.is_relative_to(WORKDIR):
        # 如果不在工作目录内，拒绝
        raise ValueError(f"Path escapes workspace: {p}")
    
    # ★ 返回安全的路径
    return path


def _run_bash(command: str) -> str:
    """
    ★ 执行 shell 命令（秘书的"命令行技能"）
    
    想象场景：
    秘书说："我想运行 'ls -la' 命令看看文件"
    这个函数就会在系统里运行这个命令，返回结果
    
    参数：
    ────
    command: 要运行的 shell 命令（如"python test.py"）
    
    返回值：
    ──────
    命令的标准输出（或错误消息）
    
    ★ 危险命令检测
    ════════════════════════════════════
    
    有些命令太危险了，秘书不能用：
    - "rm -rf /" - 删除整个系统！
    - "sudo xxxxx" - 权限提升，很危险
    - "shutdown" - 关闭电脑
    - "reboot" - 重启电脑
    
    如果秘书试图用这些命令，函数会拒绝：
    "Error: Dangerous command blocked!"
    
    ★ 执行流程
    ════════════════════════════════════
    
    1. 检查命令是否危险
       ├─ 是 → 返回错误信息
       └─ 否 → 继续
    
    2. 创建一个 subprocess（子进程）
       子进程会独立执行命令
    
    3. 等待子进程完成（最多 30 秒）
       ├─ 完成 → 收集结果
       └─ 超时 → 杀死进程，返回"超时"消息
    
    4. 返回命令输出
    
    ★ 异常处理
    ════════════════════════════════════
    
    如果命令失败：
    - 返回 "Error: xxx" 消息
    - 包含错误信息或退出代码
    
    如果超时（30秒后还没完成）：
    - 强制杀死进程
    - 返回 "Timeout after 30s"
    """
    # ★ 列出危险命令黑名单
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot"]
    
    # ★ 检查命令是否包含危险关键词
    if any(d in command for d in dangerous):
        # 检查命令是否包含危险内容
        return "Error: Dangerous command blocked"
        # 如果是，返回错误消息
    try:
        # 尝试运行命令
        r = subprocess.run(
            command, shell=True, cwd=WORKDIR,
            capture_output=True, text=True, timeout=120,
        )
        # 使用 subprocess 运行命令，设置超时 120 秒
        out = (r.stdout + r.stderr).strip()
        # 获取输出并去除空白
        return out[:50000] if out else "(no output)"
        # 返回输出，如果太长则截断
    except subprocess.TimeoutExpired:
        # 如果超时，返回错误
        return "Error: Timeout (120s)"

def _run_read(path: str, limit: int = None) -> str:
    # 定义读取文件的函数
    try:
        # 尝试读取文件
        lines = _safe_path(path).read_text().splitlines()
        # 使用安全路径读取文件内容并分割为行
        if limit and limit < len(lines):
            # 如果设置了限制且行数超过限制
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
            # 截断行并添加省略信息
        return "\n".join(lines)[:50000]
        # 返回连接后的字符串，截断如果太长
    except Exception as e:
        # 如果出错，返回错误消息
        return f"Error: {e}"

def _run_write(path: str, content: str) -> str:
    # 定义写入文件的函数
    try:
        # 尝试写入文件
        fp = _safe_path(path)
        # 获取安全路径
        fp.parent.mkdir(parents=True, exist_ok=True)
        # 创建父目录如果不存在
        fp.write_text(content)
        # 写入内容
        return f"Wrote {len(content)} bytes"
        # 返回写入字节数
    except Exception as e:
        # 如果出错，返回错误消息
        return f"Error: {e}"

def _run_edit(path: str, old_text: str, new_text: str) -> str:
    # 定义编辑文件的函数
    try:
        # 尝试编辑文件
        fp = _safe_path(path)
        # 获取安全路径
        c = fp.read_text()
        # 读取文件内容
        if old_text not in c:
            # 如果旧文本不在文件中
            return f"Error: Text not found in {path}"
            # 返回错误
        fp.write_text(c.replace(old_text, new_text, 1))
        # 替换文本并写入
        return f"Edited {path}"
        # 返回成功消息
    except Exception as e:
        # 如果出错，返回错误消息
        return f"Error: {e}"


def _run_read(path: str, limit: int = None) -> str:
    """
    ★ 读取文件内容（秘书的"阅读技能"）
    
    想象场景：
    秘书说："我想看一下 config.json 文件的内容"
    这个函数就会把文件内容打印出来
    
    参数：
    ────
    path: 要读取的文件路径（如"config.json"）
    limit: 最多读取多少行（可选，比如 limit=10 只读前 10 行）
    
    返回值：
    ──────
    文件的完整内容（或前 N 行）
    
    ★ 工作流程
    ════════════════════════════════════
    
    1. 使用 _safe_path 检查路径是否安全
    2. 读取文件内容
    3. 如果指定了 limit，只返回前 limit 行
    4. 如果文件太大（超过 50000 字符），截断显示
    """
    try:
        # ★ 获取安全路径并读取文件
        lines = _safe_path(path).read_text().splitlines()
        
        # ★ 如果指定了行数限制
        if limit and limit < len(lines):
            # 只保留前 limit 行
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
        
        # ★ 返回文件内容（超过 50000 字符则截断）
        return "\n".join(lines)[:50000]
    except Exception as e:
        # ★ 如果出错，返回错误消息
        return f"Error: {e}"


def _run_write(path: str, content: str) -> str:
    """
    ★ 写入文件（秘书的"写作技能"）
    
    想象场景：
    秘书说："我要创建一个新文件 hello.txt，内容是 Hello World"
    这个函数就会创建这个文件并写入内容
    
    参数：
    ────
    path: 要写入的文件路径（如"output.txt"）
    content: 文件内容
    
    返回值：
    ──────
    成功信息，包括写入的字节数
    
    ★ 工作流程
    ════════════════════════════════════
    
    1. 使用 _safe_path 检查路径安全性
    2. 创建必要的目录（如果目录不存在）
    3. 写入文件内容（会覆盖旧文件）
    4. 返回成功信息
    
    ★ 特点
    ════════════════════════════════════
    - 会自动创建父目录
    - 如果文件已存在，会被覆盖
    - 返回写入的字节数
    """
    try:
        # ★ 获取安全路径
        fp = _safe_path(path)
        
        # ★ 创建父目录（如果不存在）
        fp.parent.mkdir(parents=True, exist_ok=True)
        
        # ★ 写入文件内容
        fp.write_text(content)
        
        # ★ 返回成功信息
        return f"Wrote {len(content)} bytes"
    except Exception as e:
        # ★ 如果出错，返回错误消息
        return f"Error: {e}"


def _run_edit(path: str, old_text: str, new_text: str) -> str:
    """
    ★ 编辑文件（秘书的"编辑技能"）
    
    想象场景：
    秘书说："我要把文件中的 'bug' 改成 'feature'"
    这个函数就会精确地替换这一部分
    
    参数：
    ────
    path: 要编辑的文件路径
    old_text: 要替换的旧文本（必须在文件中找到）
    new_text: 新文本
    
    返回值：
    ──────
    成功信息或错误（如果旧文本找不到）
    
    ★ 工作流程
    ════════════════════════════════════
    
    1. 使用 _safe_path 检查路径安全性
    2. 读取文件内容
    3. 查找旧文本是否存在
    4. 如果存在，替换为新文本（只替换第一个）
    5. 写入修改后的内容
    6. 返回成功信息
    
    ★ 特点
    ════════════════════════════════════
    - 只替换第一个匹配的文本（避免误替换）
    - 如果文本不存在，返回错误
    - 要求精确匹配（包括空格、换行等）
    - 用于精确编辑，不是盲目替换
    """
    try:
        # ★ 获取安全路径
        fp = _safe_path(path)
        
        # ★ 读取文件内容
        c = fp.read_text()
        
        # ★ 检查旧文本是否存在
        if old_text not in c:
            # 如果找不到，返回错误
            return f"Error: Text not found in {path}"
        
        # ★ 替换文本（只替换第一个）
        fp.write_text(c.replace(old_text, new_text, 1))
        
        # ★ 返回成功信息
        return f"Edited {path}"
    except Exception as e:
        # ★ 如果出错，返回错误消息
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
# ★★★ 第四部分：Lead 的工具集（Lead 专有工具）★★★
# ═══════════════════════════════════════════════════════════════

# ★ 工具调度器（Lead 可以使用的工具）
"""
这个字典把工具名字映射到处理函数
当 Lead 说"我要用 bash 工具"，系统就在这里查找

结构：
──────
{"工具名": 函数}

比如：
{"bash": lambda **kw: _run_bash(kw["command"])}
意思是："bash 工具 → 调用 _run_bash 函数"

★ Lambda 表达式简介
════════════════════════════════════

lambda **kw: func(kw["key"])

是一个"匿名函数"，相当于：

def handle(kw):
    return func(kw["key"])

**kw 的意思是"接收所有关键字参数"

为什么这样做？
因为 Anthropic API 会这样调用工具：
handler(command="ls -la")
或者
handler(path="test.txt", limit=10)

我们用 **kw 捕捉所有参数，然后从字典里提取
"""

TOOL_HANDLERS = {
    # ################################
    # ★ 文件操作工具（4 个）
    # ################################
    
    "bash":            lambda **kw: _run_bash(kw["command"]),
    # 工具：执行 shell 命令
    # 用途：运行任何系统命令
    # 例子：bash(command="python test.py")
    
    "read_file":       lambda **kw: _run_read(kw["path"], kw.get("limit")),
    # 工具：读取文件
    # 用途：查看文件内容
    # 例子：read_file(path="config.json")
    
    "write_file":      lambda **kw: _run_write(kw["path"], kw["content"]),
    # 工具：写入文件
    # 用途：创建或覆盖文件
    # 例子：write_file(path="output.txt", content="Hello")
    
    "edit_file":       lambda **kw: _run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    # 工具：编辑文件
    # 用途：精确替换文件中的文本
    # 例子：edit_file(path="test.py", old_text="bug", new_text="feature")
    
    # ################################
    # ★ 团队管理工具（3 个）
    # ################################
    
    "spawn_teammate":  lambda **kw: TEAM.spawn(kw["name"], kw["role"], kw["prompt"]),
    # 工具：招聘秘书
    # 用途：创建新的持久 AI 秘书
    # 例子：spawn_teammate(name="alice", role="coder", prompt="写一个 Hello World")
    
    "list_teammates":  lambda **kw: TEAM.list_all(),
    # 工具：列出所有秘书
    # 用途：了解当前团队成员及其状态
    # 例子：list_teammates()
    
    "broadcast":       lambda **kw: BUS.broadcast("lead", kw["content"], TEAM.member_names()),
    # 工具：广播消息
    # 用途：同时给所有秘书发送消息
    # 例子：broadcast(content="各位，停止工作")
    
    # ################################
    # ★ 消息通信工具（2 个）
    # ################################
    
    "send_message":    lambda **kw: BUS.send("lead", kw["to"], kw["content"], kw.get("msg_type", "message")),
    # 工具：发送消息给某个秘书
    # 用途：一对一通信
    # 例子：send_message(to="alice", content="Alice，你做完了吗？")
    
    "read_inbox":      lambda **kw: json.dumps(BUS.read_inbox("lead"), indent=2),
    # 工具：读取自己的邮件
    # 用途：查看秘书们给自己发的消息
    # 例子：read_inbox()
}

# these base tools are unchanged from s02
# 这些基础工具与 s02 相同

# ★ Lead 可用工具的完整列表
"""
★ 工具列表（给予Claude AI 的"能力清单"）

这个列表告诉 Claude AI：
"你是 Lead，你可以用这 9 个工具"

每个工具定义包括：
1. "name": 工具的名字
2. "description": 工具的功能描述
3. "input_schema": 工具需要的输入参数

★ 为什么需要这个列表？
════════════════════════════════════

Claude AI 接收这个列表，理解自己有哪些能力
当 Claude 想"做什么"时，会从这里选择一个工具

比如：
AI想："我需要创建一个文件"
→ 查看工具列表
→ 找到 "write_file" 工具
→ 按照 input_schema 的要求调用它

★ 9 个工具分组
════════════════════════════════════

【文件操作】(4 个)
- bash: 运行命令
- read_file: 读文件
- write_file: 写文件
- edit_file: 编辑文件

【团队管理】(3 个)
- spawn_teammate: 招聘秘书
- list_teammates: 列出秘书
- broadcast: 群发消息

【消息通信】(2 个)
- send_message: 一对一消息
- read_inbox: 读邮件
"""

TOOLS = [
    # 工具 1: bash - 执行 shell 命令
    {
        "name": "bash",
        "description": "Run a shell command.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"}
            },
            "required": ["command"]
        }
    },
    
    # 工具 2: read_file - 读取文件
    {
        "name": "read_file",
        "description": "Read file contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer"}
            },
            "required": ["path"]
        }
    },
    
    # 工具 3: write_file - 写入文件
    {
        "name": "write_file",
        "description": "Write content to file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    },
    
    # 工具 4: edit_file - 编辑文件
    {
        "name": "edit_file",
        "description": "Replace exact text in file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"}
            },
            "required": ["path", "old_text", "new_text"]
        }
    },
    
    # 工具 5: spawn_teammate - 招聘秘书
    {
        "name": "spawn_teammate",
        "description": "Spawn a persistent teammate that runs in its own thread.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "role": {"type": "string"},
                "prompt": {"type": "string"}
            },
            "required": ["name", "role", "prompt"]
        }
    },
    
    # 工具 6: list_teammates - 列出所有秘书
    {
        "name": "list_teammates",
        "description": "List all teammates with name, role, status.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    
    # 工具 7: send_message - 发送消息给某个秘书
    {
        "name": "send_message",
        "description": "Send a message to a teammate's inbox.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "content": {"type": "string"},
                "msg_type": {
                    "type": "string",
                    "enum": list(VALID_MSG_TYPES)
                }
            },
            "required": ["to", "content"]
        }
    },
    
    # 工具 8: read_inbox - 读取 Lead 的邮件
    {
        "name": "read_inbox",
        "description": "Read and drain the lead's inbox.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    
    # 工具 9: broadcast - 群发消息
    {
        "name": "broadcast",
        "description": "Send a message to all teammates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"}
            },
            "required": ["content"]
        }
    },
]


def agent_loop(messages: list):
    """
    ★ Lead（你）的"思维循环"
    
    这是 Lead 的主循环。Lead 会不停地：
    1. 查看邮件
    2. 问 Claude AI "我应该干什么？"
    3. 执行 Claude 建议的工具
    4. 循环回到第 1 步
    
    ★ 类比：Lead 的日常工作循环
    ════════════════════════════════════
    
    09:00 上班
         "今天要做什么？让我想想..."
    
    【第1轮】
    09:05 检查邮件
         Alice 给我发了："Task A 完成了！"
         Bob 给我发了："等等，我需要帮助！"
    
    09:06 问 Claude AI
         "我需要做什么？我有两条消息..."
         Claude: "你应该给 Bob 回复，告诉他解决方案"
    
    09:07 执行工具
         使用 send_message 给 Bob 回复
    
    【第2轮】
    09:10 检查邮件
         Carol 给我发了："我完成了代码审查"
    
    09:11 问 Claude AI
         "Carol 说完成了代码审查，现在怎么办？"
         Claude: "很好！现在招聘一个新秘书处理下一个任务"
    
    09:12 执行工具
         使用 spawn_teammate 招聘新秘书
    
    【第3轮】
    09:15 检查邮件（没有新消息）
         Claude AI: "没有新任务，让我休息一下"
         → 结束循环
    
    ★ 核心流程（5 步）
    ════════════════════════════════════
    
    【步骤1】检查邮件
    ─────────────────────
    inbox = BUS.read_inbox("lead")
    （从 lead.jsonl 文件读取所有秘书发来的消息）
    
    如果有邮件，添加到对话历史，作为新信息提醒 AI
    
    【步骤2】问 Claude AI
    ─────────────────────
    Claude AI 看着邮件和对话历史，思考：
    "主人，我建议你用这个工具..."
    
    比如：
    "我建议你用 send_message 工具回复 Alice"
    "我建议你用 spawn_teammate 招聘新秘书"
    "没什么要做的，工作完成"
    
    【步骤3】AI 决定用工具 or 结束
    ─────────────────────
    如果 AI 说"用工具"：
      → 继续到步骤 4
    如果 AI 说"任务完成"：
      → 退出循环
    
    【步骤4】执行工具
    ─────────────────────
    从 TOOL_HANDLERS 字典中查找工具处理函数
    执行函数，收集结果
    
    【步骤5】结果反馈给 AI
    ─────────────────────
    把工具执行结果添加到对话历史
    回到步骤 1
    
    ★ 例子流程图
    ════════════════════════════════════
    
                    ┌─ Lead 的邮件盒
                    │  (lead.jsonl)
                    ▼
            【步骤1】读取邮件
                    │
                    ▼
            ┌──────────────┐
            │ 对话历史      │
            │ (messages)   │
            │ 包含邮件内容  │
            └──────────────┘
                    │
                    ▼
            【步骤2】问 Claude AI
                    ↓
        ┌─ AI 决定：用工具 ─┬─ AI 决定：完成 ─┐
        │                  │                 │
        ▼                  ▼                 ▼
    【步骤3】             【步骤3】        返回
    执行工具             返回
        │
        ▼
    【步骤4】
    收集结果
        │
        ▼
    【步骤5】
    添加到对话
        │
        └──────→ 回到步骤 1
    
    ★ 退出条件
    ════════════════════════════════════
    
    当 response.stop_reason != "tool_use" 时退出
    
    意思是：
    - "tool_use"     → AI 要用工具，继续
    - "end_turn"     → AI 说完了，退出
    - "max_tokens"   → 文本太长了，退出
    - 其他           → 其他原因，退出
    """
    # ★ 无限循环，直到 AI 说"完成了"
    while True:
        # 【步骤1】检查 Lead 的邮件
        inbox = BUS.read_inbox("lead")
        
        # ★ 如果有新邮件，添加到对话历史
        if inbox:
            # 把邮件转为字符串，添加到对话
            messages.append({
                "role": "user",
                "content": f"<inbox>{json.dumps(inbox, indent=2)}</inbox>",
            })
            # ★ 告诉 AI"我已经看到这些邮件了"
            messages.append({
                "role": "assistant",
                "content": "Noted inbox messages.",
            })
        
        # 【步骤2】问 Claude AI "我应该干什么？"
        response = client.messages.create(
            model=MODEL,
            system=SYSTEM,
            messages=messages,
            tools=TOOLS,
            max_tokens=8000,
        )
        
        # ★ 把 AI 的回答添加到对话历史
        messages.append({"role": "assistant", "content": response.content})
        
        # 【步骤3】检查 AI 的决定
        if response.stop_reason != "tool_use":
            # ★ 如果 AI 不是说"用工具"，说明任务完成了
            return
        
        # 【步骤4】AI 决定用工具，执行工具
        results = []
        
        # ★ 遍历 AI 的所有回答块（可能有多个工具）
        for block in response.content:
            if block.type == "tool_use":
                # ★ 这是一个工具使用块
                handler = TOOL_HANDLERS.get(block.name)
                
                # 尝试执行工具
                try:
                    # ★ 调用对应的处理函数
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as e:
                    # ★ 如果出错，返回错误信息
                    output = f"Error: {e}"
                
                # ★ 打印执行结果（用于调试）
                print(f"> {block.name}: {str(output)[:200]}")
                
                # ★ 收集工具结果
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(output),
                })
        
        # 【步骤5】把结果添加到对话历史
        # 这样下一轮 Claude AI 就能看到工具的结果
        messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    """
    ★ REPL 程序（与你互动的界面）
    
    REPL = Read-Eval-Print-Loop
    意思是："读、执行、打印、循环"
    
    这就是你用来跟 Lead（秘书事务所）交互的界面！
    
    ★ 使用示例
    ════════════════════════════════════
    
    $ python s09_agent_teams.py
    s09 >> 帮我创建一个新秘书 Alice
    [AI 执行命令，创建 Alice]
    
    s09 >> /team
    [显示所有秘书列表]
    Team: default
      alice (coder): idle
      bob (reviewer): working
    
    s09 >> /inbox
    [显示 Lead 收到的消息]
    [
      {
        "type": "message",
        "from": "alice",
        "content": "Task completed!"
      }
    ]
    
    s09 >> q
    [退出程序]
    
    ★ 特殊命令
    ════════════════════════════════════
    
    普通输入：告诉 AI 你的需求，AI 会执行
    /team:    显示所有秘书的状态
    /inbox:   显示 Lead 的邮件
    q/exit:   退出程序
    
    ★ 工作流程
    ════════════════════════════════════
    
    【循环开始】
    1. 显示提示符 "s09 >> "
    2. 等待用户输入
    3. 解析输入（特殊命令 vs 普通查询）
    4. 如果是特殊命令，直接执行
    5. 如果是普通查询，交给 agent_loop 处理
    6. 打印结果
    7. 回到步骤 1
    
    ★ 代码详解
    ════════════════════════════════════
    """
    # ★ 初始化对话历史
    history = []
    
    # ★ 无限循环（REPL 的"循环"）
    while True:
        try:
            # ★ 等待用户输入（彩色提示符）
            query = input("\033[36ms09 >> \033[0m")
            # \033[36m = 青色，\033[0m = 重置颜色
        
        except (EOFError, KeyboardInterrupt):
            # ★ 如果用户按 Ctrl+D 或 Ctrl+C，退出
            break
        
        # ★ 检查是否是退出命令
        if query.strip().lower() in ("q", "exit", ""):
            # 空输入或 q/exit 都退出
            break
        
        # ★ 检查是否是查看团队命令
        if query.strip() == "/team":
            # /team 命令：显示团队成员列表
            print(TEAM.list_all())
            continue  # 跳过后面的代码，继续循环
        
        # ★ 检查是否是查看邮件命令
        if query.strip() == "/inbox":
            # /inbox 命令：显示 Lead 的收件箱
            print(json.dumps(BUS.read_inbox("lead"), indent=2))
            continue  # 跳过后面的代码，继续循环
        
        # ★ 普通查询：添加到对话历史
        history.append({"role": "user", "content": query})
        
        # ★ 调用 agent_loop 处理这个查询
        agent_loop(history)
        
        # ★ 从历史中获取最后的 AI 响应
        response_content = history[-1]["content"]
        
        # ★ 如果响应是列表（可能有多个块），逐个打印
        if isinstance(response_content, list):
            for block in response_content:
                if hasattr(block, "text"):
                    # 如果块有 text 属性，打印它
                    print(block.text)
        
        # ★ 打印空行（美观）
        print()
