#!/usr/bin/env python3
"""Smoke-test the PyCharm SSE bridge by running a command in the IDE terminal."""

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def config_path() -> Path:
    raw = os.environ.get("COMFYUI_STUDIO_CONFIG", "~/.comfyui-studio/config.json")
    return Path(raw).expanduser()


def load_config() -> dict:
    path = config_path()
    if not path.is_file():
        raise SystemExit(f"missing config: {path}; run scripts/setup.py first")
    return json.loads(path.read_text(encoding="utf-8"))


class Client:
    def __init__(self, python: str):
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        self.proc = subprocess.Popen(
            [python, str(ROOT / "bin" / "launch_pycharm_mcp.py")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
        )
        self.lines = queue.Queue()
        self.stderr = []
        self.next_id = 0
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self):
        for line in self.proc.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def _read_stderr(self):
        for line in self.proc.stderr:
            self.stderr.append(line)

    def request(self, method, params=None, timeout=60):
        self.next_id += 1
        request_id = self.next_id
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self.proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"{method} timed out after {timeout}s")
            try:
                line = self.lines.get(timeout=min(remaining, 5))
            except queue.Empty:
                continue
            if line is None:
                raise RuntimeError(f"bridge closed stdout during {method}; stderr: {''.join(self.stderr[-20:])}")
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(f"{method}: {message['error']}")
            return message["result"]

    def notify(self, method):
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.proc.stdin.flush()

    def call(self, tool, arguments=None, timeout=120):
        return self.request("tools/call", {"name": tool, "arguments": arguments or {}}, timeout=timeout)

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command", default="echo PyCharmBridge_OK", help="command to run in the IDE terminal")
    parser.add_argument("--timeout", type=int, default=15000, help="IDE terminal timeout in milliseconds")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    cfg = load_config()
    client = Client(cfg.get("venv_python") or sys.executable)
    try:
        init = client.request(
            "initialize",
            {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "comfyui-studio-pycharm-smoke", "version": "0.1"}},
            timeout=30,
        )
        print("server:", init.get("serverInfo"))
        client.notify("notifications/initialized")
        tools = client.request("tools/list", {}, timeout=30)
        print("tools:", [tool["name"] for tool in tools.get("tools", [])])

        command = args.command.replace('"', '\\"')
        arguments = {"command": f'execute_terminal_command --command "{command}" --timeout {args.timeout}'}
        project = cfg.get("pycharm_project")
        if project:
            arguments["projectPath"] = project
        result = client.call("execute_tool", arguments, timeout=max(120, args.timeout // 1000 + 60))
        print("isError:", result.get("isError"))
        text = "\n".join(item.get("text", "") for item in result.get("content", []) if item.get("type") == "text")
        print(text[:4000])
        if result.get("isError"):
            return 1
        try:
            payload = json.loads(text)
        except ValueError:
            return 0
        return 0 if payload.get("command_exit_code") == 0 else 1
    except Exception as exc:
        print(f"\n[FAIL] {type(exc).__name__}: {exc}")
        print("\n[stderr tail]\n" + "".join(client.stderr[-40:]))
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
