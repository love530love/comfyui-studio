---
name: comfyui-image
description: 用本地 ComfyUI 通过 MCP 生成图片：Z-Image Turbo 文生图、角色一致性参考图、批量关键帧。当用户要求"用 ComfyUI 生图""出一张图/一组关键帧""验证 ComfyUI 是否可用"时使用。
---

# ComfyUI 图片生成

## 前置条件

1. 插件 MCP 服务器 `comfyui-studio-runner` 已连接（工具名前缀 `mcp__comfyui-studio-runner__` 或当前客户端的等价命名）。
2. 已在本机运行 `python scripts/setup.py`，`~/.comfyui-studio/config.json` 指向真实 ComfyUI 目录。
3. 先用 `comfyui_status` 确认状态。若返回 `not_running`，用 `comfyui_restart` 启动，然后等待 30–60 秒再查询。加载 300+ 自定义节点时首次启动会更慢。

## 出图流程

1. **查节点与模型**：`list_models` 确认 `unet_name`、`clip_name`、`vae_name` 实际文件名；`get_object_info` 确认节点必填参数。不要凭记忆写参数名。
2. **组装 API 格式工作流**：顶层是节点 id → `{class_type, inputs}`，节点间用 `["<id>", <output_index>]` 引用。最小链路见 `references/zimage-turbo.md`。
3. **提交**：`submit_workflow(workflow_json=..., wait=true, timeout=...)`。首次加载模型可能需要 1–3 分钟，超时不要判断为失败，改用 `comfyui_job_status` 查询。
4. **取结果**：返回值中的 `files` 已包含 `images`/`gifs`/`videos`/`audio` 各类输出。再用 `list_outputs` 复核文件落盘。

## 参数决策规则

- 分辨率默认 1024×1024；短剧关键帧按分镜画幅（竖屏 768×1344 或 832×1216），不要混用比例。
- seed 固定才能复现；需要变体时按 `seed = base + index` 递增并在 `00_brief.md` 记录。
- 批量出图**不要**一次塞进一个超大工作流；按镜头逐个提交，失败只重跑该镜头。

## 角色一致性

同一角色跨镜头必须复用参考图与提示词骨架，做法见 `references/character-consistency.md`。核心原则：角色描述文字逐字复用，参考图走 Qwen-Image-Edit 或 Flux Kontext 的图生图节点，不靠"记得画得像"。

## 失败处理

- `prompt` 返回 400/422：先读错误里的 `node_errors`，通常是缺必填参数或模型文件名不存在。用 `get_object_info` 对照修正，不要盲目重试同一 JSON。
- 出图全噪声：检查启动参数是否带 `--use-flash-attention`。该参数与 Z-Image 系列不兼容，用 `comfyui_restart(extra_args="--use-pytorch-cross-attention ...")` 重启后重试。
- 显存不足：降低分辨率或批次数；不要删除其它模型文件来"腾地方"，那是破坏性操作，需要用户确认。

## 输出约定

生成结果交给下游（分镜/剪辑）时，在文件清单里记录：镜头 id、提示词、seed、模型文件名、输出相对路径。没有这些字段的关键帧无法复现，视为未完成。
