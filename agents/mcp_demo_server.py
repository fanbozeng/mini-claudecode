#!/usr/bin/env python3
"""A tiny MCP server for this repository.

This gives the teaching agent a real external server to connect to when you
want to try MCP locally.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

WORKDIR = Path(__file__).resolve().parents[1]
mcp = FastMCP("learn-claude-code-demo", json_response=True)


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@mcp.tool()
def list_course_docs(locale: str = "zh") -> list[str]:
    """List available lesson docs for a locale such as zh, en, or ja."""
    docs_dir = WORKDIR / "docs" / locale
    if not docs_dir.exists():
        return []
    return sorted(path.name for path in docs_dir.glob("*.md"))


@mcp.tool()
def read_course_doc(version: str, locale: str = "zh") -> str:
    """Read one lesson document by version, for example s05 or s12."""
    path = WORKDIR / "docs" / locale / f"{version}.md"
    if not path.exists():
        return f"Document not found: docs/{locale}/{version}.md"
    return path.read_text()[:12000]


@mcp.tool()
def repo_overview() -> dict:
    """Return a compact overview of this repository."""
    return {
        "root": str(WORKDIR),
        "agents": sorted(path.name for path in (WORKDIR / "agents").glob("*.py")),
        "skills": sorted(path.parent.name for path in (WORKDIR / "skills").glob("*/SKILL.md")),
        "docs_locales": sorted(path.name for path in (WORKDIR / "docs").iterdir() if path.is_dir()),
    }


@mcp.tool()
def read_readme(locale: str = "zh") -> str:
    """Read the main README in zh, en, or ja."""
    mapping = {"zh": "README-zh.md", "en": "README.md", "ja": "README-ja.md"}
    filename = mapping.get(locale, "README-zh.md")
    return (WORKDIR / filename).read_text()[:12000]


@mcp.resource("repo://overview")
def get_repo_overview_resource() -> str:
    """Read-only repo overview as a JSON resource."""
    return json.dumps(repo_overview(), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
