#!/usr/bin/env python3
"""Bridge stdio MCP to PyCharm's built-in SSE MCP server.

PyCharm's launcher can carry a RUNASADMIN compatibility flag, so spawning
`pycharm64.exe stdioMcpServer` from a normal process fails with WinError 740.
The IDE's built-in web server exposes the same MCP tools over SSE, which works
without elevation.
"""

import json
import os
import sys
from pathlib import Path

import anyio
import mcp.types as types
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

PROXY_ENV = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)


def config_path() -> Path:
    raw = os.environ.get("COMFYUI_STUDIO_CONFIG", "~/.comfyui-studio/config.json")
    return Path(raw).expanduser()


def fail(message: str) -> None:
    print(f"[comfyui-studio] {message}", file=sys.stderr, flush=True)
    raise SystemExit(2)


def load_config() -> dict:
    path = config_path()
    if not path.is_file():
        fail(f"missing config: {path}. Run scripts/setup.py first.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail(f"cannot read config {path}: {exc}")


def root_error(exc: BaseException) -> BaseException:
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return exc


async def run_bridge(port: int) -> None:
    url = f"http://127.0.0.1:{port}/sse"
    # httpx fails to parse bracketed IPv6 entries such as "[::1]" in NO_PROXY
    for key in PROXY_ENV:
        os.environ.pop(key, None)

    async with sse_client(url) as (read, write):
        async with ClientSession(read, write) as remote:
            await remote.initialize()
            listing = await remote.list_tools()

            server = Server("pycharm-mcp-bridge", version="0.2.0")

            @server.list_tools()
            async def list_tools() -> list[types.Tool]:
                return listing.tools

            @server.call_tool()
            async def call_tool(name: str, arguments: dict | None) -> types.CallToolResult:
                return await remote.call_tool(name, arguments or {}, read_timeout_seconds=None)

            async with stdio_server() as (stdin, stdout):
                await server.run(stdin, stdout, server.create_initialization_options())


def main() -> int:
    cfg = load_config()
    port = int(cfg.get("pycharm_port") or 64462)
    try:
        anyio.run(run_bridge, port)
    except BaseException as exc:
        cause = root_error(exc)
        fail(
            f"cannot reach the PyCharm MCP server on 127.0.0.1:{port} ({cause}). "
            "Start PyCharm with the project open and check pycharm_port in "
            f"{config_path()}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
