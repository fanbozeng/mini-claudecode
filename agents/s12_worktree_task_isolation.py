#!/usr/bin/env python3
# Shebang行，指定使用Python3解释器运行此脚本
# Harness: directory isolation -- parallel execution lanes that never collide.
# 工具集：目录隔离 -- 永不冲突的并行执行通道
"""
s12_worktree_task_isolation.py - Worktree + Task Isolation
# s12_worktree_task_isolation.py - 工作树 + 任务隔离

这一章在解决一个非常实际的问题：
如果很多任务都挤在同一个目录里同时修改代码，
就很容易你碰我、我碰你，最后谁都分不清自己改了什么。

所以这一章的办法很像老师给小朋友分座位：
1. 每个任务先拿到一张“任务卡”。
2. 再给这个任务安排一张自己的“小书桌”。
3. 这个“小书桌”就是一个独立目录，也就是 `worktree`。

你可以先记住本章最重要的一句口诀：
"任务卡决定做什么，worktree 决定在哪里做。"

再说得更温柔一点就是：
1. `task` 像任务清单，负责记录目标、状态、负责人。
2. `worktree` 像独立施工区，负责真正动手改代码。
3. 大家靠 `task_id` 对上号，这样就不会乱。

所以文档里说：
Directory-level isolation for parallel task execution.
Tasks are the control plane and worktrees are the execution plane.

小朋友版理解：
1. “控制平面”就是负责安排和记录。
2. “执行平面”就是负责真正去干活。
3. 一个管“计划”，一个管“施工现场”。

    .tasks/task_12.json
    # .tasks/task_12.json 任务文件示例
      {
        "id": 12,
        "subject": "Implement auth refactor",
        "status": "in_progress",
        "worktree": "auth-refactor"
      }

    .worktrees/index.json
    # .worktrees/index.json 工作树索引文件示例
      {
        "worktrees": [
          {
            "name": "auth-refactor",
            "path": ".../.worktrees/auth-refactor",
            "branch": "wt/auth-refactor",
            "task_id": 12,
            "status": "active"
          }
        ]
      }

读这一章时，可以重点观察 6 个地方：
1. `detect_repo_root`：先搞清楚“大房子”的根目录在哪。
2. `EventBus`：像值班记录本，记下发生过什么。
3. `TaskManager`：像任务墙，管理任务卡。
4. `WorktreeManager`：像安排独立工位的管理员。
5. `worktree_run`：命令不是随便跑，而是在指定工位里跑。
6. `keep/remove`：任务做完后，这个工位是保留，还是收拾掉。

Key insight: "Isolate by directory, coordinate by task ID."
# 关键洞察："通过目录隔离，通过任务ID协调"
"""

import json  # 导入JSON模块，用于处理JSON数据格式
import os  # 导入操作系统模块，用于环境变量和路径操作
import re  # 导入正则表达式模块，用于字符串模式匹配
import subprocess  # 导入子进程模块，用于执行外部命令
import time  # 导入时间模块，用于时间戳和延迟
from pathlib import Path  # 从pathlib导入Path类，用于路径操作
from typing import Optional  # Python 3.9 兼容的类型注解

from anthropic import Anthropic  # 导入Anthropic客户端，用于AI模型调用
from dotenv import load_dotenv  # 导入dotenv，用于加载环境变量文件

load_dotenv(override=True)  # 加载.env文件中的环境变量，覆盖现有变量

if os.getenv("ANTHROPIC_BASE_URL"):  # 如果设置了自定义Anthropic基础URL
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)  # 移除认证令牌环境变量

WORKDIR = Path.cwd()  # 获取当前工作目录的Path对象
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))  # 创建Anthropic客户端实例
MODEL = os.environ["MODEL_ID"]  # 从环境变量获取模型ID


def detect_repo_root(cwd: Path) -> Optional[Path]:
    # 别怕这个名字长，它做的事其实很简单：
    # 它在问：“我们现在站的这个目录，属于哪一个 Git 项目？”
    # 如果能找到项目最顶层目录，就把那个“总门牌号”找出来。
    # 检测Git仓库根目录的函数
    # 如果当前工作目录在Git仓库内，返回仓库根目录，否则返回None
    """Return git repo root if cwd is inside a repo, else None."""
    # 返回Git仓库根目录，如果cwd在仓库内，否则返回None
    try:
        # 尝试运行git rev-parse --show-toplevel命令获取仓库根目录
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],  # Git命令：显示仓库顶级目录
            cwd=cwd,  # 在指定目录中运行命令
            capture_output=True,  # 捕获标准输出和错误输出
            text=True,  # 以文本模式返回输出
            timeout=10,  # 设置10秒超时
        )
        if r.returncode != 0:  # 如果命令执行失败（非零返回码）
            return None  # 返回None表示不在Git仓库中
        root = Path(r.stdout.strip())  # 获取并清理输出，转换为Path对象
        return root if root.exists() else None  # 如果路径存在则返回，否则返回None
    except Exception:  # 捕获任何异常（包括超时、命令不存在等）
        return None  # 返回None表示检测失败


REPO_ROOT = detect_repo_root(WORKDIR) or WORKDIR  # 检测仓库根目录，如果失败则使用当前工作目录

REPO_ROOT = detect_repo_root(WORKDIR) or WORKDIR  # 检测仓库根目录，如果失败则使用当前工作目录

# 这里是给模型看的“上课要求”。
# 它会提醒代理：
# 不要把多任务都混在一个地方做，
# 而是先建任务，再分配 worktree，再到对应的地方动手。
SYSTEM = (
    f"You are a coding agent at {WORKDIR}. "
    "Use task + worktree tools for multi-task work. "
    "For parallel or risky changes: create tasks, allocate worktree lanes, "
    "run commands in those lanes, then choose keep/remove for closeout. "
    "Use worktree_events when you need lifecycle visibility."
)
# 系统提示信息，指导AI代理如何使用任务和工作树工具
# 告诉代理使用任务+工作树工具进行多任务工作
# 对于并行或有风险的更改：创建任务，分配工作树通道，在这些通道中运行命令，然后选择保留/删除来结束


# -- EventBus: append-only lifecycle events for observability --
# 事件总线：仅追加的生命周期事件，用于可观察性
class EventBus:
    # 可以把 EventBus 想成“值班记录本”。
    # 每当系统里发生一件重要事情，
    # 比如创建 worktree、删除 worktree、任务完成，
    # 我们都往记录本里追加一条。
    #
    # 为什么这样好？
    # 因为以后如果出问题，就能回头看：
    # “刚才到底发生了什么？”
    # EventBus类：用于记录和跟踪工作树和任务的生命周期事件
    def __init__(self, event_log_path: Path):
        # 初始化事件总线
        self.path = event_log_path  # 事件日志文件路径
        self.path.parent.mkdir(parents=True, exist_ok=True)  # 确保父目录存在
        if not self.path.exists():  # 如果日志文件不存在
            self.path.write_text("")  # 创建空文件

    def emit(
        self,
        event: str,  # 事件名称
        task: dict | None = None,  # 相关任务信息（可选）
        worktree: dict | None = None,  # 相关工作树信息（可选）
        error: str | None = None,  # 错误信息（可选）
    ):
        # 发出事件的方法，将事件记录到日志文件中
        # 这里用“只追加、不回头改”的写法，
        # 很像写流水账：
        # 一件事写一行，下一件事再接着写。
        # 这样最不容易把旧记录弄乱。
        payload = {
            "event": event,  # 事件类型
            "ts": time.time(),  # 时间戳
            "task": task or {},  # 任务信息，默认为空字典
            "worktree": worktree or {},  # 工作树信息，默认为空字典
        }
        if error:  # 如果有错误信息
            payload["error"] = error  # 添加错误字段
        with self.path.open("a", encoding="utf-8") as f:  # 以追加模式打开文件
            f.write(json.dumps(payload) + "\n")  # 写入JSON格式的事件记录

    def list_recent(self, limit: int = 20) -> str:
        # 列出最近的事件记录
        # 这就像翻到记录本最后几页，
        # 看看最近发生了哪些事情。
        n = max(1, min(int(limit or 20), 200))  # 限制查询数量在1-200之间
        lines = self.path.read_text(encoding="utf-8").splitlines()  # 读取所有行
        recent = lines[-n:]  # 获取最近n行
        items = []
        for line in recent:
            try:
                items.append(json.loads(line))  # 解析JSON
            except Exception:
                items.append({"event": "parse_error", "raw": line})  # 解析失败时记录错误
        return json.dumps(items, indent=2)  # 返回格式化的JSON字符串


# -- TaskManager: persistent task board with optional worktree binding --
# 任务管理器：具有可选工作树绑定的持久任务板
class TaskManager:
    # TaskManager 就像“任务墙管理员”。
    # 它负责管理一张张任务卡：
    # 有人新建任务卡、查看任务卡、更新任务卡，
    # 都由它来负责。
    #
    # 这一章里，任务卡最重要的意义不是直接改代码，
    # 而是让大家先把“要做哪件事”说清楚。
    # TaskManager类：管理持久化任务板，支持可选的工作树绑定
    def __init__(self, tasks_dir: Path):
        # 初始化任务管理器
        self.dir = tasks_dir  # 任务目录路径
        self.dir.mkdir(parents=True, exist_ok=True)  # 确保目录存在
        self._next_id = self._max_id() + 1  # 计算下一个任务ID

    def _max_id(self) -> int:
        # 获取当前最大任务ID的私有方法
        ids = []
        for f in self.dir.glob("task_*.json"):  # 遍历所有任务文件
            try:
                ids.append(int(f.stem.split("_")[1]))  # 提取文件名的ID部分
            except Exception:
                pass  # 忽略解析错误
        return max(ids) if ids else 0  # 返回最大ID或0

    def _path(self, task_id: int) -> Path:
        # 生成任务文件路径的私有方法
        return self.dir / f"task_{task_id}.json"  # 返回任务文件路径

    def _load(self, task_id: int) -> dict:
        # 加载任务数据的私有方法
        path = self._path(task_id)  # 获取任务文件路径
        if not path.exists():  # 如果文件不存在
            raise ValueError(f"Task {task_id} not found")  # 抛出错误
        return json.loads(path.read_text())  # 读取并解析JSON

    def _save(self, task: dict):
        # 保存任务数据的私有方法
        self._path(task["id"]).write_text(json.dumps(task, indent=2))  # 写入JSON文件

    def create(self, subject: str, description: str = "") -> str:
        # 创建新任务的方法
        # 先别急着改代码，先做一张任务卡。
        # 这一步很像先写作业标题：
        # “我要做什么、它现在是什么状态、谁在负责它”。
        task = {
            "id": self._next_id,  # 任务ID
            "subject": subject,  # 任务主题
            "description": description,  # 任务描述
            "status": "pending",  # 初始状态为待处理
            "owner": "",  # 所有者（初始为空）
            "worktree": "",  # 绑定的工作树（初始为空）
            "blockedBy": [],  # 被阻塞的任务列表
            "created_at": time.time(),  # 创建时间戳
            "updated_at": time.time(),  # 更新时间戳
        }
        self._save(task)  # 保存任务
        self._next_id += 1  # 递增下一个ID
        return json.dumps(task, indent=2)  # 返回任务JSON字符串

    def get(self, task_id: int) -> str:
        # 获取任务详情的方法
        return json.dumps(self._load(task_id), indent=2)  # 返回任务JSON字符串

    def exists(self, task_id: int) -> bool:
        # 检查任务是否存在的方法
        return self._path(task_id).exists()  # 检查任务文件是否存在

    def update(self, task_id: int, status: str = None, owner: str = None) -> str:
        # 更新任务状态或所有者的方法
        # 一张任务卡会随着进度变化：
        # pending -> 还没开始
        # in_progress -> 正在做
        # completed -> 做完了
        task = self._load(task_id)  # 加载任务
        if status:  # 如果提供了状态
            if status not in ("pending", "in_progress", "completed"):  # 验证状态值
                raise ValueError(f"Invalid status: {status}")  # 无效状态抛出错误
            task["status"] = status  # 更新状态
        if owner is not None:  # 如果提供了所有者
            task["owner"] = owner  # 更新所有者
        task["updated_at"] = time.time()  # 更新时间戳
        self._save(task)  # 保存任务
        return json.dumps(task, indent=2)  # 返回更新后的任务JSON

    def bind_worktree(self, task_id: int, worktree: str, owner: str = "") -> str:
        # 绑定工作树到任务的方法
        # bind 的意思就是“把两样东西绑在一起”。
        # 这里是把“任务卡”和“独立工位”连起来。
        # 连好以后，我们就知道：
        # “这个任务，应该去哪个目录里施工。”
        task = self._load(task_id)  # 加载任务
        task["worktree"] = worktree  # 设置工作树绑定
        if owner:  # 如果提供了所有者
            task["owner"] = owner  # 设置所有者
        if task["status"] == "pending":  # 如果任务状态为待处理
            task["status"] = "in_progress"  # 改为进行中
        task["updated_at"] = time.time()  # 更新时间戳
        self._save(task)  # 保存任务
        return json.dumps(task, indent=2)  # 返回更新后的任务JSON

    def unbind_worktree(self, task_id: int) -> str:
        # 解除工作树绑定的方法
        # 当任务结束，或者这个工位不再使用时，
        # 就可以把它们松开，不再继续绑定。
        task = self._load(task_id)  # 加载任务
        task["worktree"] = ""  # 清空工作树绑定
        task["updated_at"] = time.time()  # 更新时间戳
        self._save(task)  # 保存任务
        return json.dumps(task, indent=2)  # 返回更新后的任务JSON

    def list_all(self) -> str:
        # 列出所有任务的方法
        # 这像在看任务墙总览：
        # 一眼就能知道每张卡片现在是谁负责、进度到哪里、有没有绑定工位。
        tasks = []
        for f in sorted(self.dir.glob("task_*.json")):  # 遍历排序后的任务文件
            tasks.append(json.loads(f.read_text()))  # 读取并解析每个任务
        if not tasks:  # 如果没有任务
            return "No tasks."  # 返回无任务消息
        lines = []
        for t in tasks:
            # 根据任务状态选择标记符号
            marker = {
                "pending": "[ ]",  # 待处理：空方框
                "in_progress": "[>]",  # 进行中：箭头
                "completed": "[x]",  # 已完成：叉号
            }.get(t["status"], "[?]")  # 默认未知状态
            owner = f" owner={t['owner']}" if t.get("owner") else ""  # 所有者信息
            wt = f" wt={t['worktree']}" if t.get("worktree") else ""  # 工作树信息
            lines.append(f"{marker} #{t['id']}: {t['subject']}{owner}{wt}")  # 格式化任务行
        return "\n".join(lines)  # 返回所有任务行的字符串


TASKS = TaskManager(REPO_ROOT / ".tasks")  # 创建任务管理器实例，使用.tasks目录
EVENTS = EventBus(REPO_ROOT / ".worktrees" / "events.jsonl")  # 创建事件总线实例，使用events.jsonl文件


# -- WorktreeManager: create/list/run/remove git worktrees + lifecycle index --
# 工作树管理器：创建/列出/运行/删除Git工作树 + 生命周期索引
class WorktreeManager:
    # 这一章真正的新主角就在这里。
    #
    # 把 worktree 想成“给任务单独准备的一张书桌”会很好懂：
    # 1. 同一个仓库可以长出多个独立工作目录。
    # 2. 每个目录都能单独改代码、跑命令、看 git 状态。
    # 3. 因为大家不挤在同一张桌子上，所以互相更不容易撞车。
    # WorktreeManager类：管理Git工作树的创建、列出、运行、删除，并维护生命周期索引
    def __init__(self, repo_root: Path, tasks: TaskManager, events: EventBus):
        # 初始化工作树管理器
        self.repo_root = repo_root  # Git仓库根目录
        self.tasks = tasks  # 任务管理器实例
        self.events = events  # 事件总线实例
        self.dir = repo_root / ".worktrees"  # 工作树目录
        self.dir.mkdir(parents=True, exist_ok=True)  # 确保目录存在
        self.index_path = self.dir / "index.json"  # 索引文件路径
        if not self.index_path.exists():  # 如果索引文件不存在
            self.index_path.write_text(json.dumps({"worktrees": []}, indent=2))  # 创建初始索引
        self.git_available = self._is_git_repo()  # 检查Git是否可用

    def _is_git_repo(self) -> bool:
        # 检查是否在Git仓库中的私有方法
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],  # Git命令：检查是否在工作树内
                cwd=self.repo_root,  # 在仓库根目录运行
                capture_output=True,  # 捕获输出
                text=True,  # 文本模式
                timeout=10,  # 10秒超时
            )
            return r.returncode == 0  # 返回码为0表示在Git仓库中
        except Exception:
            return False  # 异常情况下返回False

    def _run_git(self, args: list[str]) -> str:
        # 运行Git命令的私有方法
        # 所有真正和 git worktree 打交道的命令，
        # 都集中从这里过一遍。
        # 这样比较像“统一门卫”，更容易管理和报错。
        if not self.git_available:  # 如果Git不可用
            raise RuntimeError("Not in a git repository. worktree tools require git.")  # 抛出错误
        r = subprocess.run(
            ["git", *args],  # 运行Git命令
            cwd=self.repo_root,  # 在仓库根目录运行
            capture_output=True,  # 捕获输出
            text=True,  # 文本模式
            timeout=120,  # 120秒超时
        )
        if r.returncode != 0:  # 如果命令失败
            msg = (r.stdout + r.stderr).strip()  # 获取错误消息
            raise RuntimeError(msg or f"git {' '.join(args)} failed")  # 抛出运行时错误
        return (r.stdout + r.stderr).strip() or "(no output)"  # 返回输出或默认消息

    def _load_index(self) -> dict:
        # 加载索引文件的私有方法
        return json.loads(self.index_path.read_text())  # 读取并解析索引JSON

    def _save_index(self, data: dict):
        # 保存索引文件的私有方法
        self.index_path.write_text(json.dumps(data, indent=2))  # 写入格式化的JSON

    def _find(self, name: str) -> dict | None:
        # 根据名称查找工作树的私有方法
        idx = self._load_index()  # 加载索引
        for wt in idx.get("worktrees", []):  # 遍历工作树列表
            if wt.get("name") == name:  # 如果名称匹配
                return wt  # 返回工作树信息
        return None  # 未找到返回None

    def _validate_name(self, name: str):
        # 验证工作树名称的私有方法
        # 为什么名字要检查？
        # 因为 worktree 名字后面会拿去当目录名、分支名，
        # 如果里面混进奇怪字符，就容易出问题。
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", name or ""):  # 正则表达式验证名称格式
            raise ValueError(
                "Invalid worktree name. Use 1-40 chars: letters, numbers, ., _, -"
            )  # 无效名称抛出错误

    def create(self, name: str, task_id: int = None, base_ref: str = "HEAD") -> str:
        # 创建工作树的方法
        # 这一步像给任务分配一个独立工位。
        # 它会做几件事：
        # 1. 检查名字能不能用。
        # 2. 调 git 创建新的 worktree 目录和分支。
        # 3. 把这张工位信息写进 index。
        # 4. 如果给了 task_id，就顺手把任务卡和工位绑定起来。
        self._validate_name(name)  # 验证工作树名称
        if self._find(name):  # 如果工作树已存在
            raise ValueError(f"Worktree '{name}' already exists in index")  # 抛出错误
        if task_id is not None and not self.tasks.exists(task_id):  # 如果任务ID存在但任务不存在
            raise ValueError(f"Task {task_id} not found")  # 抛出错误

        path = self.dir / name  # 工作树路径
        branch = f"wt/{name}"  # 分支名称
        self.events.emit(  # 发出创建前事件
            "worktree.create.before",  # 事件类型
            task={"id": task_id} if task_id is not None else {},  # 任务信息
            worktree={"name": name, "base_ref": base_ref},  # 工作树信息
        )
        try:
            # 运行git worktree add命令创建工作树
            # `git worktree add -b ...` 可以简单理解成：
            # “从现有仓库分出一个新的施工位，并给它一条自己的分支。”
            self._run_git(["worktree", "add", "-b", branch, str(path), base_ref])

            entry = {  # 创建工作树条目
                "name": name,  # 名称
                "path": str(path),  # 路径
                "branch": branch,  # 分支
                "task_id": task_id,  # 任务ID
                "status": "active",  # 状态
                "created_at": time.time(),  # 创建时间
            }

            idx = self._load_index()  # 加载索引
            idx["worktrees"].append(entry)  # 添加条目
            self._save_index(idx)  # 保存索引

            if task_id is not None:  # 如果有关联任务
                self.tasks.bind_worktree(task_id, name)  # 绑定工作树到任务

            self.events.emit(  # 发出创建后事件
                "worktree.create.after",
                task={"id": task_id} if task_id is not None else {},
                worktree={
                    "name": name,
                    "path": str(path),
                    "branch": branch,
                    "status": "active",
                },
            )
            return json.dumps(entry, indent=2)  # 返回工作树条目JSON
        except Exception as e:  # 捕获异常
            self.events.emit(  # 发出创建失败事件
                "worktree.create.failed",
                task={"id": task_id} if task_id is not None else {},
                worktree={"name": name, "base_ref": base_ref},
                error=str(e),  # 错误信息
            )
            raise  # 重新抛出异常

    def list_all(self) -> str:
        # 列出所有工作树的方法
        # 这里看到的是“工位名单”。
        # 会告诉我们：有哪些 worktree、它们在哪、对应哪个任务。
        idx = self._load_index()  # 加载索引
        wts = idx.get("worktrees", [])  # 获取工作树列表
        if not wts:  # 如果没有工作树
            return "No worktrees in index."  # 返回无工作树消息
        lines = []
        for wt in wts:
            suffix = f" task={wt['task_id']}" if wt.get("task_id") else ""  # 任务ID后缀
            lines.append(
                f"[{wt.get('status', 'unknown')}] {wt['name']} -> "  # 状态和名称
                f"{wt['path']} ({wt.get('branch', '-')}){suffix}"  # 路径、分支和任务信息
            )
        return "\n".join(lines)  # 返回格式化的工作树列表

    def status(self, name: str) -> str:
        # 获取工作树Git状态的方法
        # 这就像走到某张书桌前看一眼：
        # “这个工位现在干净吗？有没有没提交的改动？”
        wt = self._find(name)  # 查找工作树
        if not wt:  # 如果未找到
            return f"Error: Unknown worktree '{name}'"  # 返回错误消息
        path = Path(wt["path"])  # 获取工作树路径
        if not path.exists():  # 如果路径不存在
            return f"Error: Worktree path missing: {path}"  # 返回错误消息
        r = subprocess.run(
            ["git", "status", "--short", "--branch"],  # Git状态命令
            cwd=path,  # 在工作树目录运行
            capture_output=True,  # 捕获输出
            text=True,  # 文本模式
            timeout=60,  # 60秒超时
        )
        text = (r.stdout + r.stderr).strip()  # 获取输出
        return text or "Clean worktree"  # 返回状态或默认消息

    def run(self, name: str, command: str) -> str:
        # 在工作树中运行命令的方法
        # 这是本章一个非常关键的点。
        # 不是只会 `bash`，而是会“在指定工位里 bash”。
        #
        # 普通 `bash`：
        # 在当前大工作区运行命令。
        #
        # `worktree_run`：
        # 先走到某个任务自己的目录，再在那个目录里运行命令。
        #
        # 这样每个任务就像在自己的小房间里做事，更安全。
        dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]  # 危险命令列表
        if any(d in command for d in dangerous):  # 如果包含危险命令
            return "Error: Dangerous command blocked"  # 返回阻止消息

        wt = self._find(name)  # 查找工作树
        if not wt:  # 如果未找到
            return f"Error: Unknown worktree '{name}'"  # 返回错误消息
        path = Path(wt["path"])  # 获取工作树路径
        if not path.exists():  # 如果路径不存在
            return f"Error: Worktree path missing: {path}"  # 返回错误消息

        try:
            r = subprocess.run(
                command,  # 要运行的命令
                shell=True,  # 使用shell执行
                cwd=path,  # 在工作树目录运行
                capture_output=True,  # 捕获输出
                text=True,  # 文本模式
                timeout=300,  # 300秒超时
            )
            out = (r.stdout + r.stderr).strip()  # 获取输出
            return out[:50000] if out else "(no output)"  # 返回输出或默认消息
        except subprocess.TimeoutExpired:  # 超时异常
            return "Error: Timeout (300s)"  # 返回超时错误

    def remove(self, name: str, force: bool = False, complete_task: bool = False) -> str:
        # 删除工作树的方法
        # remove 像“收拾工位并撤掉它”。
        # 如果这个工位的任务也确实做完了，
        # 还可以顺手把任务卡改成 completed。
        wt = self._find(name)  # 查找工作树
        if not wt:  # 如果未找到
            return f"Error: Unknown worktree '{name}'"  # 返回错误消息

        self.events.emit(  # 发出删除前事件
            "worktree.remove.before",
            task={"id": wt.get("task_id")} if wt.get("task_id") is not None else {},
            worktree={"name": name, "path": wt.get("path")},
        )
        try:
            args = ["worktree", "remove"]  # Git worktree remove命令
            if force:  # 如果强制删除
                args.append("--force")  # 添加--force参数
            args.append(wt["path"])  # 添加工作树路径
            self._run_git(args)  # 运行Git命令

            if complete_task and wt.get("task_id") is not None:  # 如果需要完成任务
                # 这里把“施工结束”和“任务完成”连起来了。
                # 注意：这不是自动永远发生，而是只有传入 complete_task=True 才会做。
                task_id = wt["task_id"]  # 获取任务ID
                before = json.loads(self.tasks.get(task_id))  # 获取任务之前的状态
                self.tasks.update(task_id, status="completed")  # 更新任务状态为已完成
                self.tasks.unbind_worktree(task_id)  # 解除工作树绑定
                self.events.emit(  # 发出任务完成事件
                    "task.completed",
                    task={
                        "id": task_id,
                        "subject": before.get("subject", ""),
                        "status": "completed",
                    },
                    worktree={"name": name},
                )

            idx = self._load_index()  # 加载索引
            for item in idx.get("worktrees", []):  # 遍历工作树列表
                if item.get("name") == name:  # 找到要删除的工作树
                    item["status"] = "removed"  # 标记为已删除
                    item["removed_at"] = time.time()  # 记录删除时间
            self._save_index(idx)  # 保存索引

            self.events.emit(  # 发出删除后事件
                "worktree.remove.after",
                task={"id": wt.get("task_id")} if wt.get("task_id") is not None else {},
                worktree={"name": name, "path": wt.get("path"), "status": "removed"},
            )
            return f"Removed worktree '{name}'"  # 返回成功消息
        except Exception as e:  # 捕获异常
            self.events.emit(  # 发出删除失败事件
                "worktree.remove.failed",
                task={"id": wt.get("task_id")} if wt.get("task_id") is not None else {},
                worktree={"name": name, "path": wt.get("path")},
                error=str(e),  # 错误信息
            )
            raise  # 重新抛出异常

    def keep(self, name: str) -> str:
        # 保留工作树的方法（标记为保留状态）
        # `keep` 和 `remove` 很像一对选择题：
        #
        # `keep`：
        # 这个工位我先留着，也许还要继续看、继续改、继续检查。
        #
        # `remove`：
        # 这个工位已经不用了，可以收掉。
        #
        # 所以 `keep` 不是“什么都不做”，
        # 它是在生命周期里明确记一笔：
        # “这个工位决定保留。”
        wt = self._find(name)  # 查找工作树
        if not wt:  # 如果未找到
            return f"Error: Unknown worktree '{name}'"  # 返回错误消息

        idx = self._load_index()  # 加载索引
        kept = None
        for item in idx.get("worktrees", []):  # 遍历工作树列表
            if item.get("name") == name:  # 找到工作树
                item["status"] = "kept"  # 标记为保留
                item["kept_at"] = time.time()  # 记录保留时间
                kept = item  # 保存条目
        self._save_index(idx)  # 保存索引

        self.events.emit(  # 发出保留事件
            "worktree.keep",
            task={"id": wt.get("task_id")} if wt.get("task_id") is not None else {},
            worktree={
                "name": name,
                "path": wt.get("path"),
                "status": "kept",
            },
        )
        return json.dumps(kept, indent=2) if kept else f"Error: Unknown worktree '{name}'"  # 返回条目或错误消息


WORKTREES = WorktreeManager(REPO_ROOT, TASKS, EVENTS)  # 创建工作树管理器实例


# -- Base tools (kept minimal, same style as previous sessions) --
# 基础工具（保持最小化，与之前会话相同的风格）
# 下面这些是“给模型用的基础小工具”。
# 你可以把它们想成代理的小工具箱。
# 这一章里最值得对比的是：
# 1. `run_bash` 在当前工作区执行。
# 2. `WORKTREES.run(...)` 在某个指定 worktree 里执行。
def safe_path(p: str) -> Path:
    # 安全路径函数，确保路径在工作目录内，防止路径遍历攻击
    # 这像画一条安全边界线：
    # “你可以在项目里活动，但不要跑到项目外面去乱动东西。”
    path = (WORKDIR / p).resolve()  # 解析绝对路径
    if not path.is_relative_to(WORKDIR):  # 检查是否在工作目录内
        raise ValueError(f"Path escapes workspace: {p}")  # 抛出安全错误
    return path  # 返回安全路径


def run_bash(command: str) -> str:
    # 运行bash命令的安全函数
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]  # 危险命令列表
    if any(d in command for d in dangerous):  # 检查是否包含危险命令
        return "Error: Dangerous command blocked"  # 阻止执行
    try:
        r = subprocess.run(
            command,  # 要执行的命令
            shell=True,  # 使用shell执行
            cwd=WORKDIR,  # 在工作目录执行
            capture_output=True,  # 捕获标准输出和错误输出
            text=True,  # 以文本模式返回
            timeout=120,  # 设置120秒超时
        )
        out = (r.stdout + r.stderr).strip()  # 合并输出
        return out[:50000] if out else "(no output)"  # 返回输出或默认消息
    except subprocess.TimeoutExpired:  # 超时异常
        return "Error: Timeout (120s)"  # 返回超时错误


def run_read(path: str, limit: int = None) -> str:
    # 读取文件内容的安全函数
    try:
        lines = safe_path(path).read_text().splitlines()  # 读取文件并分割为行
        if limit and limit < len(lines):  # 如果设置了行数限制且超过限制
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]  # 截断并添加省略提示
        return "\n".join(lines)[:50000]  # 合并行并限制总长度
    except Exception as e:  # 捕获异常
        return f"Error: {e}"  # 返回错误消息


def run_write(path: str, content: str) -> str:
    # 写入文件内容的安全函数
    try:
        fp = safe_path(path)  # 获取安全路径
        fp.parent.mkdir(parents=True, exist_ok=True)  # 确保父目录存在
        fp.write_text(content)  # 写入内容
        return f"Wrote {len(content)} bytes"  # 返回写入的字节数
    except Exception as e:  # 捕获异常
        return f"Error: {e}"  # 返回错误消息


def run_edit(path: str, old_text: str, new_text: str) -> str:
    # 编辑文件内容的安全函数（替换文本）
    # 这里要求 old_text 必须真的存在，
    # 是为了让修改更像“精准换一块积木”，
    # 而不是模模糊糊地乱改。
    try:
        fp = safe_path(path)  # 获取安全路径
        c = fp.read_text()  # 读取文件内容
        if old_text not in c:  # 如果旧文本不在文件中
            return f"Error: Text not found in {path}"  # 返回错误消息
        fp.write_text(c.replace(old_text, new_text, 1))  # 替换第一次出现的旧文本
        return f"Edited {path}"  # 返回成功消息
    except Exception as e:  # 捕获异常
        return f"Error: {e}"  # 返回错误消息


TOOL_HANDLERS = {
    # 工具处理器字典，将工具名称映射到相应的处理函数
    # 每个条目都是一个lambda函数，接收关键字参数并调用相应的执行函数
    # 你可以把它想成“工具遥控器背后的接线板”：
    # 模型说工具名，Python 就来这里找到真正要执行的函数。
    "bash": lambda **kw: run_bash(kw["command"]),  # bash命令执行器
    "read_file": lambda **kw: run_read(kw["path"], kw.get("limit")),  # 文件读取器，可选行数限制
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),  # 文件写入器
    "edit_file": lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),  # 文件编辑器（文本替换）
    "task_create": lambda **kw: TASKS.create(kw["subject"], kw.get("description", "")),  # 任务创建器
    "task_list": lambda **kw: TASKS.list_all(),  # 任务列表查看器
    "task_get": lambda **kw: TASKS.get(kw["task_id"]),  # 任务详情获取器
    "task_update": lambda **kw: TASKS.update(kw["task_id"], kw.get("status"), kw.get("owner")),  # 任务更新器
    "task_bind_worktree": lambda **kw: TASKS.bind_worktree(kw["task_id"], kw["worktree"], kw.get("owner", "")),  # 任务工作树绑定器
    "worktree_create": lambda **kw: WORKTREES.create(kw["name"], kw.get("task_id"), kw.get("base_ref", "HEAD")),  # 工作树创建器
    "worktree_list": lambda **kw: WORKTREES.list_all(),  # 工作树列表查看器
    "worktree_status": lambda **kw: WORKTREES.status(kw["name"]),  # 工作树状态查看器
    "worktree_run": lambda **kw: WORKTREES.run(kw["name"], kw["command"]),  # 工作树命令运行器
    "worktree_keep": lambda **kw: WORKTREES.keep(kw["name"]),  # 工作树保留器
    "worktree_remove": lambda **kw: WORKTREES.remove(kw["name"], kw.get("force", False), kw.get("complete_task", False)),  # 工作树删除器
    "worktree_events": lambda **kw: EVENTS.list_recent(kw.get("limit", 20)),  # 工作树事件查看器
}

TOOLS = [
    # 工具规范列表，定义了所有可用工具的名称、描述和输入模式
    # 每个工具都有一个JSON schema定义其输入参数的结构和类型
    # 这些工具分为基础工具、任务管理工具、工作树管理工具和事件查看工具
    #
    # 这里不是“执行代码”的地方，
    # 而是“把工具菜单展示给模型看”的地方。
    # 所以这一章常见的一组配对关系是：
    # 1. `TOOL_HANDLERS` 负责真的执行。
    # 2. `TOOLS` 负责告诉模型有哪些按钮可以按。
    {
        "name": "bash",  # bash命令工具
        "description": "Run a shell command in the current workspace (blocking).",  # 在当前工作空间运行shell命令（阻塞）
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},  # 输入参数：命令字符串
            "required": ["command"],  # 必需参数
        },
    },
    {
        "name": "read_file",  # 文件读取工具
        "description": "Read file contents.",  # 读取文件内容
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},  # 文件路径
                "limit": {"type": "integer"},  # 可选的行数限制
            },
            "required": ["path"],  # 必需参数：路径
        },
    },
    {
        "name": "write_file",  # 文件写入工具
        "description": "Write content to file.",  # 写入内容到文件
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},  # 文件路径
                "content": {"type": "string"},  # 文件内容
            },
            "required": ["path", "content"],  # 必需参数：路径和内容
        },
    },
    {
        "name": "edit_file",  # 文件编辑工具
        "description": "Replace exact text in file.",  # 在文件中替换确切文本
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},  # 文件路径
                "old_text": {"type": "string"},  # 要替换的旧文本
                "new_text": {"type": "string"},  # 新的文本
            },
            "required": ["path", "old_text", "new_text"],  # 必需参数：路径、旧文本、新文本
        },
    },
    {
        "name": "task_create",  # 任务创建工具
        "description": "Create a new task on the shared task board.",  # 在共享任务板上创建新任务
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},  # 任务主题
                "description": {"type": "string"},  # 可选的任务描述
            },
            "required": ["subject"],  # 必需参数：主题
        },
    },
    {
        "name": "task_list",  # 任务列表工具
        "description": "List all tasks with status, owner, and worktree binding.",  # 列出所有任务及其状态、所有者和工作树绑定
        "input_schema": {"type": "object", "properties": {}},  # 无输入参数
    },
    {
        "name": "task_get",  # 任务获取工具
        "description": "Get task details by ID.",  # 通过ID获取任务详情
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer"}},  # 任务ID
            "required": ["task_id"],  # 必需参数：任务ID
        },
    },
    {
        "name": "task_update",  # 任务更新工具
        "description": "Update task status or owner.",  # 更新任务状态或所有者
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},  # 任务ID
                "status": {  # 可选的状态
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed"],  # 状态枚举值
                },
                "owner": {"type": "string"},  # 可选的所有者
            },
            "required": ["task_id"],  # 必需参数：任务ID
        },
    },
    {
        "name": "task_bind_worktree",  # 任务工作树绑定工具
        "description": "Bind a task to a worktree name.",  # 将任务绑定到工作树名称
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},  # 任务ID
                "worktree": {"type": "string"},  # 工作树名称
                "owner": {"type": "string"},  # 可选的所有者
            },
            "required": ["task_id", "worktree"],  # 必需参数：任务ID和工作树
        },
    },
    {
        "name": "worktree_create",  # 工作树创建工具
        "description": "Create a git worktree and optionally bind it to a task.",  # 创建Git工作树并可选绑定到任务
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},  # 工作树名称
                "task_id": {"type": "integer"},  # 可选的任务ID
                "base_ref": {"type": "string"},  # 可选的基础引用（默认HEAD）
            },
            "required": ["name"],  # 必需参数：名称
        },
    },
    {
        "name": "worktree_list",  # 工作树列表工具
        "description": "List worktrees tracked in .worktrees/index.json.",  # 列出.worktrees/index.json中跟踪的工作树
        "input_schema": {"type": "object", "properties": {}},  # 无输入参数
    },
    {
        "name": "worktree_status",  # 工作树状态工具
        "description": "Show git status for one worktree.",  # 显示一个工作树的Git状态
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},  # 工作树名称
            "required": ["name"],  # 必需参数：名称
        },
    },
    {
        "name": "worktree_run",  # 工作树运行工具
        "description": "Run a shell command in a named worktree directory.",  # 在命名的工作树目录中运行shell命令
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},  # 工作树名称
                "command": {"type": "string"},  # 要运行的命令
            },
            "required": ["name", "command"],  # 必需参数：名称和命令
        },
    },
    {
        "name": "worktree_remove",  # 工作树删除工具
        "description": "Remove a worktree and optionally mark its bound task completed.",  # 删除工作树并可选标记其绑定任务为已完成
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},  # 工作树名称
                "force": {"type": "boolean"},  # 可选的强制删除标志
                "complete_task": {"type": "boolean"},  # 可选的完成任务标志
            },
            "required": ["name"],  # 必需参数：名称
        },
    },
    {
        "name": "worktree_keep",  # 工作树保留工具
        "description": "Mark a worktree as kept in lifecycle state without removing it.",  # 将工作树标记为生命周期中的保留状态而不删除它
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},  # 工作树名称
            "required": ["name"],  # 必需参数：名称
        },
    },
    {
        "name": "worktree_events",  # 工作树事件工具
        "description": "List recent worktree/task lifecycle events from .worktrees/events.jsonl.",  # 列出.worktrees/events.jsonl中的最近工作树/任务生命周期事件
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer"}},  # 可选的限制数量
        },
    },
]


def agent_loop(messages: list):
    # 代理主循环函数，实现与Claude API的交互和工具调用处理
    # 这个循环持续进行，直到AI决定停止（没有更多工具调用）
    # 这一章可以把它记成一句顺口话：
    # “模型先想，想完选工具；程序去执行；结果再喂回模型继续想。”
    while True:
        # 调用Claude API进行推理和决策
        response = client.messages.create(
            model=MODEL,  # 使用指定的模型
            system=SYSTEM,  # 系统提示信息
            messages=messages,  # 对话消息历史
            tools=TOOLS,  # 可用工具列表
            max_tokens=8000,  # 最大token数
        )
        # 将AI回复添加到消息历史
        messages.append({"role": "assistant", "content": response.content})
        # 如果不是工具调用，则结束循环
        if response.stop_reason != "tool_use":
            return  # 退出循环

        results = []  # 存储工具调用结果
        for block in response.content:  # 遍历响应内容块
            if block.type == "tool_use":  # 如果是工具使用块
                # 只要模型决定用工具，
                # 这一层就负责把“想法”变成“真正动作”。
                handler = TOOL_HANDLERS.get(block.name)  # 获取对应的工具处理器
                try:
                    # 执行工具调用，传入参数
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as e:  # 捕获执行异常
                    output = f"Error: {e}"  # 格式化错误消息
                # 打印工具执行结果（截断到200字符用于调试）
                print(f"> {block.name}: {str(output)[:200]}")
                # 构建工具结果对象
                results.append(
                    {
                        "type": "tool_result",  # 结果类型
                        "tool_use_id": block.id,  # 工具使用ID
                        "content": str(output),  # 结果内容
                    }
                )
        # 将工具结果作为用户消息添加到对话历史
        messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    # 主程序入口，提供交互式命令行界面来测试工作树和任务隔离系统
    # 这一段像“练习场入口”。
    # 你在终端里输入一句话，
    # 模型就会决定要不要创建任务、创建 worktree、在工位里执行命令。
    print(f"Repo root for s12: {REPO_ROOT}")  # 打印检测到的仓库根目录
    if not WORKTREES.git_available:  # 如果Git不可用
        print("Note: Not in a git repo. worktree_* tools will return errors.")  # 提示工作树工具会出错

    history = []  # 初始化对话历史列表
    while True:  # 主交互循环
        try:
            # 显示彩色提示符并等待用户输入
            query = input("\033[36ms12 >> \033[0m")
        except (EOFError, KeyboardInterrupt):  # 处理Ctrl+D或Ctrl+C
            break  # 退出循环
        # 检查退出命令（q、exit或空行）
        if query.strip().lower() in ("q", "exit", ""):
            break  # 退出循环
        # 将用户查询添加到对话历史
        history.append({"role": "user", "content": query})
        # 调用代理循环处理查询
        agent_loop(history)
        # 获取最后的响应内容
        response_content = history[-1]["content"]
        if isinstance(response_content, list):  # 如果响应是列表（工具结果）
            for block in response_content:  # 遍历结果块
                if hasattr(block, "text"):  # 如果块有文本属性
                    print(block.text)  # 打印文本内容
        print()  # 打印空行分隔输出
