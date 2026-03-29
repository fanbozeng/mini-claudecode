#!/usr/bin/env python3
# Harness: protocols -- structured handshakes between models.
"""
████████████████████████████████████████████████████████████████████████████
★★★ 老师带小朋友读代码：AI 团队里的“规矩”和“回执单” ★★★

这一个文件是 s10，重点不是“再多招几个 AI 队友”。
那个事情 s09 已经做过了。

s09 教的是：
"大家能互相发消息。"

s10 教的是：
"大家不但能发消息，而且要按规矩发消息。"

为什么要有“规矩”？
因为团队协作里，最怕两件事：

1. 你说了一个请求，对方回的是哪一个？
2. 对方到底同意了、拒绝了，还是根本还没处理？

所以，这一章引入了一个很重要的小道具：

    request_id

你可以把它想成“回执单号码”或者“快递单号”。

只要一个请求发出去，就给它配一个唯一编号。
以后谁来回复，都要带着这个编号。
这样系统才能知道：

- 这条回复是在回答哪个请求
- 这个请求现在的状态是什么
- 是谁发起的、发给谁的

--------------------------------------------------------------------------
一、这章做了两套协议，但骨架是同一个
--------------------------------------------------------------------------

协议 A：shutdown（关机协议）
意思是：lead 想让某个 teammate 优雅地停下来。

    pending -> approved / rejected

    Lead                              Teammate
    +---------------------+          +---------------------+
    | shutdown_request     |          |                     |
    | {                    | -------> | 收到请求            |
    |   request_id: abc    |          | 看看要不要同意      |
    | }                    |          |                     |
    +---------------------+          +---------------------+
                                             |
    +---------------------+          +-------v-------------+
    | shutdown_response    | <------- | shutdown_response   |
    | {                    |          | {                   |
    |   request_id: abc    |          |   request_id: abc   |
    |   approve: true      |          |   approve: true     |
    | }                    |          | }                   |
    +---------------------+          +---------------------+
            |
            v
      状态变成 approved，队友线程停止

协议 B：plan approval（计划审批协议）
意思是：teammate 要做大事之前，要先把计划交给 lead 审核。

    pending -> approved / rejected

    Teammate                          Lead
    +---------------------+          +---------------------+
    | plan_approval        |          |                     |
    | submit: {plan:"..."}| -------> | 看计划靠不靠谱       |
    +---------------------+          | 同意/拒绝？          |
                                     +---------------------+
                                             |
    +---------------------+          +-------v-------------+
    | plan_approval_resp   | <------- | plan_approval       |
    | {approve: true}      |          | review: {req_id,    |
    +---------------------+          |   approve: true}     |
                                     +---------------------+

你会发现：

- 一个是 lead -> teammate 发请求
- 一个是 teammate -> lead 发请求

方向虽然不同，但套路是一样的：

1. 先生成 request_id
2. 再把请求记录到 tracker（跟踪表）
3. 再发消息
4. 再等对方带着同一个 request_id 回复
5. 最后把状态从 pending 改成 approved/rejected

--------------------------------------------------------------------------
二、你可以把整个程序想成一个“办公室”
--------------------------------------------------------------------------

- lead：队长，负责发任务、批计划、让别人下班
- teammate：队友，在后台线程里工作
- inbox：每个人的收件箱文件
- MessageBus：邮局，负责送信
- tracker：小本本，记着“某个请求现在进行到哪一步”

大概像这样：

                 Lead（队长）
                     |
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
      Alice        Bob          Carol
     (线程)        (线程)        (线程)
        │            │            │
        ▼            ▼            ▼
   alice.jsonl   bob.jsonl    carol.jsonl

再加上两本“登记簿”：

    shutdown_requests = {
        "abc123": {"target": "alice", "status": "pending"}
    }

    plan_requests = {
        "xyz999": {"from": "bob", "plan": "...", "status": "pending"}
    }

--------------------------------------------------------------------------
三、这章真正想教你的核心思想
--------------------------------------------------------------------------

"团队协作，不只是能说话，更要能对上号。"

也就是说：

- 发出去的请求，要能被追踪
- 回来的答复，要能被关联
- 状态变化，要有地方记录

一句最重要的话：

Same request_id correlation pattern, two domains.

翻成大白话就是：

"虽然有两个业务场景（关机、审批计划），
 但它们底层都在用同一套『请求编号 + 状态跟踪』思想。"

读这份代码时，请你一直抓住这根主线：

    发请求 -> 记编号 -> 对方回复 -> 按编号更新状态

只要这条线你看懂了，这个文件就算真的看懂了。
████████████████████████████████████████████████████████████████████████████
"""

# 导入 JSON 模块，用于处理 JSON 数据
# 老师讲解：JSON 是一种数据格式，就像写信的格式
import json

# 导入操作系统接口模块，用于环境变量和路径操作
# 老师讲解：操作系统的"助手"，帮我们处理文件和环境
import os

# 导入子进程模块，用于运行外部命令
# 老师讲解：可以运行终端命令的工具，比如 ls, cd 等
import subprocess

# 导入线程模块，用于后台执行
# 老师讲解：让多个事情同时进行的魔法
import threading

# 导入时间模块，用于时间戳
# 老师讲解：时间的钟表，帮我们记录什么时候发生了什么
import time

# 导入 UUID 模块，用于生成唯一请求 ID
# 老师讲解：生成独一无二的编号，就像快递单号
import uuid

# 导入路径模块，提供面向对象的文件系统路径操作
# 老师讲解：高级的文件路径管理器，更好用
from pathlib import Path

# 导入 Anthropic AI 客户端，用于与 AI 模型交互
# 老师讲解：和AI聊天的电话机
from anthropic import Anthropic

# 导入 dotenv 模块，用于从 .env 文件加载环境变量
# 老师讲解：从秘密盒子里拿密码的工具
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
# 设置团队目录路径
TEAM_DIR = WORKDIR / ".team"
# 设置收件箱目录路径
INBOX_DIR = TEAM_DIR / "inbox"

# 设置系统提示，指示代理作为团队领导管理队友
SYSTEM = f"You are a team lead at {WORKDIR}. Manage teammates with shutdown and plan approval protocols."

# 定义有效的消息类型集合
VALID_MSG_TYPES = {
    "message",
    "broadcast",
    "shutdown_request",
    "shutdown_response",
    "plan_approval_response",
}

# -- Request trackers: correlate by request_id --
# 这两个字典就是“登记簿”。
# 不是拿来放对话正文的，而是拿来放“请求的状态”的。
#
# 例如：
# lead 发了一个 shutdown_request 给 alice，
# 系统就会马上在 shutdown_requests 里记一笔：
#   {"abc123": {"target": "alice", "status": "pending"}}
#
# 以后 alice 回复 shutdown_response，并带着 request_id=abc123，
# 系统就知道：
# “哦，原来这条回复是在回答那次关机请求。”
#
# plan_requests 也是同样的道理，只是业务从“关机”换成了“计划审批”。
shutdown_requests = {}
# 关机协议的状态表：谁被请求关闭、现在是 pending 还是 approved/rejected
plan_requests = {}
# 计划审批的状态表：谁提交了计划、计划内容是什么、审核到什么状态
_tracker_lock = threading.Lock()
# 因为有多个线程会同时读写上面的字典，所以要加锁。
# 你可以把锁想成“只有拿到钥匙的人，才能改登记簿”。


# -- MessageBus: JSONL inbox per teammate --
# 定义 MessageBus 类，每个队友有 JSONL 收件箱
class MessageBus:
    """
    MessageBus = 邮局 / 邮件总站

    这整个类不负责“思考”。
    它只负责一件事：
    把消息安全地送到对应的收件箱文件里。

    为什么用文件当收件箱？

    1. 简单：写一行 JSON 就是一封信
    2. 持久：程序一时停了，文件还在
    3. 解耦：每个人都有自己的 inbox，不会挤在一起
    4. 容易观察：你真的可以去 .team/inbox/ 里看邮件文件

    这里每个收件箱都是一个 .jsonl 文件：

    - alice.jsonl
    - bob.jsonl
    - lead.jsonl

    jsonl 的意思是：
    “一行一个 JSON 对象”。
    所以追加写很方便，也很适合邮件这种一条一条增长的东西。
    """

    # 初始化方法
    def __init__(self, inbox_dir: Path):
        # 设置收件箱目录
        self.dir = inbox_dir
        # 创建目录如果不存在
        self.dir.mkdir(parents=True, exist_ok=True)

    # 发送消息的方法
    def send(self, sender: str, to: str, content: str,
             msg_type: str = "message", extra: dict = None) -> str:
        # 如果消息类型无效，返回错误
        if msg_type not in VALID_MSG_TYPES:
            return f"Error: Invalid type '{msg_type}'. Valid: {VALID_MSG_TYPES}"
        # 创建消息字典
        msg = {
            "type": msg_type,
            "from": sender,
            "content": content,
            "timestamp": time.time(),
        }
        # 如果有额外数据，更新消息
        if extra:
            msg.update(extra)
        # 获取收件箱路径
        inbox_path = self.dir / f"{to}.jsonl"
        # 追加写入消息
        with open(inbox_path, "a") as f:
            f.write(json.dumps(msg) + "\n")
        # 返回发送确认
        return f"Sent {msg_type} to {to}"

    # 读取收件箱的方法
    def read_inbox(self, name: str) -> list:
        """
        读取并清空某个人的收件箱。

        这是一个非常关键的设计：

        1. 先把信全读出来
        2. 再把收件箱清空

        这样做的意思是：
        “这些邮件我已经收到了，不要下次再重复看一遍。”

        所以它不是普通的 read，而更像：
        drain / consume / 取走

        很像你去学校门口收自己的信：
        你把信件拿走以后，信箱就空了。
        """
        # 获取收件箱路径
        inbox_path = self.dir / f"{name}.jsonl"
        # 如果文件不存在，返回空列表
        if not inbox_path.exists():
            return []
        # 初始化消息列表
        messages = []
        # 读取文件内容，分割为行
        for line in inbox_path.read_text().strip().splitlines():
            if line:
                # 解析 JSON 并添加到列表
                messages.append(json.loads(line))
        # 清空收件箱文件
        inbox_path.write_text("")
        # 返回消息列表
        return messages

    # 广播消息的方法
    def broadcast(self, sender: str, content: str, teammates: list) -> str:
        # 初始化计数器
        count = 0
        # 遍历队友列表
        for name in teammates:
            if name != sender:
                # 发送广播消息
                self.send(sender, name, content, "broadcast")
                # 增加计数
                count += 1
        # 返回广播确认
        return f"Broadcast to {count} teammates"


BUS = MessageBus(INBOX_DIR)


# -- TeammateManager with shutdown + plan approval --
# 这个类是“团队管理员”。
# 它关心的不是某一个工具怎么跑，而是：
# 1. 队友怎么出生（spawn）
# 2. 队友怎么在后台持续工作
# 3. 队友怎么遵守协议（plan approval / shutdown）
class TeammateManager:
    """
    TeammateManager = 队伍管理员

    你可以把它想成“班主任 + 宿舍管理员”的结合体：

    - 班主任：知道班里有哪些同学
    - 宿舍管理员：知道谁在忙、谁空闲、谁已经休息
    - 调度员：可以把某个队友启动成一个后台线程

    它管理两种状态：

    1. 磁盘上的状态
       存在 .team/config.json 里，记住有哪些成员、状态是什么

    2. 内存里的状态
       self.threads 里放着真正运行中的线程对象
    """

    # 初始化方法
    def __init__(self, team_dir: Path):
        # 设置团队目录
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
        启动一个队友线程。

        注意这里做了两件事：

        1. 更新“名册”里的状态
           把成员记成 working
        2. 真正启动线程
           让这个队友在后台开始循环工作

        所以 spawn 不是“只在名单里写一下”。
        它是“登记 + 开工”一起做。
        """
        # 查找成员
        member = self._find_member(name)
        if member:
            # 如果成员存在且状态不是 idle 或 shutdown，返回错误
            if member["status"] not in ("idle", "shutdown"):
                return f"Error: '{name}' is currently {member['status']}"
            # 更新状态和角色
            member["status"] = "working"
            member["role"] = role
        else:
            # 如果成员不存在，创建新成员
            member = {"name": name, "role": role, "status": "working"}
            # 添加到成员列表
            self.config["members"].append(member)
        # 保存配置
        self._save_config()
        # 创建线程
        thread = threading.Thread(
            target=self._teammate_loop,
            args=(name, role, prompt),
            daemon=True,
        )
        # 存储线程
        self.threads[name] = thread
        # 启动线程
        thread.start()
        # 返回生成确认
        return f"Spawned '{name}' (role: {role})"

    # 私有方法，队友循环
    def _teammate_loop(self, name: str, role: str, prompt: str):
        """
        这是每个 teammate 线程真正工作的地方。

        一个队友线程的生活，大概长这样：

        1. 先带着初始 prompt 上岗
        2. 每轮先看看自己的 inbox 有没有新信
        3. 把新信塞进 messages，告诉模型“这是刚收到的事”
        4. 调一次大模型
        5. 如果模型想用工具，就执行工具
        6. 如果工具结果里出现“我同意 shutdown”，那就准备收工
        7. 最后把自己的状态标记成 idle 或 shutdown

        你要特别留意：

        - inbox 是外部世界给队友的新消息
        - messages 是喂给模型的上下文

        前者像“新收到的纸条”，后者像“队友脑子里当前看到的聊天记录”。
        """
        # 构建系统提示
        sys_prompt = (
            f"You are '{name}', role: {role}, at {WORKDIR}. "
            f"Submit plans via plan_approval before major work. "
            f"Respond to shutdown_request with shutdown_response."
        )
        # 初始化消息列表
        messages = [{"role": "user", "content": prompt}]
        # 获取队友工具
        tools = self._teammate_tools()
        # 初始化退出标志
        should_exit = False
        # 循环最多 50 次
        # 这里不是“永远循环”，而是最多 50 轮，防止教学版线程失控跑太久。
        for _ in range(50):
            # 读取收件箱
            inbox = BUS.read_inbox(name)
            for msg in inbox:
                # 添加消息到消息列表
                # 这一步相当于把“信箱里的新任务”贴进队友的聊天上下文里。
                messages.append({"role": "user", "content": json.dumps(msg)})
            if should_exit:
                # 如果应该退出，跳出循环
                break
            try:
                # 调用客户端创建消息
                response = client.messages.create(
                    model=MODEL,
                    system=sys_prompt,
                    messages=messages,
                    tools=tools,
                    max_tokens=8000,
                )
            except Exception:
                # 如果出错，跳出循环
                break
            # 添加助手响应
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                # 如果停止原因不是工具使用，跳出循环
                break
            # 初始化结果列表
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    # 执行工具
                    output = self._exec(name, block.name, block.input)
                    # 打印输出
                    print(f"  [{name}] {block.name}: {str(output)[:120]}")
                    # 添加结果
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(output),
                    })
                    if block.name == "shutdown_response" and block.input.get("approve"):
                        # 如果是关闭响应且批准，设置退出标志
                        # 注意：不是一看到 shutdown_request 就退出，
                        # 而是“自己明确做出 approve 响应”以后才退出。
                        # 这就是“优雅关闭”的味道：先回消息，再停止。
                        should_exit = True
            # 添加结果到消息
            messages.append({"role": "user", "content": results})
        # 查找成员
        member = self._find_member(name)
        if member:
            # 更新状态为 shutdown 如果退出，否则为 idle
            member["status"] = "shutdown" if should_exit else "idle"
            # 保存配置
            self._save_config()

    # 私有方法，执行工具
    def _exec(self, sender: str, tool_name: str, args: dict) -> str:
        """
        这是“队友版工具分发器”。

        模型只会说：
        “我想调用哪个工具，并给什么参数。”

        真正把这句话变成 Python 行为的人，就是这个函数。

        你可以把它理解成：
        “工具前台小姐姐，把请求分发到正确窗口。”

        其中最值得学习的不是 bash/read/write，
        而是后面两个协议型工具：

        - shutdown_response
        - plan_approval

        因为这两个工具体现了“发消息 + 改 tracker + 带 request_id”的完整套路。
        """
        # 这些基础工具与 s02 相同
        if tool_name == "bash":
            # 执行 bash 命令
            return _run_bash(args["command"])
        if tool_name == "read_file":
            # 读取文件
            return _run_read(args["path"])
        if tool_name == "write_file":
            # 写入文件
            return _run_write(args["path"], args["content"])
        if tool_name == "edit_file":
            # 编辑文件
            return _run_edit(args["path"], args["old_text"], args["new_text"])
        if tool_name == "send_message":
            # 发送消息
            return BUS.send(sender, args["to"], args["content"], args.get("msg_type", "message"))
        if tool_name == "read_inbox":
            # 读取收件箱
            return json.dumps(BUS.read_inbox(sender), indent=2)
        if tool_name == "shutdown_response":
            # 处理关闭响应
            # 这是 teammate 在说：
            # “我收到了那个 request_id 对应的关机请求，我现在同意/拒绝。”
            req_id = args["request_id"]
            # 获取请求 ID
            approve = args["approve"]
            # 获取批准状态
            with _tracker_lock:
                # 使用锁更新关闭请求状态
                # 这一步是在改“登记簿”，不是在发信。
                if req_id in shutdown_requests:
                    shutdown_requests[req_id]["status"] = "approved" if approve else "rejected"
            # 发送关闭响应消息
            # 这一步才是在“发回执单”给 lead。
            BUS.send(
                sender, "lead", args.get("reason", ""),
                "shutdown_response", {"request_id": req_id, "approve": approve},
            )
            # 返回响应确认
            return f"Shutdown {'approved' if approve else 'rejected'}"
        if tool_name == "plan_approval":
            # 处理计划批准
            # 注意名字容易绕：
            # 对队友来说，这个工具的意思是“提交计划，请求审批”。
            # 对 lead 来说，plan_approval 工具则是“审核这个计划”。
            # 同一个领域名字，站在不同角色视角，动作不一样。
            plan_text = args.get("plan", "")
            # 获取计划文本
            req_id = str(uuid.uuid4())[:8]
            # 生成请求 ID
            with _tracker_lock:
                # 使用锁添加计划请求
                # 先在登记簿记下来：“某队友提了一个计划，状态 pending”
                plan_requests[req_id] = {"from": sender, "plan": plan_text, "status": "pending"}
            # 发送计划批准响应消息
            # 虽然消息类型叫 plan_approval_response，
            # 但这里其实是在把“待审批计划”送到 lead 收件箱里。
            # lead 之后会根据 request_id 再回一个 approve/reject。
            BUS.send(
                sender, "lead", plan_text, "plan_approval_response",
                {"request_id": req_id, "plan": plan_text},
            )
            # 返回提交确认
            return f"Plan submitted (request_id={req_id}). Waiting for lead approval."
        # 返回未知工具错误
        return f"Unknown tool: {tool_name}"

    # 私有方法，获取队友工具
    def _teammate_tools(self) -> list:
        """
        告诉队友：“你手里有哪些按钮可以按”。

        大模型本身不会直接执行 Python。
        它只能看到一个工具菜单，然后决定调用哪个工具。

        所以这份列表非常像“游戏里的技能栏”：
        有哪些技能、每个技能叫什么、要传哪些参数，
        全都要先写清楚。
        """
        # 这些基础工具与 s02 相同
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
            {"name": "shutdown_response", "description": "Respond to a shutdown request. Approve to shut down, reject to keep working.",
             "input_schema": {"type": "object", "properties": {"request_id": {"type": "string"}, "approve": {"type": "boolean"}, "reason": {"type": "string"}}, "required": ["request_id", "approve"]}},
            {"name": "plan_approval", "description": "Submit a plan for lead approval. Provide plan text.",
             "input_schema": {"type": "object", "properties": {"plan": {"type": "string"}}, "required": ["plan"]}},
        ]

    # 列出所有队友的方法
    def list_all(self) -> str:
        # 如果没有成员，返回无队友消息
        if not self.config["members"]:
            return "No teammates."
        # 初始化行列表
        lines = [f"Team: {self.config['team_name']}"]
        for m in self.config["members"]:
            # 添加每行成员信息
            lines.append(f"  {m['name']} ({m['role']}): {m['status']}")
        # 返回连接后的字符串
        return "\n".join(lines)

    # 获取成员名称列表的方法
    def member_names(self) -> list:
        # 返回成员名称列表
        return [m["name"] for m in self.config["members"]]


TEAM = TeammateManager(TEAM_DIR)


# -- Base tool implementations (these base tools are unchanged from s02) --
# 定义基础工具实现（这些基础工具与 s02 相同）
def _safe_path(p: str) -> Path:
    # 定义安全路径函数，确保路径在工作目录内
    path = (WORKDIR / p).resolve()
    # 解析路径为绝对路径
    if not path.is_relative_to(WORKDIR):
        # 检查路径是否在工作目录内
        raise ValueError(f"Path escapes workspace: {p}")
        # 如果不在，抛出错误
    return path
    # 返回安全路径

def _run_bash(command: str) -> str:
    # 定义运行 bash 命令的函数
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot"]
    # 定义危险命令列表
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


# -- Lead-specific protocol handlers --
# 定义领导特定的协议处理函数
def handle_shutdown_request(teammate: str) -> str:
    """
    lead 发起“关机请求”。

    这个函数做三件事：

    1. 生成 request_id
    2. 记到 shutdown_requests 里
    3. 发消息给对应队友

    也就是说：
    “先登记，再发信。”
    """
    # 处理关闭请求
    req_id = str(uuid.uuid4())[:8]
    # 生成请求 ID
    with _tracker_lock:
        # 使用锁添加关闭请求
        shutdown_requests[req_id] = {"target": teammate, "status": "pending"}
    # 发送关闭请求消息
    BUS.send(
        "lead", teammate, "Please shut down gracefully.",
        "shutdown_request", {"request_id": req_id},
    )
    # 返回请求发送确认
    return f"Shutdown request {req_id} sent to '{teammate}' (status: pending)"

def handle_plan_review(request_id: str, approve: bool, feedback: str = "") -> str:
    """
    lead 审核某个队友提交上来的计划。

    注意这里不是“创建计划请求”，而是“处理已经存在的计划请求”。
    所以参数里直接传入 request_id。

    它的动作是：

    1. 去 plan_requests 里找到原来的申请单
    2. 把状态改成 approved 或 rejected
    3. 发一条带同样 request_id 的回复给原来的提交者
    """
    # 处理计划审查
    with _tracker_lock:
        # 使用锁获取计划请求
        req = plan_requests.get(request_id)
    if not req:
        # 如果请求不存在，返回错误
        return f"Error: Unknown plan request_id '{request_id}'"
    with _tracker_lock:
        # 使用锁更新请求状态
        req["status"] = "approved" if approve else "rejected"
    # 发送计划批准响应消息
    BUS.send(
        "lead", req["from"], feedback, "plan_approval_response",
        {"request_id": request_id, "approve": approve, "feedback": feedback},
    )
    # 返回审查确认
    return f"Plan {req['status']} for '{req['from']}'"

def _check_shutdown_status(request_id: str) -> str:
    """
    根据 request_id 查看某次关机请求现在进行到哪一步。

    为什么需要这个函数？
    因为 lead 发出 shutdown_request 以后，不一定马上就有结果。
    所以 lead 需要一个“查单号”的方法。

    就像你寄快递后，会用快递单号查：
    - 还在路上
    - 已签收
    - 还是根本没有这个单号
    """
    # 检查关闭状态
    with _tracker_lock:
        # 使用锁获取关闭请求状态
        return json.dumps(shutdown_requests.get(request_id, {"error": "not found"}))


# -- Lead tool dispatch (12 tools) --
# 定义领导工具调度（12 个工具）
TOOL_HANDLERS = {
    # 定义工具处理器字典，将工具名称映射到处理函数
    "bash":              lambda **kw: _run_bash(kw["command"]),
    # bash 工具：运行 shell 命令
    "read_file":         lambda **kw: _run_read(kw["path"], kw.get("limit")),
    # read_file 工具：读取文件内容
    "write_file":        lambda **kw: _run_write(kw["path"], kw["content"]),
    # write_file 工具：写入内容到文件
    "edit_file":         lambda **kw: _run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    # edit_file 工具：替换文件中的文本
    "spawn_teammate":    lambda **kw: TEAM.spawn(kw["name"], kw["role"], kw["prompt"]),
    # spawn_teammate 工具：生成队友
    "list_teammates":    lambda **kw: TEAM.list_all(),
    # list_teammates 工具：列出所有队友
    "send_message":      lambda **kw: BUS.send("lead", kw["to"], kw["content"], kw.get("msg_type", "message")),
    # send_message 工具：发送消息到队友收件箱
    "read_inbox":        lambda **kw: json.dumps(BUS.read_inbox("lead"), indent=2),
    # read_inbox 工具：读取并排出领导收件箱
    "broadcast":         lambda **kw: BUS.broadcast("lead", kw["content"], TEAM.member_names()),
    # broadcast 工具：广播消息到所有队友
    "shutdown_request":  lambda **kw: handle_shutdown_request(kw["teammate"]),
    # shutdown_request 工具：请求关闭队友
    "shutdown_response": lambda **kw: _check_shutdown_status(kw.get("request_id", "")),
    # shutdown_response 工具：检查关闭响应状态
    "plan_approval":     lambda **kw: handle_plan_review(kw["request_id"], kw["approve"], kw.get("feedback", "")),
    # plan_approval 工具：批准或拒绝计划
}

# these base tools are unchanged from s02
# 这些基础工具与 s02 相同
TOOLS = [
    # 定义工具列表，每个工具包含名称、描述和输入模式
    {"name": "bash", "description": "Run a shell command.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    # bash 工具定义
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    # read_file 工具定义
    {"name": "write_file", "description": "Write content to file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    # write_file 工具定义
    {"name": "edit_file", "description": "Replace exact text in file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
    # edit_file 工具定义
    {"name": "spawn_teammate", "description": "Spawn a persistent teammate.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "role": {"type": "string"}, "prompt": {"type": "string"}}, "required": ["name", "role", "prompt"]}},
    # spawn_teammate 工具定义
    {"name": "list_teammates", "description": "List all teammates.",
     "input_schema": {"type": "object", "properties": {}}},
    # list_teammates 工具定义
    {"name": "send_message", "description": "Send a message to a teammate.",
     "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "content": {"type": "string"}, "msg_type": {"type": "string", "enum": list(VALID_MSG_TYPES)}}, "required": ["to", "content"]}},
    # send_message 工具定义
    {"name": "read_inbox", "description": "Read and drain the lead's inbox.",
     "input_schema": {"type": "object", "properties": {}}},
    # read_inbox 工具定义
    {"name": "broadcast", "description": "Send a message to all teammates.",
     "input_schema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},
    # broadcast 工具定义
    {"name": "shutdown_request", "description": "Request a teammate to shut down gracefully. Returns a request_id for tracking.",
     "input_schema": {"type": "object", "properties": {"teammate": {"type": "string"}}, "required": ["teammate"]}},
    # shutdown_request 工具定义
    {"name": "shutdown_response", "description": "Check the status of a shutdown request by request_id.",
     "input_schema": {"type": "object", "properties": {"request_id": {"type": "string"}}, "required": ["request_id"]}},
    # shutdown_response 工具定义
    {"name": "plan_approval", "description": "Approve or reject a teammate's plan. Provide request_id + approve + optional feedback.",
     "input_schema": {"type": "object", "properties": {"request_id": {"type": "string"}, "approve": {"type": "boolean"}, "feedback": {"type": "string"}}, "required": ["request_id", "approve"]}},
    # plan_approval 工具定义
]


def agent_loop(messages: list):
    """
    这是 lead 自己的主循环。

    lead 每轮都会做这几件事：

    1. 先看自己的 inbox
       有没有队友发来的计划、回执、普通消息
    2. 如果有，就把 inbox 内容塞进 messages
    3. 调用大模型，请 lead 决定下一步
    4. 如果模型调用工具，就真正执行工具
    5. 把工具结果再喂回模型

    所以整个系统其实有两层循环：

    - lead 的循环：在主线程里
    - teammate 的循环：在各自后台线程里

    它们互相靠 inbox 文件传话。
    """
    # 定义代理循环函数，处理消息和工具调用
    while True:
        # 无限循环，直到停止
        # 读取领导收件箱
        inbox = BUS.read_inbox("lead")
        if inbox:
            # 如果有收件箱消息
            # 这里用 <inbox>...</inbox> 包起来，是为了让模型更清楚：
            # “下面这一坨不是普通对话，而是新收到的信件集合”。
            messages.append({
                "role": "user",
                "content": f"<inbox>{json.dumps(inbox, indent=2)}</inbox>",
            })
            # 添加用户消息
            messages.append({
                "role": "assistant",
                "content": "Noted inbox messages.",
            })
            # 添加助手消息
        # 调用客户端创建消息
        response = client.messages.create(
            model=MODEL,
            system=SYSTEM,
            messages=messages,
            tools=TOOLS,
            max_tokens=8000,
        )
        # 添加助手响应
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            # 如果停止原因不是工具使用，返回
            return
        # 初始化结果列表
        results = []
        for block in response.content:
            if block.type == "tool_use":
                # 如果是工具使用块
                handler = TOOL_HANDLERS.get(block.name)
                # 获取对应的处理器
                try:
                    # 尝试执行处理器
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                    # 如果有处理器，调用它，否则返回未知工具错误
                except Exception as e:
                    # 如果出错，设置错误输出
                    output = f"Error: {e}"
                # 打印工具名称和输出前 200 字符
                print(f"> {block.name}: {str(output)[:200]}")
                # 添加工具结果到结果列表
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(output),
                })
        # 将结果作为用户消息添加到消息列表
        messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    # 如果作为主程序运行
    history = []
    # 初始化消息历史列表
    # history 是 lead 的聊天历史，不是所有队友共享的一份总历史。
    while True:
        # 无限循环，等待用户输入
        try:
            # 尝试获取用户输入
            query = input("\033[36ms10 >> \033[0m")
            # 使用彩色提示符输入查询
        except (EOFError, KeyboardInterrupt):
            # 如果遇到 EOF 或中断，退出
            break
        if query.strip().lower() in ("q", "exit", ""):
            # 如果输入是退出命令，退出
            break
        if query.strip() == "/team":
            # 如果输入是 /team，打印团队列表
            # 这是一个调试/观察命令，方便你看每个队友当前是什么状态。
            print(TEAM.list_all())
            continue
        if query.strip() == "/inbox":
            # 如果输入是 /inbox，打印领导收件箱
            # 这也是一个观察命令，帮助你直接看 lead 收到了哪些信。
            print(json.dumps(BUS.read_inbox("lead"), indent=2))
            continue
        # 将用户查询添加到历史
        history.append({"role": "user", "content": query})
        # 调用代理循环处理查询
        agent_loop(history)
        response_content = history[-1]["content"]
        # 获取最后一条消息的内容
        if isinstance(response_content, list):
            # 如果内容是列表
            for block in response_content:
                # 遍历块
                if hasattr(block, "text"):
                    # 如果块有文本属性，打印
                    print(block.text)
        print()
        # 打印空行


# ============================================================================
# 🎓 老师的时间！让我们一起复习一下学到的知识 🎓
# ============================================================================
"""
亲爱的小博士，你真棒！我们已经一起学习了AI团队里的"规矩"和"回执单"。
让我用最温柔、最简单的方式，把今天学到的东西再总结一遍：

🌟 核心概念：团队协作的"规矩"
------------------------------------------
以前的AI：只会聊天，不会协作
现在的AI：会按规矩说话，会追踪请求状态

就像快递公司：
- 寄快递 → 给个单号
- 查快递 → 用单号查询状态
- 收快递 → 确认单号对上

这就叫"协议"！让AI们能可靠地协作。

🏢 系统比喻：办公室里的快递站
-------------------
想象一个办公室：
- 队长（lead）：负责发任务、审批计划、让队友下班
- 队友（teammate）：在后台工作的AI助手
- 收件箱（inbox）：每个人的信箱文件
- 邮局（MessageBus）：负责送信
- 登记簿（tracker）：记录请求状态的小本本

📋 两大协议：
-------------
协议A：关机协议（Shutdown Protocol）
队长想让某个队友停工：
1. 生成单号 → 记到登记簿 → 发请求信
2. 队友回复 → 按单号更新状态 → 同意/拒绝

协议B：计划审批协议（Plan Approval Protocol）
队友要做大事前要先汇报：
1. 队友提交计划 → 生成单号 → 队长审批
2. 队长回复 → 按单号更新状态 → 通过/驳回

🔄 核心套路：请求编号 + 状态跟踪
-------------------------------
虽然有两个不同的业务（关机 vs 审批），但底层思想一样：

    发请求 → 生成 request_id → 记到 tracker → 对方回复 → 按编号更新状态

就像快递：
    寄件 → 给单号 → 记到系统 → 收件 → 按单号确认

🎯 为什么这很重要？
-----------------
真正的团队协作，不是只会说话，而是：
- ✅ 能追踪请求状态
- ✅ 能关联请求和回复
- ✅ 能管理复杂的工作流程

就像一个成熟的公司：
- 发邮件 → 有邮件ID
- 审批流程 → 有审批单号
- 项目管理 → 有任务编号

你现在已经掌握了AI协作的基础！
下次遇到需要多个AI协同工作的场景，
你就会知道怎么设计可靠的协议了。

💡 关键洞察：
"团队协作，不只是能说话，更要能对上号。"

继续加油，小博士！🚀✨
"""
