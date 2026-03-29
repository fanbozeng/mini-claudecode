#!/usr/bin/env python3
# 指定使用 Python 3 解释器运行此脚本
# Harness: on-demand knowledge -- domain expertise, loaded when the model asks.
"""
s05_skill_loading.py - Skills

Two-layer skill injection that avoids bloating the system prompt:

    Layer 1 (cheap): skill names in system prompt (~100 tokens/skill)
    Layer 2 (on demand): full skill body in tool_result

    skills/
      pdf/
        SKILL.md          <-- frontmatter (name, description) + body
      code-review/
        SKILL.md

    System prompt:
    +--------------------------------------+
    | You are a coding agent.              |
    | Skills available:                    |
    |   - pdf: Process PDF files...        |  <-- Layer 1: metadata only
    |   - code-review: Review code...      |
    +--------------------------------------+

    When model calls load_skill("pdf"):
    +--------------------------------------+
    | tool_result:                         |
    | <skill>                              |
    |   Full PDF processing instructions   |  <-- Layer 2: full body
    |   Step 1: ...                        |
    |   Step 2: ...                        |
    | </skill>                             |
    +--------------------------------------+

Key insight: "Don't put everything in the system prompt. Load on demand."
"""

# 导入操作系统接口模块，用于环境变量和路径操作
import os
# 导入正则表达式模块，用于解析 YAML frontmatter
import re
# 导入子进程模块，用于运行外部命令
import subprocess
# 导入路径模块，提供面向对象的文件系统路径操作
from pathlib import Path

# 导入 Anthropic AI 客户端，用于与 AI 模型交互
from anthropic import Anthropic
# 导入 dotenv 模块，用于从 .env 文件加载环境变量
from dotenv import load_dotenv

try:
    from agents.mcp_runtime import MCPRuntime
except ImportError:
    from mcp_runtime import MCPRuntime

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
# 设置技能目录路径
SKILLS_DIR = WORKDIR / "skills"
MCP_CONFIG_PATH = WORKDIR / os.getenv("MCP_CONFIG_PATH", "mcp_servers.json")


# -- SkillLoader: scan skills/<name>/SKILL.md with YAML frontmatter --
# 定义 SkillLoader 类，用于扫描 skills/<name>/SKILL.md 文件，包含 YAML frontmatter
class SkillLoader:
    # 初始化方法，传入技能目录路径
    def __init__(self, skills_dir: Path):
        # 设置技能目录
        self.skills_dir = skills_dir
        # 初始化技能字典
        self.skills = {}
        # 加载所有技能
        self._load_all()

    # 私有方法，加载所有技能
    def _load_all(self):
        # 如果技能目录不存在，返回
        if not self.skills_dir.exists():
            return
        # 遍历所有 SKILL.md 文件，按排序
        for f in sorted(self.skills_dir.rglob("SKILL.md")):
            # 读取文件内容
            text = f.read_text()
            # 解析 frontmatter 和 body
            meta, body = self._parse_frontmatter(text)
            # 获取技能名称，默认使用父目录名
            name = meta.get("name", f.parent.name)
            # 将技能信息存储在字典中
            self.skills[name] = {"meta": meta, "body": body, "path": str(f)}

    # 私有方法，解析 YAML frontmatter
    def _parse_frontmatter(self, text: str) -> tuple:
        """Parse YAML frontmatter between --- delimiters."""
        # 使用正则表达式匹配 --- 分隔符之间的内容
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        # 如果不匹配，返回空元数据和原始文本
        if not match:
            return {}, text
        # 初始化元数据字典
        meta = {}
        # 遍历 frontmatter 的每一行
        for line in match.group(1).strip().splitlines():
            # 如果行包含冒号，分割键值对
            if ":" in line:
                key, val = line.split(":", 1)
                # 去除空白并存储
                meta[key.strip()] = val.strip()
        # 返回元数据和 body
        return meta, match.group(2).strip()

    # 获取描述的方法，用于系统提示的 Layer 1
    def get_descriptions(self) -> str:
        """Layer 1: short descriptions for the system prompt."""
        # 如果没有技能，返回无技能消息
        if not self.skills:
            return "(no skills available)"
        # 初始化行列表
        lines = []
        # 遍历每个技能
        for name, skill in self.skills.items():
            # 获取描述，默认无描述
            desc = skill["meta"].get("description", "No description")
            # 获取标签
            tags = skill["meta"].get("tags", "")
            # 构建行字符串
            line = f"  - {name}: {desc}"
            # 如果有标签，添加标签
            if tags:
                line += f" [{tags}]"
            # 添加到行列表
            lines.append(line)
        # 返回连接后的字符串
        return "\n".join(lines)

    # 获取内容的方法，用于工具结果的 Layer 2
    def get_content(self, name: str) -> str:
        """Layer 2: full skill body returned in tool_result."""
        # 获取指定名称的技能
        skill = self.skills.get(name)
        # 如果不存在，返回错误消息
        if not skill:
            return f"Error: Unknown skill '{name}'. Available: {', '.join(self.skills.keys())}"
        # 返回包装在 <skill> 标签中的 body
        return f"<skill name=\"{name}\">\n{skill['body']}\n</skill>"


# 创建 SkillLoader 实例，传入技能目录
SKILL_LOADER = SkillLoader(SKILLS_DIR)
MCP = MCPRuntime(WORKDIR, MCP_CONFIG_PATH)

# Layer 1: skill metadata injected into system prompt
# 定义系统提示，将技能元数据注入系统提示的 Layer 1
SYSTEM = f"""You are a coding agent at {WORKDIR}.
Use load_skill to access specialized knowledge before tackling unfamiliar topics.
Use MCP tools when an external integration is a better fit than local shell/file access.

Skills available:
{SKILL_LOADER.get_descriptions()}

MCP servers:
{MCP.describe_servers()}

MCP tools:
{MCP.describe_tools()}"""


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

def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        # 获取安全路径
        fp = safe_path(path)
        # 读取文件内容
        content = fp.read_text()
        # 检查旧文本是否存在于内容中
        if old_text not in content:
            # 如果不存在，返回未找到错误消息
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
    "load_skill": lambda **kw: SKILL_LOADER.get_content(kw["name"]),  # load_skill 工具：加载技能内容
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
    {"name": "load_skill", "description": "Load specialized knowledge by name.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string", "description": "Skill name to load"}}, "required": ["name"]}},
] + MCP.tool_schemas()


def agent_loop(messages: list):
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return
        results = []
        for block in response.content:
            if block.type == "tool_use":
                handler = TOOL_HANDLERS.get(block.name)
                try:
                    if handler:
                        output = handler(**block.input)
                    elif MCP.has_tool(block.name):
                        output = MCP.call_tool(block.name, block.input)
                    else:
                        output = f"Unknown tool: {block.name}"
                except Exception as e:
                    # 捕获异常
                    output = f"Error: {e}"
                # 打印工具名称和输出前200字符
                print(f"> {block.name}: {str(output)[:200]}")
                # 添加工具结果到结果列表
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)})
        # 将结果作为用户消息添加到消息列表
        messages.append({"role": "user", "content": results})


# 如果作为主程序运行
if __name__ == "__main__":
    # 初始化历史消息列表
    history = []
    # 无限循环，等待用户输入
    while True:
        try:
            # 获取用户输入，带颜色提示
            query = input("\033[36ms05 >> \033[0m")
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
