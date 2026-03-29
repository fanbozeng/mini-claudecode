#!/usr/bin/env python3
"""Minimal MCP runtime for the teaching agents.

This adapter keeps the existing agent loop unchanged. It discovers MCP tools
from external servers and forwards tool calls over stdio when needed.

The implementation intentionally reconnects per operation. That is slower than
keeping long-lived sessions, but it keeps the control flow easy to read for a
0->1 teaching project.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    MCP_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - depends on optional package
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None
    MCP_IMPORT_ERROR = exc


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class MCPToolBinding:
    prefixed_name: str
    server_name: str
    remote_name: str
    description: str
    input_schema: dict[str, Any]


class MCPRuntime:
    def __init__(self, workdir: Path, config_path: Path):
        self.workdir = workdir
        self.config_path = config_path
        self.import_error = MCP_IMPORT_ERROR
        self.config_error = None
        self.servers = self._load_config()
        self._tool_bindings: dict[str, MCPToolBinding] = {}
        self._tool_errors: list[str] = []
        if self.is_available():
            self.refresh_tools()

    def is_available(self) -> bool:
        return self.import_error is None

    def enabled(self) -> bool:
        return bool(self.servers) and self.is_available()

    def describe_servers(self) -> str:
        if self.import_error:
            return f"(mcp package unavailable: {self.import_error})"
        if self.config_error:
            return f"(invalid MCP config: {self.config_error})"
        if not self.config_path.exists():
            return f"(no MCP config at {self.config_path.name})"
        if not self.servers:
            return "(no MCP servers configured)"
        lines = []
        for server in self.servers:
            cmd = " ".join([server.command, *server.args]).strip()
            lines.append(f"  - {server.name}: {cmd}")
        return "\n".join(lines)

    def describe_tools(self) -> str:
        if self._tool_errors:
            return "\n".join(f"  - {msg}" for msg in self._tool_errors)
        if not self._tool_bindings:
            return "(no MCP tools loaded)"
        return "\n".join(
            f"  - {binding.prefixed_name}: {binding.description}"
            for binding in self._tool_bindings.values()
        )

    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "name": binding.prefixed_name,
                "description": binding.description,
                "input_schema": binding.input_schema,
            }
            for binding in self._tool_bindings.values()
        ]

    def has_tool(self, name: str) -> bool:
        return name in self._tool_bindings

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        binding = self._tool_bindings.get(name)
        if not binding:
            return f"Unknown MCP tool: {name}"
        server = next((item for item in self.servers if item.name == binding.server_name), None)
        if server is None:
            return f"Error: MCP server '{binding.server_name}' is no longer configured"
        try:
            result = asyncio.run(
                self._call_remote_tool(server, binding.remote_name, arguments)
            )
            return self._render_tool_result(result)
        except Exception as exc:
            return f"Error calling MCP tool '{name}': {exc}"

    def refresh_tools(self):
        self._tool_bindings = {}
        self._tool_errors = []
        for server in self.servers:
            try:
                tools = asyncio.run(self._list_remote_tools(server))
            except Exception as exc:
                self._tool_errors.append(f"{server.name}: {exc}")
                continue
            for tool in tools:
                remote_name = self._value(tool, "name", "")
                if not remote_name:
                    continue
                prefixed_name = self._prefixed_name(server.name, remote_name)
                description = self._value(tool, "description", "") or f"MCP tool '{remote_name}' from '{server.name}'"
                input_schema = self._value(tool, "inputSchema", {}) or {"type": "object", "properties": {}}
                self._tool_bindings[prefixed_name] = MCPToolBinding(
                    prefixed_name=prefixed_name,
                    server_name=server.name,
                    remote_name=remote_name,
                    description=f"[MCP:{server.name}] {description}",
                    input_schema=input_schema,
                )

    def _load_config(self) -> list[MCPServerConfig]:
        if not self.config_path.exists():
            return []
        try:
            raw = json.loads(self.config_path.read_text())
        except Exception as exc:
            self.config_error = str(exc)
            return []
        items = raw.get("servers", [])
        servers = []
        for item in items:
            name = str(item.get("name", "")).strip()
            command = self._expand(str(item.get("command", "")).strip())
            args = [self._expand(str(arg)) for arg in item.get("args", [])]
            env = {str(k): self._expand(str(v)) for k, v in item.get("env", {}).items()}
            if name and command:
                servers.append(MCPServerConfig(name=name, command=command, args=args, env=env))
        return servers

    def _expand(self, value: str) -> str:
        expanded = os.path.expandvars(value)
        if expanded.startswith("./") or expanded.startswith("../"):
            return str((self.workdir / expanded).resolve())
        return expanded

    def _prefixed_name(self, server_name: str, remote_name: str) -> str:
        return f"mcp__{server_name}__{remote_name}"

    def _server_params(self, server: MCPServerConfig):
        env = os.environ.copy()
        env.update(server.env)
        return StdioServerParameters(
            command=server.command,
            args=server.args,
            env=env,
        )

    async def _list_remote_tools(self, server: MCPServerConfig):
        async with stdio_client(self._server_params(server)) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                return list(getattr(result, "tools", []))

    async def _call_remote_tool(self, server: MCPServerConfig, tool_name: str, arguments: dict[str, Any]):
        async with stdio_client(self._server_params(server)) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(tool_name, arguments=arguments)

    def _value(self, obj: Any, attr: str, default: Any) -> Any:
        if hasattr(obj, attr):
            return getattr(obj, attr)
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return default

    def _render_tool_result(self, result: Any) -> str:
        parts = []
        structured = getattr(result, "structuredContent", None)
        if structured not in (None, {}, []):
            parts.append(json.dumps(structured, ensure_ascii=False, indent=2))
        for content in getattr(result, "content", []):
            text = getattr(content, "text", None)
            if text is not None:
                parts.append(text)
                continue
            resource = getattr(content, "resource", None)
            if resource is not None:
                uri = getattr(resource, "uri", "embedded://resource")
                resource_text = getattr(resource, "text", None)
                if resource_text is not None:
                    parts.append(f"[resource] {uri}\n{resource_text}")
                else:
                    parts.append(f"[resource] {uri}")
                continue
            mime_type = getattr(content, "mimeType", None)
            data = getattr(content, "data", None)
            if mime_type and data is not None:
                parts.append(f"[binary content: {mime_type}, {len(data)} bytes]")
                continue
            parts.append(str(content))
        if not parts:
            parts.append("(no content)")
        text = "\n".join(parts)
        if getattr(result, "isError", False):
            return f"Error from MCP tool:\n{text}"
        return text
