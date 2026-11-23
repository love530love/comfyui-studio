#!/usr/bin/env python3
"""Smoke-test the runner MCP server against the configured ComfyUI install.

Modes:
    probe    status, node combos and queue only
    image    Z-Image Turbo (falls back to SDXL when its combos are missing)
    video    Wan2.1 1.3B text-to-video through VHS_VideoCombine
    restart  ask the runner to restart ComfyUI and return
    all      image and video
"""

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
            [python, str(ROOT / "bin" / "launch_comfyui_runner.py")],
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
                raise RuntimeError(f"server closed stdout during {method}; stderr: {''.join(self.stderr[-20:])}")
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
        result = self.request("tools/call", {"name": tool, "arguments": arguments or {}}, timeout=timeout)
        text = "\n".join(item.get("text", "") for item in result.get("content", []) if item.get("type") == "text")
        try:
            data = json.loads(text)
        except ValueError:
            data = {"raw": text}
        if result.get("isError"):
            raise RuntimeError(f"{tool}: {data}")
        return data

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def show(title, data):
    print(f"\n### {title}")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:6000])


def option_values(object_info, class_type, field):
    spec = object_info[class_type]["inputs"].get(field, {}).get("definition")
    if isinstance(spec, list) and spec and isinstance(spec[0], list):
        return spec[0]
    return []


def zimage_workflow():
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "qwen_image"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "z-image-ae.safetensors"}},
        "4": {"class_type": "TextEncodeZImageOmni", "inputs": {"clip": ["2", 0], "prompt": "国风动漫短剧角色设定图，年轻女剑客立于雨夜长街，冷色月光，斗笠压低，眼神坚定，电影感构图，高细节", "auto_resize_images": True, "vae": ["3", 0]}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 768, "height": 1344, "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["4", 0], "latent_image": ["5", 0], "seed": 42, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": "studio_zimage_smoke", "images": ["7", 0]}},
    }


def sdxl_workflow():
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "AWPainting_V1.1fp16.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "国风动漫短剧角色设定图，年轻女剑客立于雨夜长街，冷色月光，斗笠压低，眼神坚定，电影感构图，高细节"}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "lowres, bad anatomy, bad hands, text, watermark"}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 832, "height": 1216, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "seed": 42, "steps": 24, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "studio_sdxl_smoke", "images": ["6", 0]}},
    }


def wan_workflow(t5_name):
    return {
        "1": {"class_type": "LoadWanVideoT5TextEncoder", "inputs": {"model_name": t5_name, "precision": "bf16"}},
        "2": {"class_type": "WanVideoModelLoader", "inputs": {"model": "wan2.1_t2v_1.3B_fp16.safetensors", "base_precision": "bf16", "quantization": "disabled", "load_device": "offload_device"}},
        "3": {"class_type": "WanVideoVAELoader", "inputs": {"model_name": "Wan2_1_VAE_bf16.safetensors", "precision": "bf16"}},
        "4": {"class_type": "WanVideoTextEncode", "inputs": {"positive_prompt": "夜雨长街，年轻女剑客压了压斗笠，转身拔剑，雨水飞溅，镜头缓慢推近，电影感光影", "negative_prompt": "", "t5": ["1", 0]}},
        "5": {"class_type": "WanVideoEmptyEmbeds", "inputs": {"width": 480, "height": 480, "num_frames": 17}},
        "6": {"class_type": "WanVideoSampler", "inputs": {"model": ["2", 0], "image_embeds": ["5", 0], "text_embeds": ["4", 0], "steps": 10, "cfg": 3.5, "shift": 5.0, "seed": 42, "scheduler": "euler", "force_offload": True, "riflex_freq_index": 0}},
        "7": {"class_type": "WanVideoDecode", "inputs": {"vae": ["3", 0], "samples": ["6", 0], "enable_vae_tiling": False, "tile_x": 272, "tile_y": 272, "tile_stride_x": 144, "tile_stride_y": 128}},
        "8": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["7", 0], "frame_rate": 20, "loop_count": 0, "filename_prefix": "studio_wan_smoke", "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["probe", "image", "video", "restart", "all"], nargs="?", default="all")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    cfg = load_config()
    client = Client(cfg["venv_python"])
    try:
        init = client.request(
            "initialize",
            {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "comfyui-studio-smoke", "version": "0.1"}},
            timeout=30,
        )
        show("initialize", {"server": init.get("serverInfo"), "protocol": init.get("protocolVersion")})
        client.notify("notifications/initialized")

        status = client.call("comfyui_status")
        show("status", status)
        if args.mode == "restart":
            show("restart", client.call("comfyui_restart", timeout=180))
            return 0
        if status.get("status") != "running":
            print("[FAIL] ComfyUI is not running; rerun with mode 'restart'")
            return 1

        object_info = {}
        for class_type in (
            "UNETLoader",
            "CLIPLoader",
            "VAELoader",
            "CheckpointLoaderSimple",
            "LoadWanVideoT5TextEncoder",
            "WanVideoModelLoader",
            "WanVideoVAELoader",
            "VHS_VideoCombine",
        ):
            try:
                object_info[class_type] = client.call("get_object_info", {"class_type": class_type}, timeout=60)
            except Exception as exc:
                print(f"[warn] object_info {class_type}: {exc}")

        unets = option_values(object_info, "UNETLoader", "unet_name") if "UNETLoader" in object_info else []
        clips = option_values(object_info, "CLIPLoader", "clip_name") if "CLIPLoader" in object_info else []
        vaes = option_values(object_info, "VAELoader", "vae_name") if "VAELoader" in object_info else []
        ckpts = option_values(object_info, "CheckpointLoaderSimple", "ckpt_name") if "CheckpointLoaderSimple" in object_info else []
        t5s = option_values(object_info, "LoadWanVideoT5TextEncoder", "model_name") if "LoadWanVideoT5TextEncoder" in object_info else []
        wan_models = option_values(object_info, "WanVideoModelLoader", "model") if "WanVideoModelLoader" in object_info else []
        wan_vaes = option_values(object_info, "WanVideoVAELoader", "model_name") if "WanVideoVAELoader" in object_info else []
        print("\n[combos]")
        print("unet z_image:", [v for v in unets if "z_image" in v])
        print("clip qwen3:", [v for v in clips if "qwen_3" in v])
        print("vae z-image:", [v for v in vaes if "z-image" in v])
        print("ckpt AWPainting:", [v for v in ckpts if "AWPainting" in v])
        print("t5 umt5/bf16:", [v for v in t5s if "umt5" in v.lower()])
        print("wan model:", [v for v in wan_models if "1.3B" in v])
        print("wan vae:", [v for v in wan_vaes if "Wan2_1_VAE" in v])
        print("VHS node:", "VHS_VideoCombine" in object_info)
        if args.mode == "probe":
            return 0

        if args.mode in ("image", "all"):
            use_zimage = (
                any(v == "z_image_turbo_bf16.safetensors" for v in unets)
                and any(v == "qwen_3_4b.safetensors" for v in clips)
                and any(v == "z-image-ae.safetensors" for v in vaes)
            )
            workflow = zimage_workflow() if use_zimage else sdxl_workflow()
            print(f"\n[image] submitting {'Z-Image' if use_zimage else 'SDXL AWPainting'}")
            show("image job", client.call("submit_workflow", {"workflow_json": workflow, "wait": True, "timeout": 300}, timeout=330))

        if args.mode in ("video", "all"):
            t5_name = next((v for v in t5s if "umt5" in v.lower() and "fp8" not in v.lower()), None)
            if not t5_name:
                t5_name = next((v for v in t5s if "t5" in v.lower() and "fp8" not in v.lower()), None)
            if not t5_name:
                raise RuntimeError(f"no bf16/fp16 T5 available; combos={t5s}")
            print(f"\n[video] submitting Wan2.1 with T5={t5_name}")
            job = client.call("submit_workflow", {"workflow_json": wan_workflow(t5_name), "wait": False}, timeout=60)
            show("video queued", job)
            show("video job", client.call("comfyui_wait_job", {"prompt_id": job.get("prompt_id"), "timeout": 600}, timeout=660))

        print("\n[OK] smoke finished")
        return 0
    except Exception as exc:
        print(f"\n[FAIL] {type(exc).__name__}: {exc}")
        print("\n[stderr tail]\n" + "".join(client.stderr[-40:]))
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
