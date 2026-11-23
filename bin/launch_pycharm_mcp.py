#!/usr/bin/env python3
"""Launch PyCharm's built-in stdio MCP server using the local studio config."""

import json
import os
import subprocess
import sys
from pathlib import Path


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


def main() -> int:
    cfg = load_config()
    exe_raw = os.environ.get("PYCHARM_EXE") or cfg.get("pycharm_exe")
    if not exe_raw:
        fail("pycharm_exe is not configured. Run scripts/setup.py --pycharm-exe <path>.")
    exe = Path(exe_raw).expanduser()
    if not exe.is_file():
        fail(f"PyCharm executable not found: {exe}")

    project_raw = cfg.get("pycharm_project") or cfg.get("comfyui_dir")
    if not project_raw:
        fail("pycharm_project is not configured.")
    project = Path(project_raw).expanduser()

    env = os.environ.copy()
    env["IJ_MCP_SERVER_PROJECT_PATH"] = str(project)
    env["IJ_MCP_SERVER_PORT"] = str(cfg.get("pycharm_port") or 64462)
    env["PYTHONUTF8"] = "1"

    proc = subprocess.Popen([str(exe), "stdioMcpServer"], cwd=str(project) if project.is_dir() else None, env=env)
    return proc.wait()


if __name__ == "__main__":
    raise SystemExit(main())
