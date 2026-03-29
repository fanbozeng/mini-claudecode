#!/usr/bin/env python3
# 标准Python脚本头：指定使用/usr/bin/env中的python3解释器
# Harness: the loop -- the model's first connection to the real world.
"""
s01_agent_loop.py - 代理循环/AI代理的核心实现

AI编码代理的核心秘密就在这一个模式中：

    while stop_reason == "tool_use":  # 只要模型返回工具调用停止原因
        response = LLM(messages, tools)  # 调用LLM，传入历史消息和工具定义
        execute tools  # 执行模型所请求的工具（如bash命令）
        append results  # 将结果追加到消息历史

    +----------+      +-------+      +---------+
    |   User   | ---> |  LLM  | ---> |  Tool   |
    |  prompt  |      |       |      | execute |
    +----------+      +---+---+      +----+----+
                          ^               |
                          |   tool_result |  工具结果返回给LLM
                          +---------------+
                          (循环继续)

这是核心循环：将工具结果反馈给模型，
直到模型决定停止（stop_reason变为"end_turn"或其他）。
生产级代理会在此基础上增加策略、钩子和生命周期控制。
"""

# 导入操作系统相关功能（获取环境变量、当前工作目录等）
import os
# 导入subprocess用于执行shell命令并捕获输出
import subprocess

# 从anthropic库导入Anthropic类（官方Python SDK客户端）
from anthropic import Anthropic
# 从dotenv导入load_dotenv函数（加载.env文件中的环境变量）
from dotenv import load_dotenv

# 加载.env文件中的所有环境变量到os.environ（override=True表示覆盖现有变量）
load_dotenv(override=True)

# 条件语句：如果设置了自定义的ANTHROPIC_BASE_URL（如本地服务）
if os.getenv("ANTHROPIC_BASE_URL"):
    # 移除认证令牌，因为自定义服务可能不需要或使用不同的认证方式
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

# 创建Anthropic API客户端实例
# base_url参数允许连接到自定义的API服务（如本地部署、反向代理等）
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
# 从环境变量读取模型ID（如"claude-3-5-sonnet-20241022"）
MODEL = os.environ["MODEL_ID"]

# 定义系统提示词（system prompt）：指导模型的角色和行为
# f-string会在当前工作目录插入实际路径信息
SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."

# 定义模型可用的工具列表（这里只定义bash工具）
# 这个列表会发送给LLM，告诉它可以调用什么工具
TOOLS = [{
    # 工具名称，模型会使用这个名字来调用该工具
    "name": "bash",
    # 工具描述，帮助模型理解何时使用该工具
    "description": "Run a shell command.",
    # JSON Schema定义：描述工具的输入参数格式
    "input_schema": {
        # 这是一个对象（dict）类型的输入
        "type": "object",
        # 定义对象的属性（字段）
        "properties": {
            # command属性：必须是字符串类型，用户想要执行的shell命令
            "command": {"type": "string"}
        },
        # 指定command字段是必需的（模型调用此工具时必须提供）
        "required": ["command"],
    },
}]


# 定义bash命令执行函数
def run_bash(command: str) -> str:
    # 危险命令黑名单：包含可能破坏系统的操作
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    # 检查命令是否包含危险操作，如果包含则拒绝执行
    if any(d in command for d in dangerous):
        # 返回错误信息而不是真正执行危险命令
        return "Error: Dangerous command blocked"
    try:
        # 使用subprocess.run执行shell命令
        # shell=True: 允许执行复杂的shell命令（包括管道、重定向等）
        # cwd=os.getcwd(): 在当前工作目录执行命令
        # capture_output=True: 捕获stdout和stderr
        # text=True: 以文本模式返回输出（而不是字节）
        # timeout=120: 命令最多执行120秒，防止无限循环
        r = subprocess.run(command, shell=True, cwd=os.getcwd(),
                           capture_output=True, text=True, timeout=120)
        # 合并标准输出和错误输出，并去掉首尾空白字符
        out = (r.stdout + r.stderr).strip()
        # 限制输出大小至50000字符，避免响应过长；如果没有输出则返回提示符
        return out[:50000] if out else "(no output)"
    # 捕获超时异常（命令执行超过120秒）
    except subprocess.TimeoutExpired:
        # 返回超时错误信息
        return "Error: Timeout (120s)"


# -- 核心模式：循环调用工具直到模型停止 --
def agent_loop(messages: list):
    # 无限循环：持续与LLM交互直到模型给出最终答案
    while True:
        # 调用Claude API，传入消息历史、系统提示、工具列表
        response = client.messages.create(
            # 使用环境变量中指定的模型
            model=MODEL,
            # 系统角色定义：指导模型充当编码代理
            system=SYSTEM,
            # 消息历史：包含之前所有的用户输入和助手回复
            messages=messages,
            # 可用工具列表：告诉模型它可以调用哪些工具
            tools=TOOLS,
            # 最大令牌数：限制每次响应的长度
            max_tokens=8000,
        )
        # 将助手的回复添加到消息历史（保留完整的对话上下文）
        messages.append({"role": "assistant", "content": response.content})
        # 检查停止原因：判断模型是否还要继续调用工具
        # 如果stop_reason不是"tool_use"，说明模型已完成任务（通常是"end_turn"）
        if response.stop_reason != "tool_use":
            # 退出循环，返回主程序
            return
        # 初始化结果列表：用于收集所有工具调用的执行结果
        results = []
        # 遍历LLM响应中的内容块（可能包含文本、工具调用等）
        for block in response.content:
            # 检查当前内容块是否是工具调用类型
            if block.type == "tool_use":
                # 打印执行的命令（ANSI黄色文本：\033[33m...黄色...\033[0m）
                print(f"\033[33m$ {block.input['command']}\033[0m")
                # 执行bash命令并捕获输出
                output = run_bash(block.input["command"])
                # 打印输出的前200个字符（用于调试和用户反馈）
                print(output[:200])
                # 将工具执行结果添加到结果列表
                results.append({
                    # 标识为工具结果
                    "type": "tool_result",
                    # 工具调用的唯一ID（LLM使用此ID关联后续操作）
                    "tool_use_id": block.id,
                    # 工具的实际执行输出
                    "content": output
                })
        # 将所有工具结果作为用户消息添加回消息历史
        # 这使得LLM可以看到工具执行的结果并据此继续推理
        messages.append({"role": "user", "content": results})


# 程序入口点：仅当此文件被直接执行时运行（不是被import时）
if __name__ == "__main__":
    # 初始化消息历史列表：用于存储整个对话的消息序列
    history = []
    # 外层无限循环：允许用户进行多轮交互（输入多个问题）
    while True:
        try:
            # 获取用户输入（ANSI青色提示符：\033[36m...青色...\033[0m）
            query = input("\033[36ms01 >> \033[0m")
        # 捕获文件结束符（Ctrl+D在终端中投入）或键盘中断（Ctrl+C）
        except (EOFError, KeyboardInterrupt):
            # 正确退出程序
            break
        # 检查退出条件：如果输入为"q"、"exit"或空行
        # strip()移除首尾空白，lower()转换为小写进行比较
        if query.strip().lower() in ("q", "exit", ""):
            # 退出程序
            break
        # 将用户输入作为消息添加到历史（角色为"user"）
        history.append({"role": "user", "content": query})
        # 调用代理循环处理用户的任务
        agent_loop(history)
        # 提取最后一条消息的内容（应该是助手的回复）
        response_content = history[-1]["content"]
        # 检查响应内容是否为列表类型（可能包含多个内容块）
        if isinstance(response_content, list):
            # 遍历所有内容块
            for block in response_content:
                # 检查该内容块是否有text属性（即文本块）
                if hasattr(block, "text"):
                    # 打印文本内容
                    print(block.text)
        # 打印空行，用于分隔不同的对话轮次
        print()
