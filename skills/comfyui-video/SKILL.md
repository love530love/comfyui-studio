---
name: comfyui-video
description: 用本地 ComfyUI 通过 MCP 生成视频：Wan2.1 文生视频、图生视频与动作迁移，以及 MiniMax H3 音视频单镜（已验证）。当用户要求"用 ComfyUI 生成视频""让这张图动起来""做一段带声音的镜头"或排查视频任务超时时使用。
---

# ComfyUI 视频生成

## 前置条件

1. `comfyui-studio-runner` MCP 已连接，`comfyui_status` 返回 `running`。
2. 必需插件：`ComfyUI-WanVideoWrapper`、`ComfyUI-VideoHelperSuite`。
3. 必需模型（用 `list_models` 核实实际文件名）：
   - 扩散模型：`wan2.1_t2v_1.3B_fp16.safetensors` 或本机其它 Wan 视频模型
   - 文本编码器：UMT5-XXL 的 **bf16 或 fp16** 版本
   - VAE：`Wan2_1_VAE_bf16.safetensors`

## 关键规则

- **T5 不能用 fp8 scaled**。`LoadWanVideoT5TextEncoder` 遇到 `fp8` + `scaled` 会直接抛 `Invalid T5 text encoder model`。选文件名含 `bf16`/`fp16`、不含 `fp8`/`scaled` 的版本。
- **视频任务一律非阻塞提交**：`submit_workflow(workflow_json=..., wait=false)`，然后用 `comfyui_job_status` / `comfyui_wait_job` 轮询。3 分钟以上的任务用阻塞等待会撞 MCP 客户端超时。
- **输出走 `gifs`**：`VHS_VideoCombine` 在 history 里的输出键是 `gifs` 而不是 `images`。runner 已统一解析为 `files`；若看到空列表，先用 `list_outputs` 按 mp4 复核。
- **显存**：1.3B 模型 480×480 可用 `enable_vae_tiling: false`；14B 或更高分辨率必须开 tiling，并保持 `force_offload: true`。

## 已验证链路

Wan2.1 t2v 的完整可复用 JSON、参数含义与踩坑见 `references/wan-video.md`。先用它跑通，再改提示词与画幅。

## 图生视频与动作迁移

- 图生视频：把 `WanVideoEmptyEmbeds` 换成图像输入节点（`WanVideoImageToVideoEncode` 等），输入图先放到 ComfyUI `input/`。节点必填参数用 `get_object_info` 查询，不要凭 UI 显示猜测。
- 动作迁移：ComfyUI 用户目录已保存 `video_wan2_2_14B_animate.json`、`Wan-Animate【动作迁移】换人-高质量+高细节.json` 等 UI 格式工作流。UI 格式不能直接 POST 到 `/prompt`，需要在 ComfyUI 界面里导出 API 格式；导出后同样走本技能的非阻塞提交。

## 时长与帧数

Wan 系列要求帧数满足 `4n+1`（17、33、49、81…）。20fps 下 81 帧约 4 秒。写分镜时先定时长再换算帧数，不要提交任意帧数后期待模型自动补齐。

## MiniMax H3 音视频单镜（2026-11-23 实测通过）

H3 一次生成视频+立体声，单次 5–15 秒、24fps，竖屏 768×1344 与 4 步 turbo LoRA 搭配。用于重点镜头和抽卡支线；常规叙事仍走 Wan。

- 模型（用 `list_models` 核实实际文件名；工作流里出现的不同名字可能是同一文件的符号链接别名）：`minimax_h3_fl2va_pruned_int8_convrot.safetensors`（DiT ~19.5GB）、`qwen3vl_32b_minimax_h3_int8_convrot.safetensors`（TE ~25.3GB）、`minimax_h3_video_vae_fp16.safetensors`、`minimax_h3_audio_vae_fp32.safetensors`、`minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors`。
- 节点链：`LoadImage` → `MiniMaxH3ImageToVideo`（768×1344，length=124）→ `RandomNoise` + `KSamplerSelect(res_multistep)` + `BasicScheduler(simple, steps=4)` + `BasicGuider` → `SamplerCustomAdvanced` → `VAEDecode` + `VAEDecodeAudio` → `VHS_VideoCombine(audio=…, frame_rate=24, video/h264-mp4)`。漏接 `VAEDecodeAudio` 就没有音轨；输出名形如 `*_00001-audio.mp4`。
- 实测（3090 24GB，六启动参数）：`Prompt executed 14:12` 出 124 帧/5.17s；其中文本编码 ~7 分钟、DiT 首次 staging 264s、4 步采样 ~171s（稳态 ~40s/步），其余为双 VAE 解码+封装。峰值显存 22.86/24.58GB——跑前关掉其它占卡程序，按 15 分钟量级等待，期间日志可能长时间无更新但 GPU 仍满载。
- 帧数与 latent：length=124 → latent_t 37 / audio_t 207；turbo LoRA 是 768p 档，与 768×1344 匹配。H3 单次上限约 15s（~360 帧），"75 秒成片"靠分段生成 + 首尾帧衔接。
- 已知坑：`comfyui_smznodes` 在 import 时全局补丁 `comfy.sample.prepare_noise`，对嵌套音视频 latent 只按视频流造噪声，H3 日志报 `size of tensor a (149184) must match the size of tensor b (3593664)`。修复：`custom_nodes/comfyui_smznodes/modules/rng.py` 的 `prepare_noise` 顶部加 `is_nested` 分支委托原生 `store.prepare_noise`；插件重装会覆盖，升级后复查。

## 失败处理

| 现象 | 处理 |
| --- | --- |
| `fp8 scaled is not supported` | 换 bf16/fp16 的 T5 模型 |
| `KeyError: 'precision'` | 给 `WanVideoVAELoader` 显式加 `"precision": "bf16"` |
| `KeyError: 'riflex_freq_index'` | `WanVideoSampler` 补 `"riflex_freq_index": 0` |
| `KeyError: 'load_device'` | `WanVideoModelLoader` 补 `"load_device": "main_device"` 或 `"offload_device"` |
| 任务一直 running | 查 `list_outputs` 与 ComfyUI 日志；不要重复提交同一工作流 |
| CUDA OOM | 降分辨率/帧数，开 VAE tiling；不要自动删模型或清空他人队列 |

## 交付约定

每个镜头输出记录：镜头 id、提示词、seed、帧数与帧率、模型文件名、mp4 相对路径。视频只用于爆点镜头，常规叙事优先用关键帧 + 剪辑运镜，这是漫剧成本结构的核心。
