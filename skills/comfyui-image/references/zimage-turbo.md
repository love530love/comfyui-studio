# Z-Image Turbo 已验证工作流

在本机 ComfyUI v0.45.x + RTX 3090 上实测通过的最小文生图链路。模型文件名以 `list_models` 返回为准，缺失时先补模型，不要改节点类型。

| 组件 | 文件 | 模型目录 |
| --- | --- | --- |
| UNET | `z_image_turbo_bf16.safetensors` | `models/diffusion_models/` |
| CLIP | `qwen_3_4b.safetensors` | `models/clip/` |
| VAE | `z-image-ae.safetensors` | `models/vae/` |

```json
{
  "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}},
  "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "qwen_image"}},
  "3": {"class_type": "VAELoader", "inputs": {"vae_name": "z-image-ae.safetensors"}},
  "4": {"class_type": "TextEncodeZImageOmni", "inputs": {"clip": ["2", 0], "prompt": "<prompt>", "auto_resize_images": true, "vae": ["3", 0]}},
  "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
  "6": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["4", 0], "latent_image": ["5", 0], "seed": 42, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
  "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
  "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": "studio_zimage", "images": ["7", 0]}}
}
```

## 已确认的事实

- `TextEncodeZImageOmni` 只输出 1 个 `CONDITIONING`（索引 0）；`positive` 与 `negative` 都接 `["4", 0]`。CFG=1.0 时 negative 分支不起作用，这是蒸馏模型特性。
- 4 步 `euler` + `normal` 是该模型在本机的稳定组合；`euler_ancestral`、`beta`、`simple` 在历史测试中出现明显伪影。
- 首次运行包含模型加载，约 100 秒以上属正常；热模型单张约 6–20 秒。
- 启动参数使用 `--use-pytorch-cross-attention`；`--use-flash-attention` 会产生全噪声图。

## 画幅

- 方图：1024×1024
- 竖屏短剧：768×1344（9:16）、832×1216
- 横屏：1344×768

宽度和高度建议为 16 的倍数。修改画幅只改节点 5，不要改采样参数。
