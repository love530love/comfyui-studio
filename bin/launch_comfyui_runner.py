#!/usr/bin/env python3
"""Launch the comfyui-runner MCP server using the local studio config.

The MCP client starts this stdlib-only launcher with `python`. The launcher
reads ~/.comfyui-studio/config.json (or COMFYUI_STUDIO_CONFIG), then hands the
process over to ComfyUI's own interpreter so the runner inherits its venv.
All stdio handles are inherited, so the MCP transport stays with the client.
"""

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


def resolve_python(cfg: dict, root: Path) -> Path:
    raw = os.environ.get("COMFYUI_PYTHON") or cfg.get("venv_python")
    if raw:
        candidate = Path(raw).expanduser()
    elif os.name == "nt":
        candidate = root / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = root / ".venv" / "bin" / "python"
    if not candidate.is_file():
        fail(f"ComfyUI interpreter not found: {candidate}")
    return candidate


def main() -> int:
    cfg = load_config()
    root = Path(cfg.get("comfyui_dir", "")).expanduser()
    if not (root / "main.py").is_file():
        fail(f"comfyui_dir is not a ComfyUI checkout: {root}")

    server_raw = os.environ.get("COMFYUI_RUNNER_SERVER") or cfg.get("runner_server")
    if not server_raw:
        fail("runner_server is not configured. Run scripts/setup.py --runner-server <path/to/server.py>.")
    server = Path(server_raw).expanduser()
    if not server.is_file():
        fail(f"runner server not found: {server}")

    python = resolve_python(cfg, root)
    env = os.environ.copy()
    env["COMFYUI_DIR"] = str(root)
    env["COMFYUI_HOST"] = str(cfg.get("comfyui_host") or "127.0.0.1")
    env["PYTHONUTF8"] = "1"
    if cfg.get("comfyui_port"):
        env["COMFYUI_PORT"] = str(cfg["comfyui_port"])
    if cfg.get("comfyui_start_args"):
        env["COMFYUI_START_ARGS"] = str(cfg["comfyui_start_args"])
    for key, env_name in (
        ("comfyui_vsdev", "COMFYUI_VSDEV"),
        ("comfyui_admin", "COMFYUI_ADMIN"),
    ):
        if key in cfg:
            env[env_name] = "1" if cfg[key] else "0"

    command = [str(python), str(server)]
    proc = subprocess.Popen(command, cwd=str(root), env=env)
    return proc.wait()


if __name__ == "__main__":
    raise SystemExit(main())
