#!/usr/bin/env python3
"""Write ~/.comfyui-studio/config.json for the comfyui-studio plugin.

The plugin's MCP launchers are portable and contain no machine-specific
paths. This script records the local ComfyUI checkout, its interpreter, the
comfyui-runner server, and optionally PyCharm, once per machine.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def config_path() -> Path:
    raw = os.environ.get("COMFYUI_STUDIO_CONFIG", "~/.comfyui-studio/config.json")
    return Path(raw).expanduser()


def fail(message: str) -> None:
    print(f"[setup] {message}", file=sys.stderr)
    raise SystemExit(2)


def default_python(root: Path) -> Path:
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def _pycharm_from_client_config() -> str | None:
    for raw in ("~/.workbuddy/mcp.json", "~/.qoder/mcp.json", "~/.cursor/mcp.json"):
        path = Path(raw).expanduser()
        if not path.is_file():
            continue
        try:
            servers = json.loads(path.read_text(encoding="utf-8")).get("mcpServers", {})
        except (OSError, ValueError):
            continue
        entry = servers.get("pycharm")
        if not isinstance(entry, dict):
            continue
        candidates = [entry.get("command")] + list(entry.get("args") or [])
        for candidate in candidates:
            if candidate and Path(str(candidate)).name.lower() in ("pycharm64.exe", "pycharm.exe", "pycharm.sh"):
                candidate_path = Path(str(candidate)).expanduser()
                if candidate_path.is_file():
                    return str(candidate_path)
    return None


def detect_pycharm() -> str | None:
    from_config = _pycharm_from_client_config()
    if from_config:
        return from_config

    for env_name in ("PYCHARM_EXE", "PYCHARM_HOME"):
        raw = os.environ.get(env_name)
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path.is_dir():
            for name in ("bin/pycharm64.exe", "bin/pycharm.exe", "bin/pycharm.sh"):
                if (path / name).is_file():
                    return str(path / name)
        elif path.is_file():
            return str(path)

    found = shutil.which("pycharm64") or shutil.which("pycharm")
    if found:
        return found

    if os.name == "nt":
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
            if not base:
                continue
            jetbrains = Path(base) / "JetBrains"
            if jetbrains.is_dir():
                for candidate in sorted(jetbrains.glob("PyCharm*/bin/pycharm64.exe")):
                    return str(candidate)

    return None


def check_runner(python: Path, server: Path) -> None:
    probe = subprocess.run(
        [str(python), "-c", "import mcp, sys; print(sys.version.split()[0])"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if probe.returncode != 0:
        fail(f"{python} does not provide the mcp package: {probe.stderr.strip()}")
    compile_check = subprocess.run(
        [str(python), "-c", "import py_compile,sys; py_compile.compile(sys.argv[1], doraise=True)", str(server)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if compile_check.returncode != 0:
        fail(f"runner server failed to compile: {compile_check.stderr.strip()}")
    print(f"[setup] runner ok: Python {probe.stdout.strip()}, mcp import + compile passed")


def build_config(args: argparse.Namespace) -> dict:
    root = Path(args.comfyui_dir).expanduser().resolve()
    if not (root / "main.py").is_file():
        fail(f"not a ComfyUI checkout (main.py missing): {root}")

    python = Path(args.python).expanduser().resolve() if args.python else default_python(root)
    if not python.is_file():
        fail(f"interpreter not found: {python}")

    server = Path(args.runner_server).expanduser().resolve()
    if not server.is_file():
        fail(f"runner server not found: {server}")

    if not args.skip_checks:
        check_runner(python, server)

    pycharm = args.pycharm_exe or detect_pycharm()
    if pycharm:
        pycharm = str(Path(pycharm).expanduser().resolve())
        if not Path(pycharm).is_file():
            fail(f"PyCharm executable not found: {pycharm}")
    else:
        print("[setup] PyCharm not found; set --pycharm-exe later if you want the IDE bridge", file=sys.stderr)

    project = Path(args.pycharm_project).expanduser().resolve() if args.pycharm_project else root

    return {
        "comfyui_dir": str(root),
        "venv_python": str(python),
        "runner_server": str(server),
        "comfyui_host": args.host,
        "comfyui_port": args.port,
        "comfyui_start_args": args.start_args,
        "pycharm_exe": pycharm,
        "pycharm_project": str(project),
        "pycharm_port": args.pycharm_port,
        "drama_root": str(Path(args.drama_root).expanduser().resolve()),
    }


def write_config(cfg: dict) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(path.name + f".bak-{stamp}")
        shutil.copy2(path, backup)
        print(f"[setup] backed up previous config to {backup}")
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure the comfyui-studio Qoder plugin")
    parser.add_argument("--comfyui-dir", default=os.environ.get("COMFYUI_DIR"), help="ComfyUI checkout root")
    parser.add_argument("--python", help="ComfyUI interpreter (default: <dir>/.venv/...)")
    parser.add_argument("--runner-server", default=os.environ.get("COMFYUI_RUNNER_SERVER"), help="comfyui-runner server.py")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8189)
    parser.add_argument("--start-args", default="", help="extra ComfyUI start arguments")
    parser.add_argument("--pycharm-exe", help="PyCharm executable; auto-detected when omitted")
    parser.add_argument("--pycharm-project", help="project path passed to PyCharm MCP (default: comfyui dir)")
    parser.add_argument("--pycharm-port", type=int, default=64462)
    parser.add_argument("--drama-root", default="~/ShortDramas", help="root folder for short-drama projects")
    parser.add_argument("--check", action="store_true", help="validate the existing config only")
    parser.add_argument("--print", dest="print_only", action="store_true", help="print the config without writing")
    parser.add_argument("--skip-checks", action="store_true", help="skip interpreter and compile probes")
    args = parser.parse_args()

    if args.check:
        path = config_path()
        if not path.is_file():
            fail(f"missing config: {path}")
        cfg = json.loads(path.read_text(encoding="utf-8"))
        for key in ("comfyui_dir", "venv_python", "runner_server"):
            if not cfg.get(key):
                fail(f"config missing {key}")
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
        if not (Path(cfg["comfyui_dir"]) / "main.py").is_file():
            fail("comfyui_dir no longer contains main.py")
        if not Path(cfg["venv_python"]).is_file() or not Path(cfg["runner_server"]).is_file():
            fail("configured interpreter or runner server is missing")
        if not args.skip_checks:
            check_runner(Path(cfg["venv_python"]), Path(cfg["runner_server"]))
        print(f"[setup] config ok: {path}")
        return 0

    if not args.comfyui_dir:
        fail("--comfyui-dir is required (or set COMFYUI_DIR)")
    if not args.runner_server:
        fail("--runner-server is required (or set COMFYUI_RUNNER_SERVER)")

    cfg = build_config(args)
    if args.print_only:
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
        return 0

    path = write_config(cfg)
    print(f"[setup] wrote {path}")
    print("[setup] restart Qoder (or reload plugins) so the MCP launchers pick up the config")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
