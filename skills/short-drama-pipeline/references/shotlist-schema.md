# 分镜表 schema（`shotlist/epNN.yaml`）

一个文件一集，按播放顺序排列。字段名固定，供出图、出视频、剪辑三个环节共同读取。

```yaml
episode: 1
title: "第1集 借命"
duration_target: 75          # 秒
logline: "她替死人签字，签完发现自己也在名单上"
scenes:
  - scene: 1
    location: "殡仪馆 走廊 夜"
    shots:
      - id: ep01_s001
        duration: 3.0          # 秒
        shot_type: CU          # ECU/CU/MS/WS/OTS/POV
        camera: "缓慢推近"
        characters: [linwan]
        prompt: "<逐字复用角色卡描述> 殡仪馆冷白灯光，她低头看名单，手指停在第三行"
        negative: "low quality, extra fingers, watermark"
        seed: 1001
        keyframe: 03_keyframes/ep01/ep01_s001.png
        video: false           # true 才进入视频生成
        dialogue: "第三行……是我的名字。"
        sfx: "纸张摩擦、远处冷柜嗡鸣"
        status: todo           # todo/keyframe_ok/video_ok/edited
```

## 字段约束

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | `epNN_sNNN`，全局唯一，不复用 |
| `duration` | 是 | 秒，保留一位小数；静态帧镜头 2–4 秒，视频镜头 3–5 秒 |
| `shot_type` | 是 | 景别，决定构图与提示词 |
| `camera` | 是 | 推/拉/摇/移/固定；静态镜头靠剪辑实现 |
| `characters` | 是 | 引用 `02_characters/` 的文件名，空数组表示空镜 |
| `prompt` | 是 | 只写画面与动作，不写"她很难过"这类结论 |
| `seed` | 是 | 已提交的镜头固定 seed，返工改 seed 要记入日志 |
| `keyframe` | 是 | 相对项目根目录的路径 |
| `video` | 是 | 布尔；true 表示该镜头必须出 mp4 |
| `dialogue` | 否 | 逐字台词，配音与字幕共用 |
| `sfx` | 否 | 音效描述，剪辑据此找素材 |
| `status` | 是 | 流转状态，只有剪辑可置 `edited` |

## 校验

落盘前检查：

1. 所有 `id` 唯一且与上一集不冲突。
2. `sum(duration)` 与 `duration_target` 偏差不超过 10 秒。
3. `video: true` 的镜头数在 3–5 之间（成本约束）。
4. 每个 `characters` 条目在 `02_characters/` 有对应文件。
5. `keyframe` 路径的文件存在才能把 `status` 推进到 `keyframe_ok`。

## 与视频技能的对接

`video: true` 的镜头把 `prompt`、`duration`、`seed` 作为视频生成的输入；帧数按 `frame_rate × duration` 取最近的 `4n+1`。生成的 mp4 路径写回该镜头的日志记录，不改 schema 字段。
