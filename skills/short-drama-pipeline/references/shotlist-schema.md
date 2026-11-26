# 分镜表 schema（`shotlist/epNN.yaml`）

一个文件一集，按播放顺序排列。字段名固定，供出图、出视频、剪辑三个环节共同读取。

```yaml
episode: 1
title: "第1集 借命"
duration_target: 75          # 秒
video_target: {min: 3, max: 5}   # 可选；H3 全镜模式可设 12–16，G2 冻结
logline: "她替死人签字，签完发现自己也在名单上"
scenes:
  - scene: 1
    location: "殡仪馆 走廊 夜"
    shots:
      - id: ep01_s001
        duration: 3.0          # 秒
        shot_type: CU          # ECU/CU/MS/WS/OTS/POV
        camera: "缓慢推近"
        beat: "发现名单上有自己的名字，手指停在第三行"
        characters: [linwan]
        prompt: "<逐字复用角色卡描述> 殡仪馆冷白灯光，她低头看名单，手指停在第三行"
        negative: "low quality, extra fingers, watermark"
        seed: 1001
        keyframe: 03_keyframes/ep01/ep01_s001.png
        last_frame: 03_keyframes/ep01/ep01_s001_last.png   # 可选：供下一镜接力
        chain_from: ep01_s000                              # 可选：上一镜尾帧作本镜首帧
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
| `beat` | 是 | 本镜唯一的表演节拍；情绪或状态变化必须拆成新镜 |
| `characters` | 是 | 引用 `02_characters/` 的文件名，空数组表示空镜 |
| `prompt` | 是 | 只写画面与动作，不写"她很难过"这类结论 |
| `seed` | 是 | 已提交的镜头固定 seed，返工改 seed 要记入日志 |
| `keyframe` | 是 | 相对项目根目录的路径；视频镜头即首帧 |
| `last_frame` | 否 | 本镜尾帧路径，供下一镜 `chain_from` 接力 |
| `chain_from` | 否 | 引用同场景上一个镜头的 id，用其尾帧作本镜首帧 |
| `video` | 是 | 布尔；true 表示该镜头必须出 mp4 |
| `dialogue` | 否 | 逐字台词，配音与字幕共用 |
| `sfx` | 否 | 音效描述，剪辑据此找素材 |
| `status` | 是 | 流转状态，只有剪辑可置 `edited` |

## 校验

落盘前检查：

1. 所有 `id` 唯一且与上一集不冲突。
2. `sum(duration)` 精确等于 `duration_target`，不留容差。
3. `video: true` 的镜头数在 `video_target` 范围内（默认 3–5；H3 全镜模式可设 12–16）。
4. 每个 `characters` 条目在 `02_characters/` 有对应文件。
5. `keyframe` 路径的文件存在才能把 `status` 推进到 `keyframe_ok`。
6. 每镜 `beat` 非空且只有一条；有 `dialogue` 时，镜头时长 ≥ 字数/4.5 + 0.2 秒。
7. `chain_from` 只能引用同场景的上一个镜头；被引用镜头存在时其 `last_frame` 才能用于本镜首帧。
8. ep02 起：每个角色/道具的 `state` 值必须在 `contracts.yaml` 的合法取值内。
9. ep02 起：`cut`/`chain`/`insert` 只允许状态不变；状态变化必须用 `state_change` 或 `time_jump`，并写 `motivated_by`。
10. ep02 起：同场 `axis_side` 翻转必须配中性镜或 `motivated_by`；`chain` 必须同侧。
11. ep02 起：`characters` 里的角色锚点必须逐字出现在 `prompt`；负面必填词必须出现在 `negative`。
12. `props` 为 `present` 的道具锚点必须出现在 `prompt`，且负面词不得出现在 `prompt`。

一键机检（读 `contracts.yaml`，可选出接触表）：

```bash
<comfyui>/.venv/Scripts/python.exe <comfyui-studio>/skills/short-drama-pipeline/scripts/check_continuity.py \
  --project <project_root> --episode 2 --strict \
  --sheet <project_root>/09_logs/contact/ep02_keyframes.png \
  --video-sheet <project_root>/09_logs/contact/ep02_boundaries.png
```

退出码 1 表示有 error，不得进入下一阶段；warning 必须逐条处置并记录。

## v2 连续性扩展（ep02 起必填）

ep01 为兼容基线，可缺以下字段；ep02 起新镜头必须写全，`scripts/check_continuity.py` 会强制执行。

### 场景级

```yaml
scenes:
  - scene: 1
    location: "陈默家 楼道 / 夜"
    location_ref: 01_series/assets/scenes/loc_hallway.png   # 场景参考图
    time: "夜"
    weather: "雨后"
    axis: "楼道纵深：家门口在画左，窗在画右；机位不越过门框中线"
    state_defaults:                 # 本场默认状态，可被单镜覆盖
      chenmo:
        wardrobe: raincoat_037
        helmet: off_right_hand
        injury: old_scar_only
        wetness: soaked
        held_left: phone
        held_right: helmet
```

### 镜头级

```yaml
      - id: ep02_s001
        axis_side: A                # A/B；同场不越轴
        state:                      # 只写相对 state_defaults 的变化
          chenmo:
            held_right: none
        props:
          cup: absent               # present/absent；present 必须有道具锚点
        transition:
          type: open                # open/chain/cut/match_cut/insert/state_change/time_jump
          chain_from: ep01_s024     # type=chain 时必填，或沿用顶层 chain_from
          motivated_by: "场首"       # 状态或轴线变化时必填
        refs:
          - 03_keyframes/ref/chenmo_ref_v2.png
        prompt_lock: true           # 表示 prompt 必须逐字包含角色锚点
        acceptance:
          - "右手持半盔，贴纸朝后不可见"
          - "雨衣左胸 037 可见，只有一处"
```

### 状态与道具契约

`01_series/continuity/contracts.yaml` 存角色锚点、负面词、合法状态值、道具锚点：

```yaml
version: 1
characters:
  chenmo:
    anchor: "<从 02_characters/chenmo.md 逐字复制>"
    negative_required: ["changed outfit", "missing scar", "full-face helmet"]
    forbidden_positive: ["full-face helmet", "visor", "chin bar", "blood"]
    states:
      helmet: [worn_open_face, off_right_hand, off_left_hand, on_bike, none]
      held_left: [none, phone, cup, bag, receipt]
      held_right: [none, helmet, cup, bag, receipt]
    required_phrases:
      - when: {helmet: worn_open_face, shot_type: [ECU, CU, MS]}
        phrases: ["open-face half helmet", "no visor", "no chin bar"]
props:
  cup:
    anchor: "500ml clear sealed cup with dome lid and straw"
    forbidden: ["can", "bottle", "logo", "brand"]
```

## 与视频技能的对接

`video: true` 的镜头把 `prompt`、`duration`、`seed` 作为视频生成的输入；帧数按 `frame_rate × duration` 取最近的 `4n+1`。生成的 mp4 路径写回该镜头的日志记录，不改 schema 字段。

视频槽位固定：首帧 = `keyframe`；尾帧 = `last_frame`（接力时）；人设参考 = `02_characters/` 定妆图；干音 = `05_audio/` 对应台词。生成后把末帧抽到 `last_frame`，供下一镜 `chain_from` 使用。
