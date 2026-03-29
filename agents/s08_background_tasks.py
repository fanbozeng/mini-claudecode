#!/usr/bin/env python3
# Harness: background execution -- the model thinks while the harness waits.

"""
████████████████████████████████████████████████████████████████
★★★ 🎈 小学生零基础编程讲解 🎈 ★★★

亲爱的小朋友们！欢迎来到 Python 编程的世界！

这个程序teach你一个非常厉害的概念："后台执行"

📖 【用最简单的话讲】========================================

想象你有一个魔法机器人小精灵：

场景1：★ 没有"后台执行"，机器人很慢 ★
  小你："小精灵，帮我做这件事！"
  小精灵："好的，我开始做... （过了5分钟）完成了！"
  小你："太慢了！我5分钟什么都干不了"

场景2：★ 有了"后台执行"，机器人超聪明 ★
  小你："小精灵1，做这个！"
  小精灵1："好的，我去后台做..." （一瞬间）
  小你："小精灵2，做那个！"
  小精灵2："好的，我也去后台做..." （一瞬间）
  小你："小精灵3，做这个！"  
  小精灵3："好的，我也去后台做..." （一瞬间）
  （同时）
  小精灵们在后台一起工作...
  （过了一会儿）
  小精灵1："我完成了！结果是..."
  小精灵2："我也完成了！结果是..."
  小精灵3："我也完成了！结果是..."

看出区别没有？
- 场景1：一个接一个做，很慢（阻塞式 Blocking）
- 场景2：一起做，很快（后台式 Background）

🎯 【这个程序的5个核心部分】====================================

第1部分 → BackgroundManager 类（工厂经理）
  工作：管理后台员工，给他们分配任务，收集他们的报告

第2部分 → run() 方法（分配任务）
  工作："现在去做这个任务！" → 立即返回

第3部分 → _execute() 方法（员工做工作）
  工作：在后台线程中运行任务

第4部分 → agent_loop() 函数（AI的思维循环）
  工作：AI在不断循环：检查邮件 → 思考 → 执行工具

第5部分 → 主程序（用户交互）
  工作：等待你输入命令，然后一切开始运转

💡 【关键概念讲解】==========================================

★ 什么是"线程 Thread"？====
线程 = 电脑里的"虚拟员工"

你的电脑只有1个真实的"CPU大脑"，但可以同时运行好多事情
这是通过"线程切换"实现的：
  - 做任务A做了一点
  - 切换到任务B做一点
  - 再切换回任务A做一点
  - ... 
速度很快，看起来像在同时运行

★ 什么是"队列 Queue"？====
队列 = 邮件信箱

员工完成工作后，不直接告诉经理，而是把报告放进信箱里
经理定期检查信箱，看有没有新报告
这样就不会产生冲突了

★ 什么是"锁 Lock"？====
锁 = 浴室的锁

如果你洗澡时不锁门，别人可能突然冲进来
在编程中，如果不上锁，两个线程可能同时访问同一个数据
这会造成大问题！所以需要"锁"来保护

★ 什么是"工具 Tool"？====
工具 = 魔法棒

AI 助手很聪明，但不能直接控制你的电脑
所以我们给它一些"工具"：
  - bash 工具：可以运行命令
  - read_file 工具：可以读文件
  - write_file 工具：可以写文件
  - background_run 工具：可以后台运行命令
AI 想做什么，就选择对应的工具

⚙️ 【整个程序如何运行】==================================

1. 你输入一个问题，比如："请帮我运行这个耗时命令"

2. AI 收到问题，思考一下，说："我应该用 background_run 工具"

3. AI 用了 background_run 工具，说："我已经安排好了，任务ID是abc123"
   → 此时后台线程已经在运行了，AI 不用等

4. AI 继续做其他事情...
   同时，后台线程在努力工作...

5. 后台线程完成了！把结果放进信箱

6. AI 下一次思考前，检查信箱，发现有新邮件
   → "哦！abc123 任务完成了！结果是..."
   → 看到结果后，AI 继续思考

7. 不停重复...直到 AI 完成全部任务

💪 【学完这个程序，你将理解】====================

✓ 什么是"线程"（Thread）- 虚拟工人
✓ 什么是"后台执行"- 同时做多件事
✓ 什么是"队列" - 安全的邮件系统
✓ 什么是"锁"（Lock）- 防止冲突的钥匙
✓ 什么是"工具"（Tools）- AI 能做什么
✓ 什么是"异步"（Async）- 不用等待立即返回

这些概念在实际开发中太重要了！学会了，你就是编程高手的料！

📝 【现在开始阅读代码吧！】==========================

下面的代码里有很多 ★ 符号标记重要部分
还有中文讲解，一步步教你这个程序怎么做的

祝你学得开心！🎉

████████████████████████████████████████████████████████████████
"""

# ============ 代码开始 ============

"""
s08_background_tasks.py - 后台任务执行讲解

==== 简单来说，这个程序做什么呢？ ====

想象你有一个助手小机器人：
- 你给机器人一个任务（比如"去打扫房间"）
- 机器人说："好的，我现在开始打扫"
- 你不用等机器人打扫完，你可以继续做其他事情（比如做作业）
- 机器人打扫完后，会跑过来告诉你："打扫完了！"

这个程序就是这样的原理：
    主线程（你）                    后台线程（机器人）
    +-------------------+           +-------------------+
    | 继续思考下一步    |           | 任务在这里运行    |
    | ...               |           | ...               |
    | [问AI] <---------- 我完成了---- | 完成后发送结果      |
    |  检查结果│         |           +-------------------+
    +-------------------+

时间线：
AI ---[创建任务A]---[创建任务B]---[继续思考]---
        |              |
        v              v
      [A在后台跑]  [B在后台跑]     （同时进行，不阻塞）
        |              |
        +---- 结果队列 ----> [结果被混入下一条消息]

核心理念："发射后就忘记它 -- AI不用等待任务完成，可以继续工作"


==== 为什么要这样做呢？ ====

没有后台执行的问题（效率很低）：
  1. 你给机器人一个10分钟的任务
  2. 你必须坐在那儿一直等，什么都做不了
  3. 10分钟后才能继续

有后台执行的好处（效率很高）：
  1. 你给机器人一个10分钟的任务
  2. 机器人在后台工作
  3. 你立即可以继续做其他事情（可以做多件事）
  4. 机器人完成后自动告诉你
  5. 你继续处理结果

这样你可以同时做很多事情，效率高多了！
"""

# 导入操作系统接口模块，用于环境变量和路径操作
import os
# 导入子进程模块，用于运行外部命令
import subprocess
# 导入线程模块，用于后台执行
import threading
# 导入 UUID 模块，用于生成唯一任务 ID
import uuid
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

# 设置系统提示，指示代理使用 background_run 工具
SYSTEM = f"You are a coding agent at {WORKDIR}. Use background_run for long-running commands."


# ============ 第一部分：后台任务管理器 BG ============
# 定义 BackgroundManager 类，用于线程执行和通知队列

# ★ 什么是"管理器"？
# 管理器就像一个人事部，负责：
# 1. 记录每个任务的信息
# 2. 创建新线程来执行任务
# 3. 收集完成的任务结果

class BackgroundManager:
    """
    后台任务管理器 - 就像一个工厂经理
    
    想象工厂里有很多员工：
    - 主员工（主线程）：给员工分配任务，不用等
    - 其他员工（后台线程）：在角落里做自己的工作
    - 经理就是这个 BackgroundManager
    - 经理的工作：
      * 记录谁做什么任务
      * 员工完成后告诉经理
      * 经理收集所有完成的报告
    """
    
    # ★ 初始化方法 - 就是建立这个工厂
    def __init__(self):
        # 初始化一个工作记录簿，键=员工ID，值=员工信息
        # 比如：
        #   "abc123": {"status": "running", "result": None, "command": "ls"}
        #   "def456": {"status": "completed", "result": "...输出...", "command": "pwd"}
        self.tasks = {}  # task_id -> {status, result, command}
        
        # 初始化一个通知队列 - 就像一个信箱
        # 员工完成工作后，把报告放在这个信箱里
        # 经理定期检查信箱，获取所有完成的报告
        self._notification_queue = []  # completed task results
        
        # ★ 什么是"锁"？为什么需要它？
        # 想象你在家里，你和你妈妈都想往冰箱放东西
        # 如果同时打开冰箱门，会很混乱
        # 所以需要一个"锁"，一次只让一个人打开
        # 在这里，主线程和后台线程都想访问通知队列
        # 需要用"锁"保证每次只有一个线程访问
        self._lock = threading.Lock()  # 这就是那把"锁"

    # ★★★ 最关键的方法：后台运行一个命令 ★★★
    def run(self, command: str) -> str:
        """
        启动一个后台线程来运行命令，立即返回任务ID
        
        工厂经理的动作：
        1. 老板说："我需要做任务，但我很忙"
        2. 经理给任务编号（比如"abc123"）
        3. 经理找一个员工（创建线程）
        4. 经理告诉员工："你去做这个任务"（启动线程）
        5. 经理立即回复老板："任务已分配，编号abc123"
        6. 老板可以继续工作了！
        """
        
        # UUID = 全球唯一身份码，就像身份证号
        # uuid.uuid4() 生成一个长长的随机数
        # [:8] 表示只取前8个字符（为了简短易读）
        # 比如："a1b2c3d4"
        task_id = str(uuid.uuid4())[:8]
        
        # 在工作记录簿中记录这个任务
        # "running" = 正在进行中
        # "result" = None 表示还没有结果
        # "command" = 要执行的命令
        self.tasks[task_id] = {"status": "running", "result": None, "command": command}
        
        # ★ 创建一个新线程（可以理解为"虚拟员工"）
        # target=self._execute 告诉线程去执行 _execute 这个方法
        # args=(task_id, command) 传递任务ID和命令给 _execute
        # daemon=True 表示这是"后台员工"，主程序结束时它也自动结束
        thread = threading.Thread(
            target=self._execute, args=(task_id, command), daemon=True
        )
        
        # thread.start() = "现在开始工作！"
        # 从这一刻起，这个线程就在后台独立运行了
        # 主程序不用等待它完成
        thread.start()
        
        # 立即返回一个消息给老板说"交给我了"
        # 这样老板可以继续做其他事情
        return f"Background task {task_id} started: {command[:80]}"

    # ★★★ 员工做工作的地方 ★★★
    def _execute(self, task_id: str, command: str):
        """
        这是在后台线程中运行的方法
        
        员工的工作步骤：
        1. 员工收到任务ID和要做的命令
        2. 员工执行命令（可能很耗时）
        3. 员工记录执行结果和状态
        4. 员工把报告放进信箱（通知队列）
        """
        try:
            # ★ try 语句 = "尝试做这件事，看会不会出问题"
            
            # subprocess.run() = 运行一个命令行命令
            # 就像你在电脑的终端里输入一个命令
            # shell=True = 使用 shell（类似 Mac 的终端语言）
            # cwd=WORKDIR = 在指定文件夹中执行（就像改变终端位置）
            # capture_output=True = 捕获命令的输出（不是直接打印）
            # text=True = 输出变成文字而不是字节
            # timeout=300 = 最多等待300秒（5分钟），否则超时放弃
            r = subprocess.run(
                command, shell=True, cwd=WORKDIR,
                capture_output=True, text=True, timeout=300
            )
            
            # 获取输出信息
            # r.stdout = 命令的正常输出
            # r.stderr = 命令的错误输出
            # strip() = 去掉前后的空白（换行、空格等）
            # [:50000] = 只取前50000个字符（如果太长就截断，防止内存爆炸）
            output = (r.stdout + r.stderr).strip()[:50000]
            
            # 命令成功执行了
            status = "completed"
            
        except subprocess.TimeoutExpired:
            # ★ except = 如果出现了问题，就执行这部分
            
            # subprocess.TimeoutExpired = 命令运行超过300秒了
            # 就像你让朋友做一件事，5分钟后还没做完，你放弃了
            output = "Error: Timeout (300s)"
            status = "timeout"
            
        except Exception as e:
            # Exception = 任何其他类型的错误
            # e = 错误的信息
            # 比如：命令不存在、权限不足等等
            output = f"Error: {e}"
            status = "error"
        
        # 不管成功还是失败，都要更新记录
        # 更新自己的工作状态
        self.tasks[task_id]["status"] = status
        
        # 更新自己的工作结果
        self.tasks[task_id]["result"] = output or "(no output)"
        
        # ★ with self._lock: = "上锁，执行下面的代码，然后解锁"
        # 这样主线程不会在我们操作信箱时打开信箱
        # 反之亦然，非常安全
        with self._lock:
            # 把完成报告放进信箱
            # 经理或其他人之后会来看这个信箱
            self._notification_queue.append({
                "task_id": task_id,           # 这是哪个任务
                "status": status,             # 的工作状态
                "command": command[:80],      # 原本的命令是什么
                "result": (output or "(no output)")[:500],  # 结果是什么（截至500字符）
            })


    # ★★★ 查询任务状态 ★★★
    def check(self, task_id: str = None) -> str:
        """
        老板想知道："我的任务现在怎样了？"
        
        经理可以：
        1. 如果指定了任务ID：查询特定任务的状态
        2. 如果没有指定：列出所有任务的状态
        """
        
        if task_id:
            # 老板问："abc123任务怎么样了？"
            
            # self.tasks.get(task_id) = 在工作记录簿中找到这个任务
            # .get() 如果没找到会返回 None 而不是报错
            t = self.tasks.get(task_id)
            
            if not t:
                # 如果找不到这个任务
                return f"Error: Unknown task {task_id}"
            
            # 返回任务的详细信息：
            # [running] 表示状态
            # 命令是什么
            # 现在的结果是什么
            return f"[{t['status']}] {t['command'][:60]}\n{t.get('result') or '(running)'}"
        
        # 老板问："现在有哪些任务？"
        # 列出所有任务的简略信息
        
        lines = []  # 初始化一个空列表，用来放每行信息
        
        for tid, t in self.tasks.items():
            # 遍历所有任务
            # tid = 任务ID（比如"abc123"）
            # t = 这个任务的详细信息
            
            # 添加一行信息
            # 格式：任务ID: [状态] 命令
            lines.append(f"{tid}: [{t['status']}] {t['command'][:60]}")
        
        
        # 返回连接后的字符串或无任务消息
        return "\n".join(lines) if lines else "No background tasks."

    # ★★★ 最关键方法：获取所有完成的通知 ★★★
    def drain_notifications(self) -> list:
        """
        "排出"信箱里的所有完成报告
        
        这个方法很关键！因为：
        1. 代码在后台跑的时候，AI也在做其他事
        2. 后台线程会把完成的消息放进信箱
        3. AI每处理一个任务前，都会检查信箱
        4. 这个方法就是"一次性取出所有信件"
        
        比喻：
        - 你妈妈每天给你放零花钱在信箱里
        - 你每个星期看一次信箱，把所有零花钱取出来
        - drain_notifications 就是"让我一次取出所有零花钱"
        """
        
        # with self._lock: = 开始临界区，保护信箱
        with self._lock:
            # notifs = list(self._notification_queue)
            # 把信箱中的所有信件复制到 notifs
            # list() 创建一个副本，而不是直接使用原列表
            # （为了防止别的线程同时修改）
            notifs = list(self._notification_queue)
            
            # self._notification_queue.clear()
            # 清空信箱（把信件移出去）
            # 这样下一次就不会重复发送同样的通知
            self._notification_queue.clear()
        # 结束临界区，解锁
        
        # 返回所有通知（信件列表）
        return notifs


BG = BackgroundManager()
# ★ BG = 创建一个全局的后台任务管理器
# 所有地方都可以通过 BG 来访问它
# 比如：BG.run("命令") 就可以在后台执行命令


# ============ 第二部分：工具函数 ============
# 这些函数是 AI 可以使用的"工具"，就像一套工作工具

# 定义工具实现
def safe_path(p: str) -> Path:
    """
    安全路径检查 - 防止越狱攻击
    
    为什么需要这个？防止有人要求程序删除整个电脑的文件。
    比如某个坏人让AI执行："rm -rf /" （删除系统所有文件！）
    这个函数会检查："你想访问的路径，是否在允许的工作目录内"
    
    类比：你妈妈说"你可以用房间里的东西，但不能到其他房间"
         这个函数就是检查你是不是在自己房间内
    """
    
    # resolve() = 把相对路径变成绝对路径
    # 比如："./data.txt" -> "/Users/xx/learn-claude-code/data.txt"
    path = (WORKDIR / p).resolve()
    
    # is_relative_to() = 检查路径是否是工作目录的子路径
    # 比如：
    #   /Users/xx/learn-claude-code/data.txt ✓ （在内部）
    #   /etc/passwd ✗ （在外部）
    if not path.is_relative_to(WORKDIR):
        # 如果不在工作目录内，就拒绝访问
        raise ValueError(f"Path escapes workspace: {p}")
    
    # 返回被验证的安全路径
    return path


def run_bash(command: str) -> str:
    """
    运行一个 bash 命令（直接等待，不是后台）
    
    这用来做快速的、不需要太久的命令。
    如果是耗时命令，应该用 BG.run() 在后台执行。
    """
    
    # 定义一些危险命令列表
    # 这些命令会造成严重的损害
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    
    # any(d in command for d in dangerous)
    # 检查用户的命令中，是否包含任何危险命令
    # 这是一种安全防护措施
    if any(d in command for d in dangerous):
        # 如果包含危险命令，直接拒绝
        return "Error: Dangerous command blocked"
    
    try:
        # 尝试运行命令
        # timeout=120 = 最多等待 120 秒
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, text=True, timeout=120)
        
        # 提取输出
        # r.stdout = 命令的正常输出
        # r.stderr = 命令的错误输出
        out = (r.stdout + r.stderr).strip()
        
        # 返回输出（如果太长就截断到50000字符）
        return out[:50000] if out else "(no output)"
        
    except subprocess.TimeoutExpired:
        # 如果命令超过120秒还没完成，返回超时错误
        return "Error: Timeout (120s)"

def run_read(path: str, limit: int = None) -> str:
    """
    读取文件内容 - AI用来看文件里的内容
    
    比喻：翻开一本书来看里面的内容
    """
    try:
        # 使用安全路径读取文件
        # safe_path() 先检查这个路径是否安全
        # .read_text() 读取文件的所有内容为文本
        # .splitlines() 把文本按行分割成列表
        lines = safe_path(path).read_text().splitlines()
        
        # 如果设置了行数限制（比如只看前100行）
        if limit and limit < len(lines):
            # 从第 0 行到第 limit 行
            lines = lines[:limit]
            # 然后添加一行提示："还有 xxx 行没有显示"
            + [f"... ({len(lines) - limit} more)"]
        
        # 把所有行重新用 \n 连接起来
        # [:50000] 截断到50000字符（防止数据太大）
        return "\n".join(lines)[:50000]
        
    except Exception as e:
        # 如果出错（比如文件不存在）
        return f"Error: {e}"

def run_write(path: str, content: str) -> str:
    """
    写入内容到文件 - AI用来创建或覆盖文件
    
    比喻：拿一张白纸，写上内容，然后放进文件夹
    """
    try:
        # 获取安全路径
        fp = safe_path(path)
        
        # fp.parent = 父目录（比如文件是 a/b/c.txt，父目录就是 a/b/）
        # mkdir() = 创建目录
        # parents=True = 如果父目录的上级不存在，也一起创建
        # exist_ok=True = 如果目录已存在，不要报错
        fp.parent.mkdir(parents=True, exist_ok=True)
        
        # 把内容写入文件
        # 注意：这会覆盖原来的内容！
        fp.write_text(content)
        
        # 返回写入的字节数
        return f"Wrote {len(content)} bytes"
        
    except Exception as e:
        return f"Error: {e}"

def run_edit(path: str, old_text: str, new_text: str) -> str:
    """
    编辑文件 - 找到并替换某一段文本
    
    比喻：找到书里的一句话，用新的句子替换掉它
    """
    try:
        # 获取安全路径
        fp = safe_path(path)
        
        # 读取整个文件内容为字符串
        c = fp.read_text()
        
        # 检查旧文本是否存在
        if old_text not in c:
            # 如果不存在，无法替换
            return f"Error: Text not found in {path}"
        
        # c.replace(old_text, new_text, 1)
        # 把文本中的 old_text 替换成 new_text
        # 最后的 1 表示只替换第一个找到的
        # （如果是 0 或不写，就替换所有的）
        fp.write_text(c.replace(old_text, new_text, 1))
        
        # 返回成功消息
        return f"Edited {path}"
        
    except Exception as e:
        return f"Error: {e}"


# ============ 第三部分：注册工具 ============

# TOOL_HANDLERS = 工具处理器字典
# 当 AI 想使用工具时，会从这里的对应条目找到处理函数
# 
# lambda 和字典配合 - 这是 Python 的高级技巧
# 不用完全理解，只需知道：这是"快速定义函数"的方法
# 
# 例如：
#   "bash": lambda **kw: run_bash(kw["command"])
# 意思是："当 AI 说要用 bash 工具时，调用 run_bash 函数"

TOOL_HANDLERS = {
    # bash 工具 - 同步运行命令（AI会等待）
    "bash":             lambda **kw: run_bash(kw["command"]),
    
    # read_file 工具 - 读取文件（可选行数限制）
    "read_file":        lambda **kw: run_read(kw["path"], kw.get("limit")),
    
    # write_file 工具 - 写入文件
    "write_file":       lambda **kw: run_write(kw["path"], kw["content"]),
    
    # edit_file 工具 - 替换文件中的文本
    "edit_file":        lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    
    # ★ background_run 工具 - 在后台运行命令（AI不等待）
    # 这是这个程序的核心！AI可以立即安排任务然后继续工作
    "background_run":   lambda **kw: BG.run(kw["command"]),
    
    # check_background 工具 - 检查后台任务状态
    # 如果不提供 task_id，就列出所有任务
    "check_background": lambda **kw: BG.check(kw.get("task_id")),
}

TOOLS = [
    # ============ TOOLS 列表 ============
    # 这列定义了所有AI可以使用的工具
    # 每个工具都有：
    #   - name: 工具名称
    #   - description: 工具的描述（AI读这个来理解什么时候用这个工具）
    #   - input_schema: 输入的格式要求
    
    # 工具1：bash - 直接运行命令
    # "blocking" 意思是 AI 会等待命令完成才继续
    {"name": "bash", 
     "description": "Run a shell command (blocking 阻塞式).",
     "input_schema": {"type": "object", 
                      "properties": {"command": {"type": "string"}}, 
                      "required": ["command"]}},
    
    # 工具2：read_file - 读取文件
    # path: 必须的，文件路径
    # limit: 可选的，最多读几行
    {"name": "read_file", 
     "description": "Read file contents (读文件内容).",
     "input_schema": {"type": "object", 
                      "properties": {"path": {"type": "string"}, 
                                    "limit": {"type": "integer"}}, 
                      "required": ["path"]}},
    
    # 工具3：write_file - 写入文件
    # path: 必须的，文件路径
    # content: 必须的，要写入的内容
    {"name": "write_file", 
     "description": "Write content to file (写文件).",
     "input_schema": {"type": "object", 
                      "properties": {"path": {"type": "string"}, 
                                    "content": {"type": "string"}}, 
                      "required": ["path", "content"]}},
    
    # 工具4：edit_file - 编辑文件
    # 找到 old_text 替换成 new_text
    {"name": "edit_file", 
     "description": "Replace exact text in file (替换文件中的文本).",
     "input_schema": {"type": "object", 
                      "properties": {"path": {"type": "string"}, 
                                    "old_text": {"type": "string"}, 
                                    "new_text": {"type": "string"}}, 
                      "required": ["path", "old_text", "new_text"]}},
    
    # ★★★ 工具5：background_run - 后台运行命令 ★★★
    # 这是这个程序的核心工具！
    # 特别之处：不等待命令完成，立即返回 task_id
    # AI可以安排多个任务，然后继续工作
    {"name": "background_run", 
     "description": "Run command in background thread. Returns task_id immediately (后台运行，立即返回).",
     "input_schema": {"type": "object", 
                      "properties": {"command": {"type": "string"}}, 
                      "required": ["command"]}},
    
    # 工具6：check_background - 检查后台任务
    # task_id: 可选的，如果提供就查询这个任务，否则列出所有任务
    {"name": "check_background", 
     "description": "Check background task status. Omit task_id to list all (检查任务状态).",
     "input_schema": {"type": "object", 
                      "properties": {"task_id": {"type": "string"}}}},
]


# ============ 第四部分：代理循环 ============

def agent_loop(messages: list):
    """
    代理循环 - AI的"思维循环"
    
    这是整个程序的心脏！它不断重复这个过程：
    1. 排出后台通知（检查信箱）
    2. AI思考（调用 Anthropic API）
    3. AI使用工具（执行命令、读写文件等）
    4. 重复...
    
    类比：
    - 你读完邮件，然后思考接下来做什么
    - 你决定做几件事情
    - 你等待结果
    - 你再次读邮件，看看有没有新信息
    - 重复...
    """
    while True:
        # 无限循环，直到 AI 决定停止
        
        # ★ 关键步骤1：排出后台通知
        # "排出" = 取出所有完成的消息
        notifs = BG.drain_notifications()
        # 如果有通知（比如后台任务完成了），要告诉 AI
        
        if notifs and messages:
            # 如果有通知且消息列表不空
            
            # 把所有通知格式化成文本
            # 比如：[bg:abc123] completed: 运行结果...
            notif_text = "\n".join(
                f"[bg:{n['task_id']}] {n['status']}: {n['result']}" 
                for n in notifs
            )
            
            # 重要！把通知注入为"用户消息"
            # 这样 AI 可以看到后台任务的结果
            messages.append({
                "role": "user", 
                "content": f"<background-results>\n{notif_text}\n</background-results>"
            })
            
            # 然后"助手"回应"好的，我看到了"
            messages.append({
                "role": "assistant", 
                "content": "Noted background results."
            })
        
        # ★ 关键步骤2：让 AI 思考
        # 调用 Anthropic Claude AI 模型
        response = client.messages.create(
            model=MODEL,              # 使用哪个模型（比如 claude-3-5-sonnet）
            system=SYSTEM,            # 系统提示（AI的角色和指示）
            messages=messages,        # 对话历史
            tools=TOOLS,              # 告诉 AI 有哪些工具可用
            max_tokens=8000,          # 最多生成8000个 token（大约2000字）
        )
        
        # AI 的回复添加到消息历史
        messages.append({"role": "assistant", "content": response.content})
        
        # ★ 关键步骤3：检查 AI 是否要使用工具
        # response.stop_reason 告诉我们 AI 为什么停止回复
        # 可能的值：
        #   - "end_turn" = AI 说完了，对话结束
        #   - "tool_use" = AI 想使用工具
        if response.stop_reason != "tool_use":
            # 如果不是"要使用工具"，说明 AI 完成了题目，可以返回
            return
        
        # ★ 关键步骤4：处理 AI 请求的工具调用
        results = []
        # 初始化结果列表（用来放每个工具的执行结果）
        
        for block in response.content:
            # response.content 是一个列表，可能包含文本和工具调用
            
            if block.type == "tool_use":
                # 如果这块内容是"工具使用"
                
                # 从 TOOL_HANDLERS 字典中查找对应的处理函数
                # 比如 block.name = "bash"，就找到 run_bash 函数
                handler = TOOL_HANDLERS.get(block.name)
                
                try:
                    # 尝试执行工具
                    # block.input 包含了工具的参数
                    # 比如：{"command": "ls"}
                    output = (handler(**block.input) 
                              if handler 
                              else f"Unknown tool: {block.name}")
                    
                except Exception as e:
                    # 如果工具执行出错
                    output = f"Error: {e}"
                
                # 显示执行结果（前200字符）
                print(f"> {block.name}: {str(output)[:200]}")
                
                # 记录工具执行的结果
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,      # AI 引用的 ID
                    "content": str(output)        # 执行结果
                })
        
        # 把所有工具结果作为"用户消息"发送给 AI
        # 这样 AI 可以看到工具执行的结果，然后继续思考
        messages.append({"role": "user", "content": results})


# ============ 第五部分：主程序 - 用户交互 ============

if __name__ == "__main__":
    """
    主程序 - 这是程序的入口
    
    __name__ == "__main__" 是 Python 的习语
    意思是："只有当直接运行这个文件时，才执行这部分"
    如果这个文件被另一个程序导入，这部分不会运行
    
    程序流程：
    1. 显示彩色提示符
    2. 等待用户输入问题
    3. 启动 agent_loop 处理问题
    4. 显示 AI 的回复
    5. 重复...
    """
    
    # history = 消息历史
    # 这个列表会保持整个对话过程
    # 每次用户输入或 AI 回复，都会被添加到这里
    history = []
    
    while True:
        # 无限循环，保持对话
        
        try:
            # 尝试从终端获取用户输入
            # \033[36m ... \033[0m 是 ANSI 颜色代码，让提示符显示成青色
            query = input("\033[36ms08 >> \033[0m")
            
        except (EOFError, KeyboardInterrupt):
            # EOFError = 按下 Ctrl+D （文件结束）
            # KeyboardInterrupt = 按下 Ctrl+C （中断）
            # 两种情况都表示用户要退出
            break
        
        # 检查用户是否输入了退出命令
        if query.strip().lower() in ("q", "exit", ""):
            # strip() = 去掉前后空白
            # lower() = 转换为小写
            # 允许："q", "exit", 或者空行，都可以退出
            break
        
        # 把用户的问题添加到消息历史
        history.append({"role": "user", "content": query})
        
        # 调用 agent_loop 让 AI 处理这个问题
        # agent_loop 会修改 history（添加 AI 的回复和工具结果）
        agent_loop(history)
        
        # AI 处理完后，获取最后一条消息的内容
        # history[-1] = 历史列表中最后一项
        response_content = history[-1]["content"]
        
        # 检查内容是否是列表（列表表示包含多个块，可能混有文本和工具调用）
        if isinstance(response_content, list):
            # 遍历每一块内容
            for block in response_content:
                # hasattr(block, "text") = 检查 block 是否有"text"属性
                # 如果有，说明这是一个文本块
                if hasattr(block, "text"):
                    # 打印 AI 的文本回复
                    print(block.text)
        
        print()
        #打印空行，让输出看起来更整洁
