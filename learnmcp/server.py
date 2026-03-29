from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("learnmcp-python-demo", log_level="ERROR")
OUTPUT_DIR = Path(__file__).parent / "demo-output"

INTRO_MARKDOWN = """# MCP 一句话解释

MCP = 一个统一协议，让 AI Client 能发现并调用外部能力。

## 你可以把它理解成三层

1. Client
   比如 Claude Desktop、IDE 插件、你自己写的 Agent。
2. Server
   你自己暴露能力的地方，里面可以注册 tool、resource、prompt。
3. Transport
   Client 和 Server 怎么通信。这个 demo 用的是 stdio。

## MCP 里最核心的三类能力

- Tool: 让模型“做事”，比如计算、写文件、调用接口
- Resource: 让模型“读上下文”，比如文档、配置、知识库
- Prompt: 让模型“拿模板”，比如固定问法、工作流入口

## 记忆口诀

Resource 是给模型看的资料
Prompt 是给模型用的模板
Tool 是给模型调用的动作
"""


class StudyStep(TypedDict):
    day: int
    focus: str
    exercise: str


class StudyPlan(TypedDict):
    goal: str
    total_days: int
    steps: list[StudyStep]


@mcp.resource("learnmcp://guide/intro")
def mcp_intro() -> str:
    """一份专门给这个 demo 准备的 MCP 核心概念说明。"""
    return INTRO_MARKDOWN


@mcp.prompt()
def teach_mcp(learner_name: str, topic: str) -> str:
    """生成一个适合初学者的 MCP 讲解提示词。"""
    return (
        f"你是一名循序渐进的导师。请向 {learner_name} 解释 {topic}，"
        "并使用“概念 -> 类比 -> 一个最小例子 -> 常见坑”的结构。"
    )


@mcp.tool()
def plan_mcp_learning(goal: str, days: int) -> StudyPlan:
    """根据学习目标生成一个几天的 MCP 学习计划。"""
    if not 1 <= days <= 7:
        raise ValueError("days 必须在 1 到 7 之间")

    focuses = [
        {
            "focus": "理解 Client、Server、Transport 的关系",
            "exercise": "画出一次 tool call 的调用链",
        },
        {
            "focus": "区分 Tool、Resource、Prompt",
            "exercise": "为自己的项目各举一个例子",
        },
        {
            "focus": "阅读并修改 MCP Server 代码",
            "exercise": "新增一个返回结构化结果的 tool",
        },
        {
            "focus": "写一个最小 Client 去调用 Server",
            "exercise": "用 list_tools 和 call_tool 跑通一次请求",
        },
        {
            "focus": "把 MCP 接到真实场景",
            "exercise": "思考一个你常做的重复任务，设计成 MCP tool",
        },
        {
            "focus": "补充错误处理和日志",
            "exercise": "让 tool 在非法参数下返回清晰错误",
        },
        {
            "focus": "复盘与扩展",
            "exercise": "再加一个 resource 或 prompt，巩固心智模型",
        },
    ]

    steps: list[StudyStep] = []
    for index in range(days):
        item = focuses[index]
        steps.append(
            {
                "day": index + 1,
                "focus": item["focus"],
                "exercise": item["exercise"],
            }
        )

    return {
        "goal": goal,
        "total_days": days,
        "steps": steps,
    }


@mcp.tool()
def save_learning_note(title: str, content: str) -> str:
    """把一段学习总结写入本地文件，模拟 tool 的副作用。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = slugify(title)
    file_path = OUTPUT_DIR / f"{safe_name}.md"
    file_path.write_text(f"# {title}\n\n{content}\n", encoding="utf-8")
    return f"笔记已保存到 {file_path}"


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    chars = [char if char.isalnum() else "-" for char in lowered]
    normalized = "".join(chars).strip("-")
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized or "mcp-note"


if __name__ == "__main__":
    mcp.run(transport="stdio")
