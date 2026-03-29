#!/usr/bin/env python3
# 工具：自主性 -- 模型主动寻找工作，无需外部告知。
"""
s11_autonomous_agents.py - 自主代理

这一章想教我们的核心想法只有一句话：
以前是“领导一直分配工作”，这一章变成“队友自己也会找工作”。

你可以把整个系统想成一个小办公室：
1. `.team/inbox/` 是每个人的信箱。
2. `.tasks/` 是贴任务卡片的任务墙。
3. `lead` 是老师或队长。
4. `teammate` 是会自己干活的小助手。

这一章最重要的 4 个新能力：
1. 队友没活干时，不是立刻消失，而是先进入“空闲等待”。
2. 空闲时会定期去看信箱，有没有人给自己发新消息。
3. 空闲时也会去看任务墙，有没有还没人认领的新任务。
4. 如果聊天记录被压缩得太短，它会重新提醒自己“我是谁、我属于哪个团队”。

把生命周期想成下面这样：

    队友生命周期：
    +-------+
    | 生成 |
    +---+---+
        |
        v
    +-------+  工具使用    +-------+
    | 工作  | <----------- |  LLM  |
    +---+---+              +-------+
        |
        | 停止原因 != 工具使用
        v
    +--------+
    | 空闲   | 每5秒轮询，最多60秒
    +---+----+
        |
        +---> 检查收件箱 -> 有消息？ -> 恢复工作
        |
        +---> 扫描.tasks/ -> 未认领？ -> 认领 -> 恢复工作
        |
        +---> 超时(60秒) -> 关闭

阅读这份代码时，可以重点盯住 5 个地方：
1. `MessageBus`：大家怎么互相传话。
2. `scan_unclaimed_tasks / claim_task`：大家怎么从任务墙领任务。
3. `TeammateManager._loop`：队友怎么在“工作”和“空闲”之间切换。
4. `make_identity_block`：记忆变短后，怎样提醒模型自己的身份。
5. `agent_loop`：领导者自己又是怎么调用工具的。

关键洞察：
"真正更自主的代理，不是一直等命令，而是会在合适的时候自己去找下一件事。"
"""

# 先看导入：
# 这里没有“神秘魔法”，只是把后面要用到的小工具箱拿进来。
# 你可以先记住一个原则：
# “import 谁，就表示后面要借用谁的本领。”
# 标准库导入，用于文件操作、JSON处理和系统交互
import json  # 用于解析和生成JSON数据结构
import os    # 用于操作系统接口和路径操作
import subprocess  # 用于运行外部shell命令
import threading   # 用于并发执行队友代理
import time        # 用于时间操作和轮询间隔
import uuid        # 用于生成唯一请求标识符

# 第三方导入，用于路径处理和AI交互
from pathlib import Path  # 用于面向对象的文件系统路径
from anthropic import Anthropic  # 用于与Anthropic的Claude API交互
from dotenv import load_dotenv  # 用于从.env文件加载环境变量

# 从.env文件加载环境变量，覆盖现有变量
load_dotenv(override=True)
# 如果使用自定义基础URL，移除认证令牌（用于本地API服务器）
if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

# 从这里开始是“全局设置区”。
# 可以把它理解成：在游戏开局前，先把地图、玩家、规则都摆好。
# 设置工作目录为当前目录
WORKDIR = Path.cwd()
# 使用可选的自定义基础URL初始化Anthropic客户端
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
# 从环境变量获取模型ID
MODEL = os.environ["MODEL_ID"]
# 定义团队目录，用于持久化团队状态
TEAM_DIR = WORKDIR / ".team"
# 定义收件箱目录，用于消息传递
INBOX_DIR = TEAM_DIR / "inbox"
# 定义任务目录，用于任务板持久化
TASKS_DIR = WORKDIR / ".tasks"

# 轮询间隔（秒），空闲代理检查新任务的频率
POLL_INTERVAL = 5
# 空闲超时（秒），代理在关闭前等待的最大时间
IDLE_TIMEOUT = 60

# 领导代理的系统提示
SYSTEM = f"You are a team lead at {WORKDIR}. Teammates are autonomous -- they find work themselves."

# 消息类型就像“信件分类标签”。
# 程序看到不同标签，就知道这封信是普通聊天、广播通知，
# 还是“请准备关机”“这是计划审批回复”。
# 有效的消息类型，用于团队通信
VALID_MSG_TYPES = {
    "message",           # 普通消息
    "broadcast",         # 广播消息
    "shutdown_request",  # 关闭请求
    "shutdown_response", # 关闭响应
    "plan_approval_response", # 计划批准响应
}

# -- 请求跟踪器 --
# 这里的两个字典像“登记本”。
# 因为请求发出去以后，不一定马上收到回复，
# 所以我们要把 request_id 记下来，之后才能查“那件事处理到哪一步了”。
# 字典，按请求ID跟踪关闭请求
shutdown_requests = {}
# 字典，按请求ID跟踪计划批准请求
plan_requests = {}
# 线程锁，用于安全访问关闭请求跟踪器
_tracker_lock = threading.Lock()
# 线程锁，用于安全执行任务认领操作
_claim_lock = threading.Lock()


# -- MessageBus: 每个队友的JSONL收件箱 --
class MessageBus:
    """
    处理代理间通信，通过JSONL文件实现消息持久化。

    小朋友版理解：
    这就是“班级信箱管理员”。
    每个人都有一个自己的信箱文件。
    谁要传话，就把一条 JSON 消息塞进对方的信箱。

    这里故意不用复杂数据库，而是用文件来做，
    因为这样很容易看见系统到底存了什么。
    """
    def __init__(self, inbox_dir: Path):
        """使用收件箱目录初始化消息总线。"""
        self.dir = inbox_dir
        self.dir.mkdir(parents=True, exist_ok=True)  # 确保收件箱目录存在

    def send(self, sender: str, to: str, content: str,
             msg_type: str = "message", extra: dict = None) -> str:
        """向特定队友的收件箱发送消息。"""
        # 第一步：先检查消息标签是不是合法的。
        # 验证消息类型是否有效
        if msg_type not in VALID_MSG_TYPES:
            return f"Error: Invalid type '{msg_type}'. Valid: {VALID_MSG_TYPES}"
        # 创建包含元数据的消息结构
        msg = {
            "type": msg_type,
            "from": sender,
            "content": content,
            "timestamp": time.time(),  # 添加时间戳
        }
        # 如果提供了额外字段，则添加进去
        if extra:
            msg.update(extra)
        # JSONL 的意思是：
        # 一行放一条 JSON。
        # 这样追加消息很方便，不用每次都重写整个大文件。
        # 将消息追加到接收者的JSONL收件箱文件
        inbox_path = self.dir / f"{to}.jsonl"
        with open(inbox_path, "a") as f:
            f.write(json.dumps(msg) + "\n")
        return f"Sent {msg_type} to {to}"

    def read_inbox(self, name: str) -> list:
        """读取并清空队友收件箱中的所有消息。"""
        inbox_path = self.dir / f"{name}.jsonl"
        # 如果收件箱不存在，返回空列表
        if not inbox_path.exists():
            return []
        # 读信箱时，这里采用的是“拿走全部信件”的规则：
        # 先把所有行读出来，再把文件清空。
        # 所以这个操作常常也叫 drain（排空）。
        # 解析所有JSONL行到消息对象列表
        messages = []
        for line in inbox_path.read_text().strip().splitlines():
            if line:  # 跳过空行
                messages.append(json.loads(line))
        # 读取后清空收件箱（清空操作）
        inbox_path.write_text("")
        return messages

    def broadcast(self, sender: str, content: str, teammates: list) -> str:
        """向所有指定的队友广播消息（除了发送者自己）。"""
        count = 0  # 记录成功发送的消息数量
        for name in teammates:
            if name != sender:  # 不给自己发送广播消息
                self.send(sender, name, content, "broadcast")  # 发送广播消息
                count += 1  # 计数器加1
        return f"Broadcast to {count} teammates"  # 返回广播结果


# 创建全局消息总线实例，用于团队间通信
BUS = MessageBus(INBOX_DIR)


# -- 任务板扫描 --
def scan_unclaimed_tasks() -> list:
    """扫描并返回所有未认领任务的列表。"""
    # `.tasks/` 可以想成办公室门口的任务墙。
    # 每个 `task_*.json` 文件就是一张任务卡片。
    TASKS_DIR.mkdir(exist_ok=True)  # 确保任务目录存在
    unclaimed = []  # 存储未认领任务的列表
    # 遍历所有任务文件，按文件名排序
    for f in sorted(TASKS_DIR.glob("task_*.json")):
        task = json.loads(f.read_text())  # 读取任务数据
        # 一张任务卡片要满足 3 个条件，才算“现在能接”：
        # 1. status == pending，说明还没开始
        # 2. owner 为空，说明还没人接
        # 3. blockedBy 为空，说明没有前置任务卡住它
        # 检查任务是否未认领：状态为pending，无所有者，无阻塞依赖
        if (task.get("status") == "pending"
                and not task.get("owner")
                and not task.get("blockedBy")):
            unclaimed.append(task)  # 添加到未认领任务列表
    return unclaimed  # 返回未认领任务列表


def claim_task(task_id: int, owner: str) -> str:
    """认领指定ID的任务，将其分配给指定所有者。"""
    # 为什么这里要加锁？
    # 因为可能有两个队友几乎同一时间都看到了同一张任务卡。
    # 如果不加锁，就可能发生“大家都以为是自己领到了”的抢单问题。
    with _claim_lock:  # 使用锁确保线程安全，避免竞态条件
        path = TASKS_DIR / f"task_{task_id}.json"  # 构建任务文件路径
        if not path.exists():  # 检查任务文件是否存在
            return f"Error: Task {task_id} not found"  # 返回未找到错误
        task = json.loads(path.read_text())  # 读取当前任务数据
        task["owner"] = owner  # 设置任务所有者
        task["status"] = "in_progress"  # 更新任务状态为进行中
        path.write_text(json.dumps(task, indent=2))  # 保存更新后的任务数据
    return f"Claimed task #{task_id} for {owner}"  # 返回认领成功消息


# -- 压缩后的身份重新注入 --
def make_identity_block(name: str, role: str, team_name: str) -> dict:
    """创建身份块，用于在上下文压缩后重新建立代理身份。"""
    # 这段很重要。
    # 大模型聊天太久时，前面的历史可能会被压缩或裁掉。
    # 如果“你是谁”这件事被忘了，模型就可能跑偏。
    # 所以我们会补一张身份卡：
    # “你叫谁、角色是什么、属于哪个团队，请继续工作。”
    return {
        "role": "user",
        "content": f"<identity>You are '{name}', role: {role}, team: {team_name}. Continue your work.</identity>",
    }


# -- 自主队友管理器 --
class TeammateManager:
    """
    管理自主代理队友的生命周期、配置和线程。

    如果把整个系统想成一个班级，
    这个类就像“班主任的后台管理器”：
    负责记住班上有哪些同学、他们现在在干嘛，
    以及帮他们启动工作线程。
    """
    def __init__(self, team_dir: Path):
        """初始化队友管理器，设置团队目录和配置。"""
        self.dir = team_dir
        self.dir.mkdir(parents=True, exist_ok=True)  # 确保团队目录存在
        self.config_path = self.dir / "config.json"  # 团队配置文件路径
        self.config = self._load_config()  # 加载团队配置
        self.threads = {}  # 存储运行中的队友线程

    def _load_config(self) -> dict:
        """从配置文件加载团队配置，如果不存在则创建默认配置。"""
        if self.config_path.exists():  # 检查配置文件是否存在
            return json.loads(self.config_path.read_text())  # 读取并解析JSON配置
        return {"team_name": "default", "members": []}  # 返回默认配置

    def _save_config(self):
        """保存当前团队配置到文件。"""
        self.config_path.write_text(json.dumps(self.config, indent=2))  # 以格式化的JSON保存

    def _find_member(self, name: str) -> dict:
        """根据名称查找队友成员信息。"""
        for m in self.config["members"]:  # 遍历所有成员
            if m["name"] == name:  # 找到匹配的成员
                return m  # 返回成员信息字典
        return None  # 未找到返回None

    def _set_status(self, name: str, status: str):
        """更新指定队友的状态并保存配置。"""
        member = self._find_member(name)  # 查找成员
        if member:  # 如果成员存在
            member["status"] = status  # 更新状态
            self._save_config()  # 保存配置到文件

    def spawn(self, name: str, role: str, prompt: str) -> str:
        """生成或重启一个自主队友代理。"""
        # spawn 的意思就是“生出一个新执行单元”。
        # 这里不是复制一个真人，而是开启一个后台线程，
        # 让这个名字对应的队友开始独立跑自己的循环。
        member = self._find_member(name)  # 查找现有成员
        if member:  # 如果成员已存在
            if member["status"] not in ("idle", "shutdown"):  # 检查状态是否允许重启
                return f"Error: '{name}' is currently {member['status']}"  # 返回错误
            member["status"] = "working"  # 更新状态为工作
            member["role"] = role  # 更新角色
        else:  # 如果是新成员
            member = {"name": name, "role": role, "status": "working"}  # 创建新成员
            self.config["members"].append(member)  # 添加到成员列表
        self._save_config()  # 保存配置
        # 创建后台线程运行队友循环
        thread = threading.Thread(
            target=self._loop,
            args=(name, role, prompt),
            daemon=True,  # 设置为守护线程，随主线程退出
        )
        self.threads[name] = thread  # 存储线程引用
        thread.start()  # 启动线程
        return f"Spawned '{name}' (role: {role})"  # 返回生成成功消息

    def _loop(self, name: str, role: str, prompt: str):
        """队友代理的主循环，实现工作阶段和空闲轮询阶段。"""
        team_name = self.config["team_name"]  # 获取团队名称
        # 构建系统提示，定义代理的身份和行为
        sys_prompt = (
            f"You are '{name}', role: {role}, team: {team_name}, at {WORKDIR}. "
            f"Use idle tool when you have no more work. You will auto-claim new tasks."
        )
        messages = [{"role": "user", "content": prompt}]  # 初始化消息历史
        tools = self._teammate_tools()  # 获取可用的工具列表

        while True:  # 主循环，持续运行直到关闭
            # 可以把整个 while True 想成“值班循环”：
            # 做一会儿事 -> 没事了就去巡逻 -> 有新情况再回来做事。

            # -- 工作阶段：标准代理循环 --
            # 工作阶段像“坐在桌前认真干活”。
            # 只要模型还在主动调用工具，就说明它还知道下一步要做什么。
            for _ in range(50):  # 最多50轮对话，避免无限循环
                inbox = BUS.read_inbox(name)  # 读取收件箱消息
                for msg in inbox:  # 处理每条消息
                    if msg.get("type") == "shutdown_request":  # 如果是关闭请求
                        self._set_status(name, "shutdown")  # 设置状态为关闭
                        return  # 退出循环
                    # 外部消息会被塞回对话历史里，
                    # 这样模型下一次思考时就能“看见”刚收到的内容。
                    messages.append({"role": "user", "content": json.dumps(msg)})  # 添加消息到历史
                try:  # 尝试调用AI模型
                    response = client.messages.create(
                        model=MODEL,
                        system=sys_prompt,
                        messages=messages,
                        tools=tools,
                        max_tokens=8000,
                    )
                except Exception:  # 如果调用失败
                    self._set_status(name, "idle")  # 设置为空闲状态
                    return  # 退出循环
                messages.append({"role": "assistant", "content": response.content})  # 添加AI响应到历史
                if response.stop_reason != "tool_use":  # 如果不是工具使用，结束工作阶段
                    # 走到这里，说明模型这轮没有继续要求工具。
                    # 它可能是回答完了，也可能是不知道下一步了。
                    # 这时我们先离开“工作阶段”。
                    break
                results = []  # 存储工具执行结果
                idle_requested = False  # 标记是否请求空闲
                for block in response.content:  # 处理响应中的每个块
                    if block.type == "tool_use":  # 如果是工具使用
                        if block.name == "idle":  # 如果是空闲工具
                            # `idle` 不是“彻底结束”，而是“我现在没事，先去门口看看有没有新任务”。
                            idle_requested = True  # 标记请求空闲
                            output = "Entering idle phase. Will poll for new tasks."  # 空闲提示
                        else:  # 其他工具
                            output = self._exec(name, block.name, block.input)  # 执行工具
                        print(f"  [{name}] {block.name}: {str(output)[:120]}")  # 打印执行结果（截断）
                        results.append({  # 添加结果到列表
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(output),
                        })
                messages.append({"role": "user", "content": results})  # 添加工具结果到消息历史
                if idle_requested:  # 如果请求了空闲，跳出工作循环
                    break

            # -- 空闲阶段：轮询收件箱消息和未认领任务 --
            # 空闲阶段像“离开工位去巡逻”。
            # 注意：空闲 != 死掉。
            # 它只是先暂停重度思考，每隔几秒检查一下周围有没有新情况。
            self._set_status(name, "idle")  # 设置状态为空闲
            resume = False  # 标记是否需要恢复工作
            polls = IDLE_TIMEOUT // max(POLL_INTERVAL, 1)  # 计算轮询次数
            for _ in range(polls):  # 在超时前持续轮询
                time.sleep(POLL_INTERVAL)  # 等待轮询间隔
                inbox = BUS.read_inbox(name)  # 检查收件箱
                if inbox:  # 如果有新消息
                    # 只要有人来信了，就说明有新上下文，应该回到工作阶段。
                    for msg in inbox:  # 处理每条消息
                        if msg.get("type") == "shutdown_request":  # 如果是关闭请求
                            self._set_status(name, "shutdown")  # 设置为关闭状态
                            return  # 退出循环
                        messages.append({"role": "user", "content": json.dumps(msg)})  # 添加消息到历史
                    resume = True  # 标记需要恢复工作
                    break  # 跳出轮询循环
                unclaimed = scan_unclaimed_tasks()  # 扫描未认领任务
                if unclaimed:  # 如果有未认领任务
                    # 自主性的关键就在这里：
                    # 没人点名分配，它也会自己去任务墙看，并主动接活。
                    task = unclaimed[0]  # 取第一个任务
                    claim_task(task["id"], name)  # 认领任务
                    # 构建自动认领的任务提示
                    task_prompt = (
                        f"<auto-claimed>Task #{task['id']}: {task['subject']}\n"
                        f"{task.get('description', '')}</auto-claimed>"
                    )
                    # 如果消息历史较短，重新注入身份（防止压缩后丢失身份）
                    if len(messages) <= 3:
                        # 为什么“历史很短”时要补身份？
                        # 因为上下文太短时，模型可能已经看不到前面那句“你是某某角色”了。
                        # 所以重新塞一张身份卡，帮助它继续扮演同一个队友。
                        messages.insert(0, make_identity_block(name, role, team_name))  # 插入身份块
                        messages.insert(1, {"role": "assistant", "content": f"I am {name}. Continuing."})  # 插入确认消息
                    messages.append({"role": "user", "content": task_prompt})  # 添加任务提示
                    messages.append({"role": "assistant", "content": f"Claimed task #{task['id']}. Working on it."})  # 添加认领确认
                    resume = True  # 标记需要恢复工作
                    break  # 跳出轮询循环

            if not resume:  # 如果没有恢复工作（超时）
                # 长时间没有新消息，也没有新任务，就礼貌地下线。
                self._set_status(name, "shutdown")  # 设置为关闭状态
                return  # 退出主循环
            self._set_status(name, "working")  # 设置为工作状态

    def _exec(self, sender: str, tool_name: str, args: dict) -> str:
        """执行队友可用的工具命令。"""
        # 这里像“工具总控台”。
        # 模型只会说：“我想用 read_file” 或 “我想用 bash”。
        # 真正把这个请求翻译成 Python 函数执行的，是这一层。
        # 这些基础工具与s02保持不变
        if tool_name == "bash":  # 执行shell命令
            return _run_bash(args["command"])
        if tool_name == "read_file":  # 读取文件内容
            return _run_read(args["path"])
        if tool_name == "write_file":  # 写入文件内容
            return _run_write(args["path"], args["content"])
        if tool_name == "edit_file":  # 编辑文件内容
            return _run_edit(args["path"], args["old_text"], args["new_text"])
        if tool_name == "send_message":  # 发送消息给队友
            return BUS.send(sender, args["to"], args["content"], args.get("msg_type", "message"))
        if tool_name == "read_inbox":  # 读取并清空收件箱
            return json.dumps(BUS.read_inbox(sender), indent=2)
        if tool_name == "shutdown_response":  # 响应关闭请求
            req_id = args["request_id"]
            with _tracker_lock:  # 线程安全更新请求状态
                if req_id in shutdown_requests:
                    shutdown_requests[req_id]["status"] = "approved" if args["approve"] else "rejected"
            BUS.send(  # 发送响应消息给领导
                sender, "lead", args.get("reason", ""),
                "shutdown_response", {"request_id": req_id, "approve": args["approve"]},
            )
            return f"Shutdown {'approved' if args['approve'] else 'rejected'}"  # 返回批准结果
        if tool_name == "plan_approval":  # 提交计划等待批准
            plan_text = args.get("plan", "")
            req_id = str(uuid.uuid4())[:8]  # 生成唯一请求ID
            with _tracker_lock:  # 线程安全存储计划请求
                plan_requests[req_id] = {"from": sender, "plan": plan_text, "status": "pending"}
            BUS.send(  # 发送计划批准请求给领导
                sender, "lead", plan_text, "plan_approval_response",
                {"request_id": req_id, "plan": plan_text},
            )
            return f"Plan submitted (request_id={req_id}). Waiting for approval."  # 返回提交确认
        if tool_name == "claim_task":  # 认领任务
            return claim_task(args["task_id"], sender)
        return f"Unknown tool: {tool_name}"  # 未知工具

    def _teammate_tools(self) -> list:
        """返回队友代理可用的工具列表。"""
        # 这个列表可以理解成“发给模型看的工具菜单”。
        # 模型不能随便凭空调用函数，
        # 只能从这里声明过的工具里挑。
        # 这些基础工具与s02保持不变
        return [
            {"name": "bash", "description": "Run a shell command.",
             "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
            {"name": "read_file", "description": "Read file contents.",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
            {"name": "write_file", "description": "Write content to file.",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
            {"name": "edit_file", "description": "Replace exact text in file.",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
            {"name": "send_message", "description": "Send message to a teammate.",
             "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "content": {"type": "string"}, "msg_type": {"type": "string", "enum": list(VALID_MSG_TYPES)}}, "required": ["to", "content"]}},
            {"name": "read_inbox", "description": "Read and drain your inbox.",
             "input_schema": {"type": "object", "properties": {}}},
            {"name": "shutdown_response", "description": "Respond to a shutdown request.",
             "input_schema": {"type": "object", "properties": {"request_id": {"type": "string"}, "approve": {"type": "boolean"}, "reason": {"type": "string"}}, "required": ["request_id", "approve"]}},
            {"name": "plan_approval", "description": "Submit a plan for lead approval.",
             "input_schema": {"type": "object", "properties": {"plan": {"type": "string"}}, "required": ["plan"]}},
            {"name": "idle", "description": "Signal that you have no more work. Enters idle polling phase.",
             "input_schema": {"type": "object", "properties": {}}},
            {"name": "claim_task", "description": "Claim a task from the task board by ID.",
             "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]}},
        ]

    def list_all(self) -> str:
        """列出所有队友及其状态。"""
        if not self.config["members"]:  # 如果没有成员
            return "No teammates."  # 返回无队友消息
        lines = [f"Team: {self.config['team_name']}"]  # 团队名称
        for m in self.config["members"]:  # 遍历每个成员
            lines.append(f"  {m['name']} ({m['role']}): {m['status']}")  # 成员信息
        return "\n".join(lines)  # 返回格式化的字符串

    def member_names(self) -> list:
        """返回所有成员名称的列表。"""
        return [m["name"] for m in self.config["members"]]  # 提取成员名称


# 创建全局队友管理器实例
TEAM = TeammateManager(TEAM_DIR)


# -- 基础工具实现（这些基础工具与s02保持不变）--
def _safe_path(p: str) -> Path:
    """确保路径在工作目录内，防止路径遍历攻击。"""
    # 安全课：
    # 如果别人传来一个奇怪路径，比如 `../../系统文件`，
    # 程序就可能跑出当前项目目录，去读不该读的地方。
    # 所以这里强制要求：路径最终必须仍然落在 WORKDIR 里面。
    path = (WORKDIR / p).resolve()  # 解析绝对路径
    if not path.is_relative_to(WORKDIR):  # 检查是否在工作目录内
        raise ValueError(f"Path escapes workspace: {p}")  # 抛出安全错误
    return path  # 返回安全路径


def _run_bash(command: str) -> str:
    """安全执行shell命令，阻止危险操作。"""
    # 让模型执行 shell 很强大，但也很危险。
    # 所以我们至少先挡住几种特别危险的命令。
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot"]  # 危险命令列表
    if any(d in command for d in dangerous):  # 检查是否包含危险命令
        return "Error: Dangerous command blocked"  # 阻止执行
    try:  # 尝试执行命令
        r = subprocess.run(
            command, shell=True, cwd=WORKDIR,  # 在工作目录执行
            capture_output=True, text=True, timeout=120,  # 捕获输出，设置超时
        )
        out = (r.stdout + r.stderr).strip()  # 合并标准输出和错误输出
        return out[:50000] if out else "(no output)"  # 返回输出（限制长度）
    except subprocess.TimeoutExpired:  # 超时异常
        return "Error: Timeout (120s)"  # 返回超时错误


def _run_read(path: str, limit: int = None) -> str:
    """安全读取文件内容，支持行数限制。"""
    try:
        lines = _safe_path(path).read_text().splitlines()  # 读取文件并分割为行
        if limit and limit < len(lines):  # 如果设置了限制且超过限制
            # `limit` 的用途是：
            # 文件太长时，只先给模型看前面一部分，避免一次喂太多内容。
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]  # 添加省略提示
        return "\n".join(lines)[:50000]  # 合并行并限制总长度
    except Exception as e:  # 捕获异常
        return f"Error: {e}"  # 返回错误信息


def _run_write(path: str, content: str) -> str:
    """安全写入内容到文件，自动创建父目录。"""
    try:
        fp = _safe_path(path)  # 获取安全路径
        fp.parent.mkdir(parents=True, exist_ok=True)  # 创建父目录
        fp.write_text(content)  # 写入内容
        return f"Wrote {len(content)} bytes"  # 返回写入的字节数
    except Exception as e:  # 捕获异常
        return f"Error: {e}"  # 返回错误信息


def _run_edit(path: str, old_text: str, new_text: str) -> str:
    """安全编辑文件，用新文本替换旧文本。"""
    try:
        fp = _safe_path(path)  # 获取安全路径
        c = fp.read_text()  # 读取文件内容
        if old_text not in c:  # 检查旧文本是否存在
            # 这里要求“精确匹配旧文本”是故意的。
            # 这样模型不会稀里糊涂改错地方。
            return f"Error: Text not found in {path}"  # 返回未找到错误
        fp.write_text(c.replace(old_text, new_text, 1))  # 替换第一次出现的旧文本
        return f"Edited {path}"  # 返回成功消息
    except Exception as e:  # 捕获异常
        return f"Error: {e}"  # 返回错误信息


# -- 领导特定的协议处理函数 --
def handle_shutdown_request(teammate: str) -> str:
    """向指定队友发送关闭请求。"""
    req_id = str(uuid.uuid4())[:8]  # 生成唯一请求ID
    with _tracker_lock:  # 线程安全存储请求
        shutdown_requests[req_id] = {"target": teammate, "status": "pending"}
    BUS.send(  # 发送关闭请求消息
        "lead", teammate, "Please shut down gracefully.",
        "shutdown_request", {"request_id": req_id},
    )
    return f"Shutdown request {req_id} sent to '{teammate}'"  # 返回请求ID


def handle_plan_review(request_id: str, approve: bool, feedback: str = "") -> str:
    """批准或拒绝队友的计划。"""
    with _tracker_lock:  # 线程安全访问计划请求
        req = plan_requests.get(request_id)  # 获取请求信息
    if not req:  # 如果请求不存在
        return f"Error: Unknown plan request_id '{request_id}'"  # 返回错误
    with _tracker_lock:  # 线程安全更新状态
        req["status"] = "approved" if approve else "rejected"  # 设置批准状态
    BUS.send(  # 发送计划批准响应
        "lead", req["from"], feedback, "plan_approval_response",
        {"request_id": request_id, "approve": approve, "feedback": feedback},
    )
    return f"Plan {req['status']} for '{req['from']}'"  # 返回处理结果


def _check_shutdown_status(request_id: str) -> str:
    """检查关闭请求的状态。"""
    with _tracker_lock:  # 线程安全访问
        return json.dumps(shutdown_requests.get(request_id, {"error": "not found"}))


# -- Lead tool dispatch (14 tools) --
# 领导者工具调度器（14个工具）
# 这张表就是“领导者版本的工具遥控器”。
# 左边是工具名，右边是实际要调用的 Python 行为。
# 当模型说“我要用 spawn_teammate”时，程序就到这里找对应处理函数。
TOOL_HANDLERS = {
    "bash":              lambda **kw: _run_bash(kw["command"]),  # 执行bash命令
    "read_file":         lambda **kw: _run_read(kw["path"], kw.get("limit")),  # 读取文件内容，可选限制行数
    "write_file":        lambda **kw: _run_write(kw["path"], kw["content"]),  # 写入文件内容
    "edit_file":         lambda **kw: _run_edit(kw["path"], kw["old_text"], kw["new_text"]),  # 编辑文件，替换文本
    "spawn_teammate":    lambda **kw: TEAM.spawn(kw["name"], kw["role"], kw["prompt"]),  # 生成新的队友代理
    "list_teammates":    lambda **kw: TEAM.list_all(),  # 列出所有队友
    "send_message":      lambda **kw: BUS.send("lead", kw["to"], kw["content"], kw.get("msg_type", "message")),  # 发送消息给指定队友
    "read_inbox":        lambda **kw: json.dumps(BUS.read_inbox("lead"), indent=2),  # 读取并清空领导者的收件箱
    "broadcast":         lambda **kw: BUS.broadcast("lead", kw["content"], TEAM.member_names()),  # 广播消息给所有队友
    "shutdown_request":  lambda **kw: handle_shutdown_request(kw["teammate"]),  # 请求关闭指定队友
    "shutdown_response": lambda **kw: _check_shutdown_status(kw.get("request_id", "")),  # 检查关闭请求状态
    "plan_approval":     lambda **kw: handle_plan_review(kw["request_id"], kw["approve"], kw.get("feedback", "")),  # 批准或拒绝队友计划
    "idle":              lambda **kw: "Lead does not idle.",  # 领导者不进入空闲状态
    "claim_task":        lambda **kw: claim_task(kw["task_id"], "lead"),  # 领导者认领指定任务
}

# `TOOLS` 是另一张很关键的表。
# `TOOL_HANDLERS` 给 Python 看，告诉程序“怎么执行”。
# `TOOLS` 给模型看，告诉模型“你能用什么、参数要长什么样”。
# 这是一种常见的设计：同一个工具系统，分成“声明”和“执行”两层。
TOOLS = [
    {"name": "bash", "description": "Run a shell command.",  # 运行shell命令
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",  # 读取文件内容
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to file.",  # 写入文件内容
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in file.",  # 在文件中替换确切文本
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
    {"name": "spawn_teammate", "description": "Spawn an autonomous teammate.",  # 生成自主队友
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "role": {"type": "string"}, "prompt": {"type": "string"}}, "required": ["name", "role", "prompt"]}},
    {"name": "list_teammates", "description": "List all teammates.",  # 列出所有队友
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "send_message", "description": "Send a message to a teammate.",  # 发送消息给队友
     "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "content": {"type": "string"}, "msg_type": {"type": "string", "enum": list(VALID_MSG_TYPES)}}, "required": ["to", "content"]}},
    {"name": "read_inbox", "description": "Read and drain the lead's inbox.",  # 读取并清空领导者收件箱
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "broadcast", "description": "Send a message to all teammates.",  # 广播消息给所有队友
     "input_schema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},
    {"name": "shutdown_request", "description": "Request a teammate to shut down.",  # 请求关闭队友
     "input_schema": {"type": "object", "properties": {"teammate": {"type": "string"}}, "required": ["teammate"]}},
    {"name": "shutdown_response", "description": "Check shutdown request status.",  # 检查关闭请求状态
     "input_schema": {"type": "object", "properties": {"request_id": {"type": "string"}}, "required": ["request_id"]}},
    {"name": "plan_approval", "description": "Approve or reject a teammate's plan.",  # 批准或拒绝队友计划
     "input_schema": {"type": "object", "properties": {"request_id": {"type": "string"}, "approve": {"type": "boolean"}, "feedback": {"type": "string"}}, "required": ["request_id", "approve"]}},
    {"name": "idle", "description": "Enter idle state (for lead -- rarely used).",  # 进入空闲状态（领导者很少使用）
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "claim_task", "description": "Claim a task from the board by ID.",  # 通过ID认领任务板上的任务
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]}},
]


def agent_loop(messages: list):
    # 这是领导者的大脑循环。
    # 你可以用一句顺口溜记住它：
    # “先收信，再思考；要用工具就去做；做完把结果送回去，再继续想。”
    while True:
        # 检查领导者的收件箱是否有新消息
        inbox = BUS.read_inbox("lead")
        if inbox:
            # 如果有消息，将其添加到对话历史中
            messages.append({
                "role": "user",
                "content": f"<inbox>{json.dumps(inbox, indent=2)}</inbox>",
            })
            messages.append({
                "role": "assistant",
                "content": "Noted inbox messages.",  # 确认收到消息
            })
        # 调用Claude API进行推理
        response = client.messages.create(
            model=MODEL,  # 使用指定的模型
            system=SYSTEM,  # 系统提示
            messages=messages,  # 对话历史
            tools=TOOLS,  # 可用工具列表
            max_tokens=8000,  # 最大token数
        )
        # 将助手回复添加到对话历史
        messages.append({"role": "assistant", "content": response.content})
        # 如果不是工具调用，则结束循环
        if response.stop_reason != "tool_use":
            # 这里结束，表示模型这轮已经不想再调工具了，
            # 往往意味着它准备把答案停在这里。
            return
        # 处理工具调用结果
        results = []
        for block in response.content:
            if block.type == "tool_use":
                # 获取对应的工具处理器
                handler = TOOL_HANDLERS.get(block.name)
                try:
                    # 执行工具调用
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as e:
                    # 处理执行错误
                    output = f"Error: {e}"
                # 打印日志是为了让人类开发者能看见“模型刚刚做了什么”。
                # 这对调试代理系统特别重要。
                # 打印工具执行结果（截断到200字符）
                print(f"> {block.name}: {str(output)[:200]}")
                # 构建工具结果
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(output),
                })
        # 将工具结果添加到对话历史作为用户消息
        messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    # 主程序入口。
    # 这一段不是“代理核心算法”，而是给人类准备的试玩入口。
    # 你在终端里输入一句话，领导代理就会开始行动。
    history = []  # 对话历史记录
    while True:
        try:
            # 显示彩色提示符并等待用户输入
            query = input("\033[36ms11 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            # 处理Ctrl+D或Ctrl+C退出
            break
        # 检查退出命令
        if query.strip().lower() in ("q", "exit", ""):
            break
        # `/team`、`/inbox`、`/tasks` 这些都像“老师专用查看命令”。
        # 它们不走模型推理，直接由本地 Python 程序执行。
        # 特殊命令：显示团队成员
        if query.strip() == "/team":
            print(TEAM.list_all())
            continue
        # 特殊命令：显示收件箱内容
        if query.strip() == "/inbox":
            print(json.dumps(BUS.read_inbox("lead"), indent=2))
            continue
        # 特殊命令：显示任务板状态
        if query.strip() == "/tasks":
            TASKS_DIR.mkdir(exist_ok=True)  # 确保任务目录存在
            # 遍历所有任务文件并显示状态
            for f in sorted(TASKS_DIR.glob("task_*.json")):
                t = json.loads(f.read_text())
                # 根据任务状态选择标记符号
                marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}.get(t["status"], "[?]")
                # 如果有所有者，显示所有者信息
                owner = f" @{t['owner']}" if t.get("owner") else ""
                print(f"  {marker} #{t['id']}: {t['subject']}{owner}")
            continue
        # 将用户输入添加到对话历史
        history.append({"role": "user", "content": query})
        # 调用代理循环处理请求
        agent_loop(history)
        # 获取并显示最后的响应内容
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            # 如果响应是工具结果列表，打印每个文本块
            for block in response_content:
                if hasattr(block, "text"):
                    print(block.text)
        print()  # 打印空行分隔


# ============================================================================
# 🎓 老师的时间！让我们一起复习一下学到的知识 🎓
# ============================================================================
"""
亲爱的博士小学生，你真棒！我们已经一起学习了自主代理的奥秘。
让我用最温柔、最简单的方式，把今天学到的东西再总结一遍：

🌟 核心概念：自主代理就像聪明的机器人助手
------------------------------------------
以前的机器人：主人说"扫地"，它就扫地。扫完就傻傻等着。
现在的机器人：主人说"扫地"，它扫完后会自己想：
"厨房也脏了，要不要也扫扫？""花园的叶子掉了，要不要捡捡？"

这就叫"自主性"！机器人会主动找事情做，而不是被动等待。

🏢 系统比喻：小办公室
-------------------
想象一个温暖的小办公室：
- 每个人都有自己的"信箱"（.team/inbox/）
- 墙上贴着"任务卡片"（.tasks/）
- 有一个"老师"（lead）负责指挥
- 有几个"小助手"（teammates）会自己干活

📋 4个新本领：
-------------
1️⃣ 空闲等待：小助手做完活，不是马上回家，而是坐在椅子上等老师
2️⃣ 检查信箱：每隔几秒钟，看看有没有人给自己发新消息
3️⃣ 看任务墙：主动检查有没有新作业可以做
4️⃣ 身份提醒：如果"忘记"自己是谁，会重新自我介绍

🔄 生命周期图：
-------------
生成 → 工作（调用工具） → 空闲（等待5秒） → 检查信箱/任务 → 继续工作 或 超时关闭

🎯 关键代码片段复习：
------------------
1. MessageBus：大家的"传话系统"，用JSON文件存消息
2. scan_unclaimed_tasks：看看任务墙上有哪些活还没人做
3. claim_task：抢着做任务（要加锁，避免两个人同时抢）
4. TeammateManager._loop：小助手的工作循环
5. make_identity_block：当记忆短时，提醒"我是谁"

💡 为什么这很重要？
-----------------
真正的智能助手，不是只会听命令的工具人，
而是会主动发现问题、主动解决问题的小伙伴！

就像一个优秀的学生：
- 老师布置作业，他认真完成
- 做完作业，他会主动复习错题
- 看到黑板上有新通知，他会主动去看
- 忘记了学习目标，他会重新提醒自己

你现在已经掌握了AI自主性的基础！
下次遇到需要多个AI协同工作的场景，
你就会知道怎么设计这样的系统了。

继续加油，小博士！🚀✨
"""
