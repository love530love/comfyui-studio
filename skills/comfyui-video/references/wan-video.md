# Wan2.1 文生视频：实测工作流

来源：本机 `headless_test_video.py`（ComfyUI v0.45.x，RTX 3090 24GB，实测出片）。模型文件名以 `list_models` 返回为准。

## 节点链路

```
LoadWanVideoT5TextEncoder ─→ WanVideoTextEncode ─┐
WanVideoModelLoader ─────────────────────────────┼→ WanVideoSampler → WanVideoDecode → VHS_VideoCombine
WanVideoEmptyEmbeds ─────────────────────────────┘
WanVideoVAELoader ───────────────────────────────────────────────────────→ (decode)
```

## 可复用 JSON

```json
{
  "1": {"class_type": "LoadWanVideoT5TextEncoder", "inputs": {"model_name": "<umt5-xxl bf16>.safetensors", "precision": "bf16"}},
  "2": {"class_type": "WanVideoModelLoader", "inputs": {"model": "wan2.1_t2v_1.3B_fp16.safetensors", "base_precision": "bf16", "quantization": "disabled", "load_device": "offload_device"}},
  "3": {"class_type": "WanVideoVAELoader", "inputs": {"model_name": "Wan2_1_VAE_bf16.safetensors", "precision": "bf16"}},
  "4": {"class_type": "WanVideoTextEncode", "inputs": {"positive_prompt": "<prompt>", "negative_prompt": "", "t5": ["1", 0]}},
  "5": {"class_type": "WanVideoEmptyEmbeds", "inputs": {"width": 480, "height": 480, "num_frames": 17}},
  "6": {"class_type": "WanVideoSampler", "inputs": {"model": ["2", 0], "image_embeds": ["5", 0], "text_embeds": ["4", 0], "steps": 10, "cfg": 3.5, "shift": 5.0, "seed": 42, "scheduler": "euler", "force_offload": true, "riflex_freq_index": 0}},
  "7": {"class_type": "WanVideoDecode", "inputs": {"vae": ["3", 0], "samples": ["6", 0], "enable_vae_tiling": false, "tile_x": 272, "tile_y": 272, "tile_stride_x": 144, "tile_stride_y": 128}},
  "8": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["7", 0], "frame_rate": 20, "loop_count": 0, "filename_prefix": "studio_wan", "format": "video/h264-mp4", "pingpong": false, "save_output": true}}
}
```

## 参数说明

| 参数 | 实测值 | 说明 |
| --- | --- | --- |
| width / height | 480×480 | 480p 最快；竖屏可用 480×832，14B 模型慎用 |
| num_frames | 17 | 满足 4n+1；81 帧约 4 秒 @20fps |
| steps | 10 | 1.3B 模型 10 步可用；画质要求高时 20 步 |
| cfg | 3.5 | 高于图生图常用值，属 Wan 的推荐区间 |
| shift | 5.0 | 调度偏移，别和 scheduler 混淆 |
| scheduler | euler | 实测稳定 |
| frame_rate | 20 | 与帧数共同决定时长 |
| format | video/h264-mp4 | VHS 输出 mp4 |

## API 提交时容易漏的必填项

这些参数在 UI 上可能不显示或显示为可选，但 API 提交缺失会报 KeyError：

- `WanVideoModelLoader.load_device`：`"offload_device"` 或 `"main_device"`
- `WanVideoVAELoader.precision`：`"bf16"`
- `WanVideoSampler.riflex_freq_index`：`0`
- `VHS_VideoCombine.pingpong`：`false`
- `VHS_VideoCombine.save_output`：`true`

提交前用 `get_object_info(class_type)` 对照一遍必填输入。

## 输出解析

`VHS_VideoCombine` 的结果在 `/history` 中位于 `gifs` 键，字段与 `images` 相同（`filename` / `subfolder` / `type`）。runner 的 `collect_output_files` 已覆盖 `images`、`gifs`、`videos`、`audio`；若仍为空，用 `list_outputs(prefix=".mp4")` 或按前缀复核磁盘。
