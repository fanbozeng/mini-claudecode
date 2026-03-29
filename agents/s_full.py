#!/usr/bin/env python3
# Harness: all mechanisms combined -- the complete cockpit for the model.

"""
████████████████████████████████████████████████████████████████████████████

⚡ 【快速导航】如果你只想看某一部分：
==================================

🔹 只想理解基本概念？  
   → 读【一句话概括】到【类比：秘书事务所】部分（5分钟）

🔹 想了解整个系统架构？  
   → 读【整个系统的12个"齿轮"】部分（10分钟）

🔹 想看最关键函数？  
   → 跳到 agent_loop 部分（最重要的【心脏】）

🔹 想看所有工具定义？  
   → 搜索 TOOL_HANDLERS 字典

🔹 想快速检查一个概念？  
   → 使用 Ctrl+F 搜索："★★★" 或你感兴趣的关键词

████████████████████████████████████████████████████████████████████████████

【关键数字参考】
================

TOKEN_THRESHOLD = 100000   ← AI 脑子的容量（当超过时压缩）
POLL_INTERVAL = 5          ← 秘书多久检查一次新消息
IDLE_TIMEOUT = 60          ← 秘书多久没任务进入休眠
TOOLS 列表共 31 个工具     ← AI 可以用的"手"
齿轮共 12 个              ← 整个系统的模块数
函数和类共 50+ 个         ← 系统复杂度有多高

████████████████████████████████████████████████████████████████████████████

★★★ 🎯 博士生&小学生智力讲解：完整AI系统 🎯 ★★★

亲爱的各位诸位：

虽然你们可能发表过论文、读过专业论文...但今天我们要当一个"智力小学生"，
从**最最最基础**的角度理解这个复杂的AI系统。

████████████████████████████████████████████████████████████████████████████

【一句话概括这个程序】
===================

这是一个"超级AI秘书"的办公室管理系统。

想象你是一个富豪，雇了一个AI秘书。这个秘书能做很多事情：
  ✓ 执行命令（bash）
  ✓ 管理待办事项（todos）
  ✓ 雇别的秘书一起工作（subagent）
  ✓ 学习新技能（skills）
  ✓ 在后台工作而不让你等（background tasks）
  ✓ 和其他秘书聊天（messaging）
  ✓ 团队协作（team）
  ✓ 需要时找你批准计划（plan approval）

✨ 核心理念：让 AI 能像真人秘书一样聪明、高效、能协作。

████████████████████████████████████████████████████████████████████████████

【整个系统的12个"齿轮"】==  从简单到复杂  ==
===================================================

齿轮1️⃣：base_tools（基础工具）
  ├─ 工具就像"秘书的手"
  ├─ safe_path()   → 检查路径在工作目录内（防止秘书跑到别人家）
  ├─ run_bash()    → 运行命令  
  ├─ run_read()    → 读文件
  ├─ run_write()   → 写文件
  └─ run_edit()    → 编辑文件

齿轮2️⃣：TodoManager（待办清单）[s03]
  ├─ 秘书需要记住所有任务
  ├─ 可以创建、获取、更新、删除任务
  ├─ 格式：{"id": "任务ID", "title": "做什么", "status": "进行中/完成"}
  └─ 自动保存到 .tasks/ 文件夹

齿轮3️⃣：SubagentManager（雇用小秘书）[s04]
  ├─ 主秘书可以临时雇佣其他秘书来帮忙
  ├─ 分配任务 → 小秘书工作 → 汇报结果
  ├─ 比如："帮我分析这个项目，然后告诉我结论"
  └─ 小秘书完成后立即汇报，不用等

齿轮4️⃣：SkillLoader（学习技能）[s05]
  ├─ 秘书可以读取"技能书"（skills/目录下的.md文件）
  ├─ 学到新技能后，执行任务时更聪明
  ├─ 例如：学会"PDF处理技能"后，可以处理PDF文件
  └─ 通过系统提示注入到 AI 的脑子里

齿轮5️⃣：Compression（消息压缩）[s06]
  ├─ AI 的脑容量是有限的（token数量限制）
  ├─ 当对话太长时，需要"压缩"旧消息
  ├─ microcompact()    → 看看消息有多"重"
  ├─ auto_compact()    → 当太"重"时自动压缩
  └─ 原理：把旧的聊天内容总结成一句话

齿轮6️⃣：TaskManager（文件任务）[s07]
  ├─ 秘书需要在磁盘上保存任务信息
  ├─ 这样关机重启后，任务不会丢失
  ├─ 支持创建、查询、更新、完成任务
  └─ 任务互不干扰，相互独立

齿轮7️⃣：BackgroundManager（后台执行）[s08]
  ├─ 有些任务很耗时（比如运行10分钟的程序）
  ├─ 不能让主秘书傻傻等着
  ├─ 创建后台线程，主秘书继续处理其他东西
  ├─ 后台线程完成后，把结果放进"信箱"
  └─ 主秘书适时检查信箱，发现有新结果

齿轮8️⃣：MessageBus（消息系统）[s09]
  ├─ 多个秘书需要互相通信
  ├─ 秘书A想告诉秘书B某个信息
  ├─ 用"消息总线"传递，而不是直接说话
  ├─ 好处：秘书之间解耦，互不干扰
  └─ 消息存储在 .team/inbox/

齿轮9️⃣：TeammateManager（团队协作）[s09/s11]
  ├─ 管理所有雇佣的秘书（teammates）
  ├─ 每个秘书有自己的线程，在 .team/agents/teammate_X.json 里记录状态
  ├─ 秘书可以工作 → 空闲 → 接收任务 → 工作...
  ├─ 自动认领任务（s11 autonomous agent）
  └─ 主秘书可以给他们分配工作

齿轮🔟：ShutdownProtocol + PlanApproval [s10]
  ├─ 秘书需要"优雅关机"
  ├─ shutdown_request handshake: 秘书说"我要关闭"→你说"好"→秘书关闭
  ├─ 计划批准机制：秘书制定大计划 → 提交给你 → 你批准/拒绝
  ├─ 防止秘书做错误的事情
  └─ 计划存储在 .team/approvals/

齿轮1️⃣1️⃣：agent_loop（大脑循环）[完全整合]
  ├─ 这是整个系统的"心脏"
  ├─ 不停循环：检查 → 思考 → 执行 → 检查...
  ├─ 每次循环前，自动做5件事：
  │   1. 压缩过长的消息  （齿轮5）
  │   2. 检查后台任务完成没  （齿轮7）
  │   3. 检查新消息  （齿轮8）
  │   4. 检查任务更新  （齿轮6）
  │   5. 问"要不要继续？"  （如果启用todo nagging）
  ├─ 然后调用 AI（Claude）进行思考
  └─ AI 使用各种工具，再循环...

齿轮1️⃣2️⃣：WorktreeManager（工作树隔离）[s12]
  ├─ 解决并行任务冲突问题
  ├─ 每个任务分配独立目录（worktree）
  ├─ Git worktree 技术实现目录隔离
  ├─ 任务卡决定做什么，worktree决定在哪里做
  ├─ 支持 worktree_create, worktree_run, worktree_status 等工具
  └─ 事件日志记录所有操作（.worktrees/events.jsonl）

████████████████████████████████████████████████████████████████████████████

【这个系统如何连接】
====================

                     ┌─────────────────┐
                     │   User Input    │
                     │   (你的命令)     │
                     └────────┬────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │  agent_loop()   │ ◄─── 主循环（齿轮11）
                     │  (大脑循环)      │
                     └────────┬────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
    ┌───────┐          ┌───────────┐        ┌──────────┐
    │Compress│          │ CheckBG   │        │CheckInbox│
    │(齿轮5)  │          │ (齿轮7)   │        │(齿轮8)   │
    └───────┘          └───────────┘        └──────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   AI thinks      │ ◄─── Claude 的大脑
                    │  (使用工具)      │
                    └────────┬─────────┘
                             │
        ┌────────┬───────────┼───────────┬──────────┐
        │        │           │           │          │
        ▼        ▼           ▼           ▼          ▼
    ┌─────┐ ┌────────┐  ┌──────────┐┌──────┐ ┌──────────┐
    │bash │ │read    │ │write     ││edit  │ │TodoWrite │
    └─────┘ └────────┘  └──────────┘└──────┘ └──────────┘
        │        │           │           │          │
        └────────┴───────────┴───────────┴──────────┘
                              │
                              ▼
                        ┌──────────┐
                        │ Results  │
                        │ 放回AI    │
                        └──────────┘
                              │
                              ▼
               (AI 看到结果，继续思考或停止)

████████████████████████████████████████████████████████████████████████████

【类比：秘书事务所】
===================

想象一个秘书事务所:

  您 (User)
    │
    ▼
  主秘书 (Main Agent) ◄─────┐
    │                        │
    ├─ 有记忆本 (TodoManager)  │ 所有秘书都住在
    ├─ 有技能书 (SkillLoader)  │ 同一个办公室
    ├─ 有信息板 (MessageBus)   │ (.team/目录)
    ├─ 管理任务 (TaskManager)  │
    ├─ 管理后台 (BackgroundManager)
    │                        │
    ├─► 小秘书 #1 ─────────┐ │
    ├─► 小秘书 #2 ─────────┤ 自动协作
    └─► 小秘书 #3 ─────────┘ （s11）
                        ▲
                        │ 每个秘书都在
                        │ 自己的线程里工作
                        │ (不互相打扰)

████████████████████████████████████████████████████████████████████████████

【关键理解：这不是11个独立的程序】
===================================

这些不是11个独立的脚本，而是**11个功能层**，像意大利面条一样缠在一起：

  ✓ s01 基础循环 ✓ s02 工具系统 ✓ s03 待办管理
          ↓ (使用了)  ↓ (集成了)
  ✓ s04 子代理 ✓ s05 技能系统 ✓ s06 消息压缩
          ↓ (使用了)  ↓ (集成了)
  ✓ s07 任务系统 ✓ s08 后台执行 ✓ s09 消息总线
          ↓ (使用了)  ↓ (集成了)
  ✓ s10 关闭协议+计划批准 ✓ s11 自动认领
          ↓ (集成进)
  ✓✓✓ s_full.py （730行的怪兽系统）✓✓✓

████████████████████████████████████████████████████████████████████████████

现在让我们一行行读代码...
"""

# ========================== 导入部分（都是Python的标准库和外部库）==========================

import json        # 处理 JSON 格式数据（配置、消息等）
import os          # 操作系统接口（读环境变量、路径操作）
import re          # 正则表达式（搜索、匹配文本）
import subprocess  # 运行外部命令（比如shell命令）
import threading   # 多线程（多个秘书同时工作）
import time        # 时间操作（计时、延迟等）
import uuid        # 生成唯一ID（给每个任务、消息、秘书一个独特身份）
from pathlib import Path  # 路径操作（用对象而不是字符串）
from queue import Queue   # 队列（秘书之间安全地传递消息）
from typing import Optional  # 类型注解（可选类型）

from anthropic import Anthropic  # ★ AI 大脑的核心：Claude 模型
from dotenv import load_dotenv   # 加载 .env 文件的环境变量

# ========================== 初始化（设置秘书办公室的环境）==========================

load_dotenv(override=True)  # 从 .env 文件中加载 API密钥 等配置
if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)  # 防止两个认证方式冲突

# 秘书办公室的位置
WORKDIR = Path.cwd()  # 工作目录（整个办公室）
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))  # 连接到 Claude AI
MODEL = os.environ["MODEL_ID"]  # 使用哪个 Claude 模型（比如 claude-3-5-sonnet）

# 检测Git仓库根目录
def detect_repo_root(cwd: Path) -> Optional[Path]:
    """Return git repo root if cwd is inside a repo, else None."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return None
        root = Path(r.stdout.strip())
        return root if root.exists() else None
    except Exception:
        return None

REPO_ROOT = detect_repo_root(WORKDIR) or WORKDIR  # 检测仓库根目录，如果失败则使用当前工作目录

# ========================== 目录结构（秘书办公室的文件柜）==========================
#
# 办公室看起来长这样：
# 
# .team/                         ← 团队秘书的工作区
#   ├── inbox/                   ← 消息收件箱
#   ├── agents/                  ← 每个秘书的记录文件
#   └── approvals/               ← 需要批准的计划
# 
# .tasks/                        ← 任务数据库（持久化存储）
# skills/                        ← 秘书的技能库（.md文件）
# .transcripts/                  ← 对话记录存档
#

TEAM_DIR = WORKDIR / ".team"           # 团队办公室目录
INBOX_DIR = TEAM_DIR / "inbox"         # 消息盒子
TASKS_DIR = WORKDIR / ".tasks"         # 任务存储
SKILLS_DIR = WORKDIR / "skills"        # 技能库
TRANSCRIPT_DIR = WORKDIR / ".transcripts"  # 对话记录

# ========================== 全局参数（秘书办公室的规则）==========================

TOKEN_THRESHOLD = 100000   # AI 的脑子能容纳 100000 个 token（当超过时压缩消息）
POLL_INTERVAL = 5          # 每 5 秒检查一次新消息（秘书休息时间）
IDLE_TIMEOUT = 60          # 秘书 60 秒没有任务就进入"休眠"状态

# 允许的消息类型（秘书之间的谈话规范）
VALID_MSG_TYPES = {"message",              # 普通消息
                   "broadcast",             # 广播消息（发给所有人）
                   "shutdown_request",      # 关闭请求
                   "shutdown_response",     # 关闭响应
                   "plan_approval_response"}  # 计划批准响应


# ============== 齿轮1️⃣：基础工具 (base_tools) ========================
# 这些是秘书的"手"，能做的基础动作

# === SECTION: base_tools ===

def safe_path(p: str) -> Path:
    """
    ★ 安全路径检查 - 防止秘书"越狱"
    
    为什么需要？
    想象有个恶意的人，让秘书删除系统文件："rm -rf /"
    这个函数就像保安，检查："你要访问的路径，是否在我们的办公室里？"
    
    逻辑：
    1. 把相对路径变成绝对路径（如：./data.txt → /Users/xxx/data.txt）
    2. 检查这个路径是否在工作目录内
    3. 如果在，返回；如果不在，抛出错误
    """
    path = (WORKDIR / p).resolve()  # 转换为绝对路径
    if not path.is_relative_to(WORKDIR):  # 检查是否在工作目录内
        raise ValueError(f"Path escapes workspace: {p}")  # 不在就报错
    return path

def run_bash(command: str) -> str:
    """
    ★ 运行一个 bash 命令（同步/阻塞式）
    
    秘书说："老板，我要运行一个命令"
    秘书停下来等命令完成，然后告诉你结果
    
    工作流程：
    1. 检查命令是否包含危险指令
    2. 如果安全，运行命令
    3. 捕获输出（stdout 和 stderr）
    4. 返回结果给 AI
    """
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]  # 黑名单
    if any(d in command for d in dangerous):  # 检查命令是否危险
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, text=True, timeout=120)  # 最多等 120 秒
        out = (r.stdout + r.stderr).strip()  # 合并输出和错误信息
        return out[:50000] if out else "(no output)"  # 返回结果（截断到50000字符）
    except subprocess.TimeoutExpired:  # 如果超时
        return "Error: Timeout (120s)"

def run_read(path: str, limit: int = None) -> str:
    """
    ★ 读取文件内容
    
    秘书说："老板，我要读一个文件"
    秘书打开文件，读出内容，告诉你
    
    参数：
    - path: 文件路径
    - limit: 可选，最多读几行（如果文件太大，可以只看前几行）
    """
    try:
        lines = safe_path(path).read_text().splitlines()  # 读文件，按行分割
        if limit and limit < len(lines):
            # 如果设置了行数限制且文件超过限制
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]  # 只保留前 limit 行
        return "\n".join(lines)[:50000]  # 连接起来，截断到50000字符
    except Exception as e:
        return f"Error: {e}"

def run_write(path: str, content: str) -> str:
    """
    ★ 写入文件
    
    秘书说："老板，我要写一些内容到文件"
    秘书创建文件（如果不存在），写入内容
    """
    try:
        fp = safe_path(path)  # 检查路径安全
        fp.parent.mkdir(parents=True, exist_ok=True)  # 创建父目录（如果不存在）
        fp.write_text(content)  # 写入内容
        return f"Wrote {len(content)} bytes"
    except Exception as e:
        return f"Error: {e}"

def run_edit(path: str, old_text: str, new_text: str) -> str:
    """
    ★ 编辑文件（查找并替换）
    
    秘书说："老板，我要把文件里的 A 改成 B"
    秘书找到 A，替换成 B，保存文件
    """
    try:
        fp = safe_path(path)
        c = fp.read_text()  # 读整个文件
        if old_text not in c:  # 检查旧文本是否存在
            return f"Error: Text not found in {path}"
        fp.write_text(c.replace(old_text, new_text, 1))  # 替换（只替换第一个）
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"

def run_write(path: str, content: str) -> str:
    """
    ★ 写入文件
    
    秘书说："老板，我要写一些内容到文件"
    秘书创建文件（如果不存在），写入内容
    """
    try:
        fp = safe_path(path)  # 检查路径安全
        fp.parent.mkdir(parents=True, exist_ok=True)  # 创建父目录（如果不存在）
        fp.write_text(content)  # 写入内容
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"

def run_edit(path: str, old_text: str, new_text: str) -> str:
    """
    ★ 编辑文件（查找并替换）
    
    秘书说："老板，我要把文件里的 A 改成 B"
    秘书找到 A，替换成 B，保存文件
    """
    try:
        fp = safe_path(path)  # 检查路径安全
        c = fp.read_text()  # 读整个文件
        if old_text not in c:  # 检查旧文本是否存在
            return f"Error: Text not found in {path}"
        fp.write_text(c.replace(old_text, new_text, 1))  # 替换（只替换第一个）
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


# ============== 齿轮2️⃣：待办管理 (TodoManager) - s03 ========================
# 秘书的"记忆本"，记录所有要做的事情

# === SECTION: todos (s03) ===
class TodoManager:
    """
    ★ 待办事项管理器 - 秘书的任务清单
    
    就像你有一个手账本，记录要做的事情：
    - [ ] 买菜
    - [x] 洗碗
    - [ ] 写代码
    
    TodoManager 就是电子版的这个手账本
    """
    def __init__(self):
        # 初始化任务列表，起始为空
        self.items = []

    def update(self, items: list) -> str:
        """更新所有任务列表"""
        validated, ip = [], 0
        for i, item in enumerate(items):
            content = str(item.get("content", "")).strip()
            status = str(item.get("status", "pending")).lower()
            af = str(item.get("activeForm", "")).strip()
            if not content: raise ValueError(f"Item {i}: content required")
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Item {i}: invalid status '{status}'")
            if not af: raise ValueError(f"Item {i}: activeForm required")
            if status == "in_progress": ip += 1
            validated.append({"content": content, "status": status, "activeForm": af})
        if len(validated) > 20: raise ValueError("Max 20 todos")
        if ip > 1: raise ValueError("Only one in_progress allowed")
        self.items = validated
        return self.render()

    def render(self) -> str:
        if not self.items: return "No todos."
        lines = []
        for item in self.items:
            m = {"completed": "[x]", "in_progress": "[>]", "pending": "[ ]"}.get(item["status"], "[?]")
            suffix = f" <- {item['activeForm']}" if item["status"] == "in_progress" else ""
            lines.append(f"{m} {item['content']}{suffix}")
        done = sum(1 for t in self.items if t["status"] == "completed")
        lines.append(f"\n({done}/{len(self.items)} completed)")
        return "\n".join(lines)

    def has_open_items(self) -> bool:
        return any(item.get("status") != "completed" for item in self.items)


# === SECTION: subagent (s04) ===
def run_subagent(prompt: str, agent_type: str = "Explore") -> str:
    sub_tools = [
        {"name": "bash", "description": "Run command.",
         "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
        {"name": "read_file", "description": "Read file.",
         "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    ]
    if agent_type != "Explore":
        sub_tools += [
            {"name": "write_file", "description": "Write file.",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
            {"name": "edit_file", "description": "Edit file.",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
        ]
    sub_handlers = {
        "bash": lambda **kw: run_bash(kw["command"]),
        "read_file": lambda **kw: run_read(kw["path"]),
        "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
        "edit_file": lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    }
    sub_msgs = [{"role": "user", "content": prompt}]
    resp = None
    for _ in range(30):
        resp = client.messages.create(model=MODEL, messages=sub_msgs, tools=sub_tools, max_tokens=8000)
        sub_msgs.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            break
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                h = sub_handlers.get(b.name, lambda **kw: "Unknown tool")
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": str(h(**b.input))[:50000]})
        sub_msgs.append({"role": "user", "content": results})
    if resp:
        return "".join(b.text for b in resp.content if hasattr(b, "text")) or "(no summary)"
    return "(subagent failed)"


# === SECTION: skills (s05) ===
class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills = {}
        if skills_dir.exists():
            for f in sorted(skills_dir.rglob("SKILL.md")):
                text = f.read_text()
                match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
                meta, body = {}, text
                if match:
                    for line in match.group(1).strip().splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            meta[k.strip()] = v.strip()
                    body = match.group(2).strip()
                name = meta.get("name", f.parent.name)
                self.skills[name] = {"meta": meta, "body": body}

    def descriptions(self) -> str:
        if not self.skills: return "(no skills)"
        return "\n".join(f"  - {n}: {s['meta'].get('description', '-')}" for n, s in self.skills.items())

    def load(self, name: str) -> str:
        s = self.skills.get(name)
        if not s: return f"Error: Unknown skill '{name}'. Available: {', '.join(self.skills.keys())}"
        return f"<skill name=\"{name}\">\n{s['body']}\n</skill>"


# === SECTION: compression (s06) ===
def estimate_tokens(messages: list) -> int:
    return len(json.dumps(messages, default=str)) // 4

def microcompact(messages: list):
    indices = []
    for i, msg in enumerate(messages):
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            for part in msg["content"]:
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    indices.append(part)
    if len(indices) <= 3:
        return
    for part in indices[:-3]:
        if isinstance(part.get("content"), str) and len(part["content"]) > 100:
            part["content"] = "[cleared]"

def auto_compact(messages: list) -> list:
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
    with open(path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")
    conv_text = json.dumps(messages, default=str)[:80000]
    resp = client.messages.create(
        model=MODEL,
        messages=[{"role": "user", "content": f"Summarize for continuity:\n{conv_text}"}],
        max_tokens=2000,
    )
    summary = resp.content[0].text
    return [
        {"role": "user", "content": f"[Compressed. Transcript: {path}]\n{summary}"},
        {"role": "assistant", "content": "Understood. Continuing with summary context."},
    ]


# === SECTION: event_bus (s12) ===
class EventBus:
    def __init__(self, event_log_path: Path):
        self.path = event_log_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("")

    def emit(self, event: str, task: Optional[dict] = None, worktree: Optional[dict] = None, error: Optional[str] = None):
        payload = {"event": event, "ts": time.time(), "task": task or {}, "worktree": worktree or {}}
        if error:
            payload["error"] = error
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")

    def list_recent(self, limit: int = 20) -> str:
        n = max(1, min(int(limit or 20), 200))
        lines = self.path.read_text(encoding="utf-8").splitlines()
        recent = lines[-n:]
        items = []
        for line in recent:
            try:
                items.append(json.loads(line))
            except Exception:
                items.append({"event": "parse_error", "raw": line})
        return json.dumps(items, indent=2)


# === SECTION: file_tasks (s07) ===
class TaskManager:
    def __init__(self):
        TASKS_DIR.mkdir(exist_ok=True)

    def _next_id(self) -> int:
        ids = [int(f.stem.split("_")[1]) for f in TASKS_DIR.glob("task_*.json")]
        return max(ids, default=0) + 1

    def _load(self, tid: int) -> dict:
        p = TASKS_DIR / f"task_{tid}.json"
        if not p.exists(): raise ValueError(f"Task {tid} not found")
        return json.loads(p.read_text())

    def _save(self, task: dict):
        (TASKS_DIR / f"task_{task['id']}.json").write_text(json.dumps(task, indent=2))

    def create(self, subject: str, description: str = "") -> str:
        task = {"id": self._next_id(), "subject": subject, "description": description,
                "status": "pending", "owner": None, "blockedBy": [], "blocks": []}
        self._save(task)
        return json.dumps(task, indent=2)

    def get(self, tid: int) -> str:
        return json.dumps(self._load(tid), indent=2)

    def update(self, tid: int, status: str = None,
               add_blocked_by: list = None, add_blocks: list = None) -> str:
        task = self._load(tid)
        if status:
            task["status"] = status
            if status == "completed":
                for f in TASKS_DIR.glob("task_*.json"):
                    t = json.loads(f.read_text())
                    if tid in t.get("blockedBy", []):
                        t["blockedBy"].remove(tid)
                        self._save(t)
            if status == "deleted":
                (TASKS_DIR / f"task_{tid}.json").unlink(missing_ok=True)
                return f"Task {tid} deleted"
        if add_blocked_by:
            task["blockedBy"] = list(set(task["blockedBy"] + add_blocked_by))
        if add_blocks:
            task["blocks"] = list(set(task["blocks"] + add_blocks))
        self._save(task)
        return json.dumps(task, indent=2)

    def list_all(self) -> str:
        tasks = [json.loads(f.read_text()) for f in sorted(TASKS_DIR.glob("task_*.json"))]
        if not tasks: return "No tasks."
        lines = []
        for t in tasks:
            m = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}.get(t["status"], "[?]")
            owner = f" @{t['owner']}" if t.get("owner") else ""
            blocked = f" (blocked by: {t['blockedBy']})" if t.get("blockedBy") else ""
            lines.append(f"{m} #{t['id']}: {t['subject']}{owner}{blocked}")
        return "\n".join(lines)

    def claim(self, tid: int, owner: str) -> str:
        task = self._load(tid)
        task["owner"] = owner
        task["status"] = "in_progress"
        self._save(task)
        return f"Claimed task #{tid} for {owner}"

    def bind_worktree(self, task_id: int, worktree: str, owner: str = "") -> str:
        task = self._load(task_id)
        task["worktree"] = worktree
        if owner:
            task["owner"] = owner
        if task["status"] == "pending":
            task["status"] = "in_progress"
        task["updated_at"] = time.time()
        self._save(task)
        return json.dumps(task, indent=2)

    def unbind_worktree(self, task_id: int) -> str:
        task = self._load(task_id)
        task["worktree"] = ""
        task["updated_at"] = time.time()
        self._save(task)
        return json.dumps(task, indent=2)


# === SECTION: background (s08) ===
class BackgroundManager:
    def __init__(self):
        self.tasks = {}
        self.notifications = Queue()

    def run(self, command: str, timeout: int = 120) -> str:
        tid = str(uuid.uuid4())[:8]
        self.tasks[tid] = {"status": "running", "command": command, "result": None}
        threading.Thread(target=self._exec, args=(tid, command, timeout), daemon=True).start()
        return f"Background task {tid} started: {command[:80]}"

    def _exec(self, tid: str, command: str, timeout: int):
        try:
            r = subprocess.run(command, shell=True, cwd=WORKDIR,
                               capture_output=True, text=True, timeout=timeout)
            output = (r.stdout + r.stderr).strip()[:50000]
            self.tasks[tid].update({"status": "completed", "result": output or "(no output)"})
        except Exception as e:
            self.tasks[tid].update({"status": "error", "result": str(e)})
        self.notifications.put({"task_id": tid, "status": self.tasks[tid]["status"],
                                "result": self.tasks[tid]["result"][:500]})

    def check(self, tid: str = None) -> str:
        if tid:
            t = self.tasks.get(tid)
            return f"[{t['status']}] {t.get('result', '(running)')}" if t else f"Unknown: {tid}"
        return "\n".join(f"{k}: [{v['status']}] {v['command'][:60]}" for k, v in self.tasks.items()) or "No bg tasks."

    def drain(self) -> list:
        notifs = []
        while not self.notifications.empty():
            notifs.append(self.notifications.get_nowait())
        return notifs


# === SECTION: messaging (s09) ===
class MessageBus:
    def __init__(self):
        INBOX_DIR.mkdir(parents=True, exist_ok=True)

    def send(self, sender: str, to: str, content: str,
             msg_type: str = "message", extra: dict = None) -> str:
        msg = {"type": msg_type, "from": sender, "content": content,
               "timestamp": time.time()}
        if extra: msg.update(extra)
        with open(INBOX_DIR / f"{to}.jsonl", "a") as f:
            f.write(json.dumps(msg) + "\n")
        return f"Sent {msg_type} to {to}"

    def read_inbox(self, name: str) -> list:
        path = INBOX_DIR / f"{name}.jsonl"
        if not path.exists(): return []
        msgs = [json.loads(l) for l in path.read_text().strip().splitlines() if l]
        path.write_text("")
        return msgs

    def broadcast(self, sender: str, content: str, names: list) -> str:
        count = 0
        for n in names:
            if n != sender:
                self.send(sender, n, content, "broadcast")
                count += 1
        return f"Broadcast to {count} teammates"


# === SECTION: shutdown + plan tracking (s10) ===
shutdown_requests = {}
plan_requests = {}


# === SECTION: worktree (s12) ===
class WorktreeManager:
    def __init__(self, repo_root: Path, tasks: TaskManager, events: EventBus):
        self.repo_root = repo_root
        self.tasks = tasks
        self.events = events
        self.dir = repo_root / ".worktrees"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.dir / "index.json"
        if not self.index_path.exists():
            self.index_path.write_text(json.dumps({"worktrees": []}, indent=2))
        self.git_available = self._is_git_repo()

    def _is_git_repo(self) -> bool:
        try:
            r = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=self.repo_root, capture_output=True, text=True, timeout=10)
            return r.returncode == 0
        except Exception:
            return False

    def _run_git(self, args: list[str]) -> str:
        if not self.git_available:
            raise RuntimeError("Not in a git repository. worktree tools require git.")
        r = subprocess.run(["git", *args], cwd=self.repo_root, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            msg = (r.stdout + r.stderr).strip()
            raise RuntimeError(msg or f"git {' '.join(args)} failed")
        return (r.stdout + r.stderr).strip() or "(no output)"

    def _load_index(self) -> dict:
        return json.loads(self.index_path.read_text())

    def _save_index(self, data: dict):
        self.index_path.write_text(json.dumps(data, indent=2))

    def _find(self, name: str) -> Optional[dict]:
        idx = self._load_index()
        for wt in idx.get("worktrees", []):
            if wt.get("name") == name:
                return wt
        return None

    def _validate_name(self, name: str):
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", name or ""):
            raise ValueError("Invalid worktree name. Use 1-40 chars: letters, numbers, ., _, -")

    def create(self, name: str, task_id: int = None, base_ref: str = "HEAD") -> str:
        self._validate_name(name)
        if self._find(name):
            raise ValueError(f"Worktree '{name}' already exists in index")
        if task_id is not None:
            try:
                self.tasks._load(task_id)
            except:
                raise ValueError(f"Task {task_id} not found")

        path = self.dir / name
        branch = f"wt/{name}"
        self.events.emit("worktree.create.before", task={"id": task_id} if task_id is not None else {}, worktree={"name": name, "base_ref": base_ref})
        try:
            self._run_git(["worktree", "add", "-b", branch, str(path), base_ref])

            entry = {"name": name, "path": str(path), "branch": branch, "task_id": task_id, "status": "active", "created_at": time.time()}
            idx = self._load_index()
            idx["worktrees"].append(entry)
            self._save_index(idx)

            if task_id is not None:
                self.tasks.bind_worktree(task_id, name)

            self.events.emit("worktree.create.after", task={"id": task_id} if task_id is not None else {}, worktree={"name": name, "path": str(path), "branch": branch, "status": "active"})
            return json.dumps(entry, indent=2)
        except Exception as e:
            self.events.emit("worktree.create.failed", task={"id": task_id} if task_id is not None else {}, worktree={"name": name, "base_ref": base_ref}, error=str(e))
            raise

    def list_all(self) -> str:
        idx = self._load_index()
        wts = idx.get("worktrees", [])
        if not wts:
            return "No worktrees in index."
        lines = []
        for wt in wts:
            suffix = f" task={wt['task_id']}" if wt.get("task_id") else ""
            lines.append(f"[{wt.get('status', 'unknown')}] {wt['name']} -> {wt['path']} ({wt.get('branch', '-')}){suffix}")
        return "\n".join(lines)

    def status(self, name: str) -> str:
        wt = self._find(name)
        if not wt:
            return f"Error: Unknown worktree '{name}'"
        path = Path(wt["path"])
        if not path.exists():
            return f"Error: Worktree path missing: {path}"
        r = subprocess.run(["git", "status", "--short", "--branch"], cwd=path, capture_output=True, text=True, timeout=60)
        text = (r.stdout + r.stderr).strip()
        return text or "Clean worktree"

    def run(self, name: str, command: str) -> str:
        dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
        if any(d in command for d in dangerous):
            return "Error: Dangerous command blocked"

        wt = self._find(name)
        if not wt:
            return f"Error: Unknown worktree '{name}'"
        path = Path(wt["path"])
        if not path.exists():
            return f"Error: Worktree path missing: {path}"

        try:
            r = subprocess.run(command, shell=True, cwd=path, capture_output=True, text=True, timeout=300)
            out = (r.stdout + r.stderr).strip()
            return out[:50000] if out else "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: Timeout (300s)"

    def remove(self, name: str, force: bool = False, complete_task: bool = False) -> str:
        wt = self._find(name)
        if not wt:
            return f"Error: Unknown worktree '{name}'"

        self.events.emit("worktree.remove.before", task={"id": wt.get("task_id")} if wt.get("task_id") is not None else {}, worktree={"name": name, "path": wt.get("path")})
        try:
            args = ["worktree", "remove"]
            if force:
                args.append("--force")
            args.append(wt["path"])
            self._run_git(args)

            if complete_task and wt.get("task_id") is not None:
                task_id = wt["task_id"]
                before = json.loads(self.tasks.get(task_id))
                self.tasks.update(task_id, status="completed")
                self.tasks.unbind_worktree(task_id)
                self.events.emit("task.completed", task={"id": task_id, "subject": before.get("subject", ""), "status": "completed"}, worktree={"name": name})

            idx = self._load_index()
            for item in idx.get("worktrees", []):
                if item.get("name") == name:
                    item["status"] = "removed"
                    item["removed_at"] = time.time()
            self._save_index(idx)

            self.events.emit("worktree.remove.after", task={"id": wt.get("task_id")} if wt.get("task_id") is not None else {}, worktree={"name": name, "path": wt.get("path"), "status": "removed"})
            return f"Removed worktree '{name}'"
        except Exception as e:
            self.events.emit("worktree.remove.failed", task={"id": wt.get("task_id")} if wt.get("task_id") is not None else {}, worktree={"name": name, "path": wt.get("path")}, error=str(e))
            raise

    def keep(self, name: str) -> str:
        wt = self._find(name)
        if not wt:
            return f"Error: Unknown worktree '{name}'"

        idx = self._load_index()
        kept = None
        for item in idx.get("worktrees", []):
            if item.get("name") == name:
                item["status"] = "kept"
                item["kept_at"] = time.time()
                kept = item
        self._save_index(idx)

        self.events.emit("worktree.keep", task={"id": wt.get("task_id")} if wt.get("task_id") is not None else {}, worktree={"name": name, "path": wt.get("path"), "status": "kept"})
        return json.dumps(kept, indent=2) if kept else f"Error: Unknown worktree '{name}'"


# === SECTION: team (s09/s11) ===
class TeammateManager:
    def __init__(self, bus: MessageBus, task_mgr: TaskManager):
        TEAM_DIR.mkdir(exist_ok=True)
        self.bus = bus
        self.task_mgr = task_mgr
        self.config_path = TEAM_DIR / "config.json"
        self.config = self._load()
        self.threads = {}

    def _load(self) -> dict:
        if self.config_path.exists():
            return json.loads(self.config_path.read_text())
        return {"team_name": "default", "members": []}

    def _save(self):
        self.config_path.write_text(json.dumps(self.config, indent=2))

    def _find(self, name: str) -> dict:
        for m in self.config["members"]:
            if m["name"] == name: return m
        return None

    def spawn(self, name: str, role: str, prompt: str) -> str:
        member = self._find(name)
        if member:
            if member["status"] not in ("idle", "shutdown"):
                return f"Error: '{name}' is currently {member['status']}"
            member["status"] = "working"
            member["role"] = role
        else:
            member = {"name": name, "role": role, "status": "working"}
            self.config["members"].append(member)
        self._save()
        threading.Thread(target=self._loop, args=(name, role, prompt), daemon=True).start()
        return f"Spawned '{name}' (role: {role})"

    def _set_status(self, name: str, status: str):
        member = self._find(name)
        if member:
            member["status"] = status
            self._save()

    def _loop(self, name: str, role: str, prompt: str):
        team_name = self.config["team_name"]
        sys_prompt = (f"You are '{name}', role: {role}, team: {team_name}, at {WORKDIR}. "
                      f"Use idle when done with current work. You may auto-claim tasks.")
        messages = [{"role": "user", "content": prompt}]
        tools = [
            {"name": "bash", "description": "Run command.", "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
            {"name": "read_file", "description": "Read file.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
            {"name": "write_file", "description": "Write file.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
            {"name": "edit_file", "description": "Edit file.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
            {"name": "send_message", "description": "Send message.", "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "content": {"type": "string"}}, "required": ["to", "content"]}},
            {"name": "idle", "description": "Signal no more work.", "input_schema": {"type": "object", "properties": {}}},
            {"name": "claim_task", "description": "Claim task by ID.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]}},
        ]
        while True:
            # -- WORK PHASE --
            for _ in range(50):
                inbox = self.bus.read_inbox(name)
                for msg in inbox:
                    if msg.get("type") == "shutdown_request":
                        self._set_status(name, "shutdown")
                        return
                    messages.append({"role": "user", "content": json.dumps(msg)})
                try:
                    response = client.messages.create(
                        model=MODEL, system=sys_prompt, messages=messages,
                        tools=tools, max_tokens=8000)
                except Exception:
                    self._set_status(name, "shutdown")
                    return
                messages.append({"role": "assistant", "content": response.content})
                if response.stop_reason != "tool_use":
                    break
                results = []
                idle_requested = False
                for block in response.content:
                    if block.type == "tool_use":
                        if block.name == "idle":
                            idle_requested = True
                            output = "Entering idle phase."
                        elif block.name == "claim_task":
                            output = self.task_mgr.claim(block.input["task_id"], name)
                        elif block.name == "send_message":
                            output = self.bus.send(name, block.input["to"], block.input["content"])
                        else:
                            dispatch = {"bash": lambda **kw: run_bash(kw["command"]),
                                        "read_file": lambda **kw: run_read(kw["path"]),
                                        "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
                                        "edit_file": lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"])}
                            output = dispatch.get(block.name, lambda **kw: "Unknown")(**block.input)
                        print(f"  [{name}] {block.name}: {str(output)[:120]}")
                        results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)})
                messages.append({"role": "user", "content": results})
                if idle_requested:
                    break
            # -- IDLE PHASE: poll for messages and unclaimed tasks --
            self._set_status(name, "idle")
            resume = False
            for _ in range(IDLE_TIMEOUT // max(POLL_INTERVAL, 1)):
                time.sleep(POLL_INTERVAL)
                inbox = self.bus.read_inbox(name)
                if inbox:
                    for msg in inbox:
                        if msg.get("type") == "shutdown_request":
                            self._set_status(name, "shutdown")
                            return
                        messages.append({"role": "user", "content": json.dumps(msg)})
                    resume = True
                    break
                unclaimed = []
                for f in sorted(TASKS_DIR.glob("task_*.json")):
                    t = json.loads(f.read_text())
                    if t.get("status") == "pending" and not t.get("owner") and not t.get("blockedBy"):
                        unclaimed.append(t)
                if unclaimed:
                    task = unclaimed[0]
                    self.task_mgr.claim(task["id"], name)
                    # Identity re-injection for compressed contexts
                    if len(messages) <= 3:
                        messages.insert(0, {"role": "user", "content":
                            f"<identity>You are '{name}', role: {role}, team: {team_name}.</identity>"})
                        messages.insert(1, {"role": "assistant", "content": f"I am {name}. Continuing."})
                    messages.append({"role": "user", "content":
                        f"<auto-claimed>Task #{task['id']}: {task['subject']}\n{task.get('description', '')}</auto-claimed>"})
                    messages.append({"role": "assistant", "content": f"Claimed task #{task['id']}. Working on it."})
                    resume = True
                    break
            if not resume:
                self._set_status(name, "shutdown")
                return
            self._set_status(name, "working")

    def list_all(self) -> str:
        if not self.config["members"]: return "No teammates."
        lines = [f"Team: {self.config['team_name']}"]
        for m in self.config["members"]:
            lines.append(f"  {m['name']} ({m['role']}): {m['status']}")
        return "\n".join(lines)

    def member_names(self) -> list:
        return [m["name"] for m in self.config["members"]]


# === SECTION: global_instances ===
TODO = TodoManager()
SKILLS = SkillLoader(SKILLS_DIR)
TASK_MGR = TaskManager()
BG = BackgroundManager()
BUS = MessageBus()
TEAM = TeammateManager(BUS, TASK_MGR)
EVENTS = EventBus(REPO_ROOT / ".worktrees" / "events.jsonl")
WORKTREES = WorktreeManager(REPO_ROOT, TASK_MGR, EVENTS)

# === SECTION: system_prompt ===
SYSTEM = f"""You are a coding agent at {WORKDIR}. Use tools to solve tasks.
Prefer task_create/task_update/task_list for multi-step work. Use TodoWrite for short checklists.
Use task for subagent delegation. Use load_skill for specialized knowledge.
Use task + worktree tools for multi-task work. For parallel or risky changes: create tasks, allocate worktree lanes, run commands in those lanes, then choose keep/remove for closeout.
Skills: {SKILLS.descriptions()}"""


# === SECTION: shutdown_protocol (s10) ===
def handle_shutdown_request(teammate: str) -> str:
    req_id = str(uuid.uuid4())[:8]
    shutdown_requests[req_id] = {"target": teammate, "status": "pending"}
    BUS.send("lead", teammate, "Please shut down.", "shutdown_request", {"request_id": req_id})
    return f"Shutdown request {req_id} sent to '{teammate}'"

# === SECTION: plan_approval (s10) ===
def handle_plan_review(request_id: str, approve: bool, feedback: str = "") -> str:
    req = plan_requests.get(request_id)
    if not req: return f"Error: Unknown plan request_id '{request_id}'"
    req["status"] = "approved" if approve else "rejected"
    BUS.send("lead", req["from"], feedback, "plan_approval_response",
             {"request_id": request_id, "approve": approve, "feedback": feedback})
    return f"Plan {req['status']} for '{req['from']}'"


# === SECTION: tool_dispatch (s02) ===
TOOL_HANDLERS = {
    "bash":             lambda **kw: run_bash(kw["command"]),
    "read_file":        lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file":       lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":        lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    "TodoWrite":        lambda **kw: TODO.update(kw["items"]),
    "task":             lambda **kw: run_subagent(kw["prompt"], kw.get("agent_type", "Explore")),
    "load_skill":       lambda **kw: SKILLS.load(kw["name"]),
    "compress":         lambda **kw: "Compressing...",
    "background_run":   lambda **kw: BG.run(kw["command"], kw.get("timeout", 120)),
    "check_background": lambda **kw: BG.check(kw.get("task_id")),
    "task_create":      lambda **kw: TASK_MGR.create(kw["subject"], kw.get("description", "")),
    "task_get":         lambda **kw: TASK_MGR.get(kw["task_id"]),
    "task_update":      lambda **kw: TASK_MGR.update(kw["task_id"], kw.get("status"), kw.get("add_blocked_by"), kw.get("add_blocks")),
    "task_list":        lambda **kw: TASK_MGR.list_all(),
    "spawn_teammate":   lambda **kw: TEAM.spawn(kw["name"], kw["role"], kw["prompt"]),
    "list_teammates":   lambda **kw: TEAM.list_all(),
    "send_message":     lambda **kw: BUS.send("lead", kw["to"], kw["content"], kw.get("msg_type", "message")),
    "read_inbox":       lambda **kw: json.dumps(BUS.read_inbox("lead"), indent=2),
    "broadcast":        lambda **kw: BUS.broadcast("lead", kw["content"], TEAM.member_names()),
    "shutdown_request": lambda **kw: handle_shutdown_request(kw["teammate"]),
    "plan_approval":    lambda **kw: handle_plan_review(kw["request_id"], kw["approve"], kw.get("feedback", "")),
    "idle":             lambda **kw: "Lead does not idle.",
    "claim_task":       lambda **kw: TASK_MGR.claim(kw["task_id"], "lead"),
    "task_bind_worktree": lambda **kw: TASK_MGR.bind_worktree(kw["task_id"], kw["worktree"], kw.get("owner", "")),
    "worktree_create":  lambda **kw: WORKTREES.create(kw["name"], kw.get("task_id"), kw.get("base_ref", "HEAD")),
    "worktree_list":    lambda **kw: WORKTREES.list_all(),
    "worktree_status":  lambda **kw: WORKTREES.status(kw["name"]),
    "worktree_run":     lambda **kw: WORKTREES.run(kw["name"], kw["command"]),
    "worktree_keep":    lambda **kw: WORKTREES.keep(kw["name"]),
    "worktree_remove":  lambda **kw: WORKTREES.remove(kw["name"], kw.get("force", False), kw.get("complete_task", False)),
    "worktree_events":  lambda **kw: EVENTS.list_recent(kw.get("limit", 20)),
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
    {"name": "TodoWrite", "description": "Update task tracking list.",
     "input_schema": {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {"content": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}, "activeForm": {"type": "string"}}, "required": ["content", "status", "activeForm"]}}}, "required": ["items"]}},
    {"name": "task", "description": "Spawn a subagent for isolated exploration or work.",
     "input_schema": {"type": "object", "properties": {"prompt": {"type": "string"}, "agent_type": {"type": "string", "enum": ["Explore", "general-purpose"]}}, "required": ["prompt"]}},
    {"name": "load_skill", "description": "Load specialized knowledge by name.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "compress", "description": "Manually compress conversation context.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "background_run", "description": "Run command in background thread.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["command"]}},
    {"name": "check_background", "description": "Check background task status.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}}}},
    {"name": "task_create", "description": "Create a persistent file task.",
     "input_schema": {"type": "object", "properties": {"subject": {"type": "string"}, "description": {"type": "string"}}, "required": ["subject"]}},
    {"name": "task_get", "description": "Get task details by ID.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]}},
    {"name": "task_update", "description": "Update task status or dependencies.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "deleted"]}, "add_blocked_by": {"type": "array", "items": {"type": "integer"}}, "add_blocks": {"type": "array", "items": {"type": "integer"}}}, "required": ["task_id"]}},
    {"name": "task_list", "description": "List all tasks.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "spawn_teammate", "description": "Spawn a persistent autonomous teammate.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "role": {"type": "string"}, "prompt": {"type": "string"}}, "required": ["name", "role", "prompt"]}},
    {"name": "list_teammates", "description": "List all teammates.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "send_message", "description": "Send a message to a teammate.",
     "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "content": {"type": "string"}, "msg_type": {"type": "string", "enum": list(VALID_MSG_TYPES)}}, "required": ["to", "content"]}},
    {"name": "read_inbox", "description": "Read and drain the lead's inbox.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "broadcast", "description": "Send message to all teammates.",
     "input_schema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},
    {"name": "shutdown_request", "description": "Request a teammate to shut down.",
     "input_schema": {"type": "object", "properties": {"teammate": {"type": "string"}}, "required": ["teammate"]}},
    {"name": "plan_approval", "description": "Approve or reject a teammate's plan.",
     "input_schema": {"type": "object", "properties": {"request_id": {"type": "string"}, "approve": {"type": "boolean"}, "feedback": {"type": "string"}}, "required": ["request_id", "approve"]}},
    {"name": "idle", "description": "Enter idle state.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "claim_task", "description": "Claim a task from the board.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]}},
    {"name": "task_bind_worktree", "description": "Bind a task to a worktree name.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}, "worktree": {"type": "string"}, "owner": {"type": "string"}}, "required": ["task_id", "worktree"]}},
    {"name": "worktree_create", "description": "Create a git worktree and optionally bind it to a task.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "task_id": {"type": "integer"}, "base_ref": {"type": "string"}}, "required": ["name"]}},
    {"name": "worktree_list", "description": "List worktrees tracked in .worktrees/index.json.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "worktree_status", "description": "Show git status for one worktree.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "worktree_run", "description": "Run a shell command in a named worktree directory.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "command": {"type": "string"}}, "required": ["name", "command"]}},
    {"name": "worktree_keep", "description": "Mark a worktree as kept in lifecycle state without removing it.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "worktree_remove", "description": "Remove a worktree and optionally mark its bound task completed.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "force": {"type": "boolean"}, "complete_task": {"type": "boolean"}}, "required": ["name"]}},
    {"name": "worktree_events", "description": "List recent worktree/task lifecycle events from .worktrees/events.jsonl.",
     "input_schema": {"type": "object", "properties": {"limit": {"type": "integer"}}}},
]


# ============ 🫀 最终大脑：整合所有11个齿轮 ============
# === SECTION: agent_loop ===

def agent_loop(messages: list):
    """
    ★★★ 这是整个系统的【心脏】 ★★★
    
    这个函数在**无限循环**中做同一件事：
    1. 清理消息（压缩）
    2. 检查后台任务完成没
    3. 检查有没有新消息
    4. 让 AI 思考并做决定
    5. AI 使用一些工具
    6. 重复...
    
    类比：一个人在工作
    ┌─────────────────────────────────────────┐
    │ 1. 整理桌子（可能有太多纸张了）        │
    │ 2. 检查邮箱（有没有新邮件）            │
    │ 3. 检查留言板（有没有新消息）          │
    │ 4. 看看当前的任务，思考下一步          │
    │ 5. 执行任务（用手做点什么）            │
    │ 6. 回到第一步（永远不停）              │
    └─────────────────────────────────────────┘
    
    在 LLM 开发中，这个循环被称为："agentic loop" 或 "thinking loop"
    """
    rounds_without_todo = 0  # 计数器：多少轮没有使用待办功能了
    
    while True:
        # 无限循环，直到 AI 说"我完成了"
        
        # ============ 步骤1️⃣：消息压缩（齿轮5️⃣）============
        # AI 的脑子有容量限制（100000 tokens）
        # 当对话太长时，需要压缩旧消息
        microcompact(messages)  # 快速检查消息的大小
        
        if estimate_tokens(messages) > TOKEN_THRESHOLD:  # 如果超过限制
            print("[auto-compact triggered]")  # 触发自动压缩
            messages[:] = auto_compact(messages)  # 把旧消息进行总结压缩
        
        # ============ 步骤2️⃣：检查后台任务（齿轮7️⃣）============
        # 如果有后台线程完成了工作，检查结果
        notifs = BG.drain()  # 从"信箱"里取出所有完成的任务通知
        
        if notifs:  # 如果有任务完成了
            # 把所有完成的结果格式化成文本
            txt = "\n".join(f"[bg:{n['task_id']}] {n['status']}: {n['result']}" 
                           for n in notifs)
            # 把结果注入到消息历史中，让 AI 看到
            messages.append({"role": "user", 
                           "content": f"<background-results>\n{txt}\n</background-results>"})
            # AI"确认"收到了这些消息
            messages.append({"role": "assistant", "content": "Noted background results."})
        
        # ============ 步骤3️⃣：检查新消息（齿轮8️⃣）============
        # 如果有其他秘书给主秘书留了消息，检查收件箱
        inbox = BUS.read_inbox("lead")  # 读取"lead"收件箱中的所有消息
        
        if inbox:  # 如果有新消息
            # 把消息注入到 AI 的视野
            messages.append({"role": "user", 
                           "content": f"<inbox>{json.dumps(inbox, indent=2)}</inbox>"})
            # AI"确认"收到了消息
            messages.append({"role": "assistant", "content": "Noted inbox messages."})
        
        # ============ 步骤4️⃣：AI 做决定（齿轮11️⃣的核心）============
        # 现在让 Claude AI 看一下消息历史，思考下一步
        response = client.messages.create(
            model=MODEL,              # 使用 Claude 模型
            system=SYSTEM,            # 告诉 AI 它的角色
            messages=messages,        # 整个对话历史
            tools=TOOLS,              # AI 可以使用哪些工具
            max_tokens=8000,          # 最多生成 8000 个 token
        )
        
        # 把 AI 的回应添加到消息历史（这样下一轮 AI 能看到自己之前做了什么）
        messages.append({"role": "assistant", "content": response.content})
        
        # 检查 AI 为什么停止了回复
        # "tool_use" = AI 想使用工具
        # "end_turn" 或其他 = AI 完成了对话
        if response.stop_reason != "tool_use":
            # 如果 AI 不是想要使用工具，说明任务完成，可以退出循环
            return
        
        # ============ 步骤5️⃣：执行 AI 请求的工具（齿轮2️⃣）============
        # AI 说："我要用 bash 工具运行一个命令"
        # 我们现在来执行这个请求
        
        results = []  # 存储所有工具的执行结果
        used_todo = False  # 追踪是否使用了待办功能
        manual_compress = False  # 追踪是否手动压缩了消息
        
        for block in response.content:
            # response.content 包含多个"块"（可能有文本、工具调用等）
            
            if block.type == "tool_use":  # 这是一个工具调用请求
                
                if block.name == "compress":  # 标记手动压缩
                    manual_compress = True
                
                # 从工具处理器字典中找到对应的函数
                handler = TOOL_HANDLERS.get(block.name)
                
                try:
                    # 执行工具（block.input 包含工具的参数）
                    output = (handler(**block.input) 
                             if handler 
                             else f"Unknown tool: {block.name}")
                except Exception as e:
                    # 如果工具执行出错
                    output = f"Error: {e}"
                
                # 打印工具执行的结果（用于调试）
                print(f"> {block.name}: {str(output)[:200]}")
                
                # 记录工具的执行结果
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,      # AI 用这个ID来引用结果
                    "content": str(output)        # 工具的执行结果
                })
                
                if block.name == "TodoWrite":  # 标记使用了待办功能
                    used_todo = True
        
        # ============ 齿轮3️⃣：待办提醒（s03）============
        # 如果 AI 有打开的待办事项，但很多轮都没有管它们
        # 就在消息中"碎碎念"提醒 AI
        rounds_without_todo = 0 if used_todo else rounds_without_todo + 1
        
        if TODO.has_open_items() and rounds_without_todo >= 3:
            # 提醒 AI："嘿，你还有待办事项没处理呢！"
            results.insert(0, {"type": "text", "text": "<reminder>Update your todos.</reminder>"})
        
        # 把所有工具执行的结果返回给 AI
        messages.append({"role": "user", "content": results})
        
        # ============ 额外功能：手动压缩（齿轮5️⃣）============
        # 如果 AI 主动要求压缩消息，就执行压缩
        if manual_compress:
            print("[manual compact]")
            messages[:] = auto_compact(messages)
        
        # 循环回到最开始（无限循环）


# ============ REPL（用户交互界面）============
# === SECTION: repl ===
if __name__ == "__main__":
    """
    ★ REPL = Read-Eval-Print Loop（读取-求值-打印循环）
    
    这是一个"会话模式"，让你和 AI 对话
    
    流程：
    1. 读取你的输入
    2. 让 AI 处理
    3. 打印 AI 的输出
    4. 重复...
    
    特殊命令：
    /compact     → 手动压缩消息历史
    /tasks       → 列出所有任务
    /team        → 列出所有秘书  
    /inbox       → 检查收件箱
    """
    history = []  # 对话历史
    
    while True:
        try:
            # 等待用户输入（提示符是 "s_full >> " 的青色版本）
            query = input("\033[36ms_full >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        if query.strip() == "/compact":
            if history:
                print("[manual compact via /compact]")
                history[:] = auto_compact(history)
            continue
        if query.strip() == "/tasks":
            print(TASK_MGR.list_all())
            continue
        if query.strip() == "/team":
            print(TEAM.list_all())
            continue
        if query.strip() == "/inbox":
            print(json.dumps(BUS.read_inbox("lead"), indent=2))
            continue
        history.append({"role": "user", "content": query})
        agent_loop(history)
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if hasattr(block, "text"):
                    print(block.text)
        print()